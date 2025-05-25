from flask import Flask, render_template, session, redirect, url_for, request, jsonify, flash
from uuid import uuid4
from Game.role import Role, RoleType, PlayerType
from Game.Process import create_role, Initialize, check_game_end
from collections import Counter
import random
import re
from player.AI_Player import generate_speech
import threading

app = Flask(__name__)
app.secret_key = 'secret'
players = []
room_ready = False
refresh_token = str(uuid4())  # 用于前端检测房间状态变化
model_options = ["qwen2:7b", "deepseek-r1:7b"]
app.game_state = None
system_messages = ["系统提示：游戏开始"]

app.system_messages = ["系统提示：游戏开始，天黑请闭眼"]

# 避免内存爆炸
if len(app.system_messages) > 100:
    app.system_messages.pop(0)


class GameState:
    def __init__(self, players):
        self.players = players
        self.wolf, self.god, self.civil = Initialize(players)
        self.day_count = 1
        self.is_night = True
        self.game_over = False
        self.night_done = set()  # 存储夜间完成操作的玩家 ID
        self.day_stage = 'none'  # 'speech', 'vote', 'result'
        self.day_done = set()  # 记录发言/投票完成的玩家
        self.speech_order = []  # 记录发言顺序（玩家 ID）
        self.current_speaker_index = 0
        self.hunter_die_night = False
        self.ai_done = False
        self.seer_checked_results = {}  # 结构为 {seer_id: [(target_id, '好人' / '狼人'), ...]}


speech_history = []  # 全局变量，记录所有玩家的发言历史
# 房主转AI后依旧是房主守护逻辑
def is_current_host(player_id):
    if not players:
        return False
    host = players[0]
    if isinstance(host, str):
        return host == player_id
    elif isinstance(host, dict):
        return host.get("id") == player_id
    elif isinstance(host, Role):
        return getattr(host, 'player_id', None) == player_id  # 从 Role 中取 player_id
    return False


def save_speech(player_id, speech_text, max_history=10):
    """保存一条玩家发言，并按时间顺序维护总历史（所有人混在一起）"""
    global speech_history
    speech_history.append((player_id, speech_text))
    if len(speech_history) > max_history:
        speech_history = speech_history[-max_history:]


def get_recent_history_text():
    """按时间顺序拼接最近发言（所有玩家混合）"""
    global speech_history
    if not speech_history:
        return ""
    lines = [
        f"{get_display_name(pid)}：{text}" for pid, text in speech_history
    ]
    print("get_recent_history_text")
    return "最近所有玩家的发言历史如下：\n" + "\n".join(lines) + "\n"



@app.route('/get_messages')
def get_messages():
    return jsonify({'messages': app.system_messages})


# 玩家进入房间逻辑
@app.route('/')
def index():
    global players, refresh_token
    pid = session.get('player_id')
    if not pid:
        pid = str(uuid4())
        session['player_id'] = pid

        if len(players) < 6:
            players.append(pid)
            refresh_token = str(uuid4())

    player_id = session['player_id']
    is_host = is_current_host(player_id)

    return render_template('game.html', players=players, player_id=player_id,
                           is_host=is_host, model_options=model_options, refresh_token=refresh_token)


# 房主对其他玩家选择AI
@app.route('/add_ai', methods=['POST'])
def add_ai():
    global players, refresh_token
    player_id = session.get('player_id')
    index = int(request.form.get('index'))
    model = request.form.get('model', 'qwen2:7b')

    if not is_current_host(player_id):
        return redirect(url_for('index'))

    if 0 <= index < 6:
        if index >= len(players):
            players.extend([""] * (index - len(players) + 1))
        if players[index] == "":
            players[index] = {'type': 'AI', 'model': model}
    refresh_token = str(uuid4())
    return redirect(url_for('index'))

# 进入游戏 + 阵营划分
@app.route('/room')
def room():
    global players
    session_pid = session.get('player_id')

    # 查找对应的角色对象
    player_role_id = None
    current_index = None

    for idx, role in enumerate(players):
        if isinstance(role, Role) and role.player_id == session_pid:
            player_role_id = role.player_id
            current_index = idx
            break

    # fallback，避免 player_id 为空
    if not player_role_id or not current_index:
        player_role_id = session_pid
        for idx, p in enumerate(players):
            if isinstance(p, Role) and p.player_id == session_pid:
                current_index = idx
                break
            elif isinstance(p, dict) and p.get("id") == session_pid:
                current_index = idx
                break

    if not room_ready and not is_current_host(player_role_id):
        return redirect(url_for('waiting'))

    if app.game_state is None:
        app.game_state = GameState(players)
        print("初始化房间状态")

    if app.game_state.hunter_die_night == True:
        print("进入夜间死亡猎人射击页面")
        print(players[app.game_state.hunter_id].player_id)
        print(app.game_state.hunter_id)
        return redirect(url_for('hunter_shoot'))

    return render_template('room.html', players=players, player_id=player_role_id, current_index=current_index,
                           show_roles=session.get('reveal_roles', False), game_state=app.game_state,
                           is_host=is_current_host(session_pid), system_messages=app.system_messages)


# 初始化角色 + 身份查看
@app.route('/submit_reveal', methods=['POST'])
def submit_reveal():
    global room_ready, refresh_token, players
    player_id = session.get('player_id')

    if room_ready:
        return jsonify({'success': False, 'error': 'Game already initialized'})

    if not is_current_host(player_id):
        return jsonify({'success': False, 'error': 'not host'})

    reveal = request.form.get('reveal', 'no')
    session['reveal_roles'] = (reveal == 'yes')
    room_ready = True
    refresh_token = str(uuid4())

    # 初始化角色
    role_list = create_role()
    for i, p in enumerate(players):
        if isinstance(p, dict) and p.get("type") == "AI":
            model = p.get("model", "qwen2:7b")
            role_list[i].player_type = PlayerType.AI
            role_list[i].model_name = model
            role_list[i].player_id = p.get("id", f"AI-{i}")  # AI房主也保留ID
        else:
            role_list[i].player_type = PlayerType.HUMAN
            role_list[i].model_name = "HUMAN"
            role_list[i].player_id = p

    players = role_list
    print(players)

    return jsonify({'success': True})

# 同步进入游戏页面
@app.route('/check_ready')
def check_ready():
    return jsonify({'ready': room_ready})

# 刷新页面
@app.route('/get_refresh_token')
def get_refresh_token():
    return jsonify({'token': refresh_token})

# 房主AI自选
@app.route('/set_self_ai', methods=['POST'])
def set_self_ai():
    global players, refresh_token
    player_id = session.get('player_id')
    model = request.form.get('model', 'qwen2:7b')

    if not is_current_host(player_id):
        return jsonify({'success': False, 'error': 'Not host'})

    # 替换房主为AI身份，但保留其player_id
    players[0] = {'type': 'AI', 'model': model, 'id': player_id}
    refresh_token = str(uuid4())
    return jsonify({'success': True})

# 游戏主流程启动
@app.route('/progress_game', methods=['GET', 'POST'])
def progress_game():
    game_state = app.game_state

    if request.method == 'POST':
        # 房主手动点击“继续”按钮时
        if not is_current_host(session.get('player_id')):
            return jsonify({'success': False, 'error': 'Not host'})

        if game_state.game_over:
            return jsonify({'success': False, 'error': 'Game already over'})

        # todo: 检查是否结束
        game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god, app.game_state.civil)
        if not game_continue:
            app.game_state.game_over = True
            app.system_messages.append(end_message)

            return jsonify({
                "success": True,
                "game_over": True,
                "message": end_message,
                "redirect_url": "/room"  # 告诉前端跳转到 room 页面
            })

        # 白天 or 黑夜
        if game_state.is_night:
            next_url = url_for('night_phase')
        else:
            if game_state.day_stage == 'none':
                message = f"第{game_state.day_count}天，白天来临"
                app.system_messages.append(message)
                game_state.day_stage = 'speech'
                game_state.day_done = set()
                alive_players = [p for p in players if p.alive]
                game_state.speech_order = [p.player_id for p in alive_players]
                game_state.current_speaker_index = 0
                app.system_messages.append("开始发言阶段")
            next_url = url_for('day_phase')

        return jsonify({
            'success': True,
            'message': '',
            'next': next_url
        })

    elif request.method == 'GET':
        # 遗言后自动跳转：无需权限、直接跳转
        print("来自 GET 请求，进入阶段跳转")

        if game_state.is_night:
            print("Get的黑夜")
            return redirect(url_for('night_phase'))
        else:
            print("Get的白天")
            if game_state.day_stage == 'none':
                message = f"第{game_state.day_count}天，白天来临"
                app.system_messages.append(message)

                # TODO:白天发言前判断游戏结束
                game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god,
                                                            app.game_state.civil)
                if not game_continue:
                    app.game_state.game_over = True
                    app.system_messages.append(end_message)

                    return jsonify({
                        "success": True,
                        "game_over": True,
                        "message": end_message,
                        "redirect_url": "/room"  # 告诉前端跳转到 room 页面
                    })

                game_state.day_stage = 'speech'
                game_state.day_done = set()
                alive_players = [p for p in players if p.alive]
                game_state.speech_order = [p.player_id for p in alive_players]
                game_state.current_speaker_index = 0
                app.system_messages.append("开始发言阶段")
            return redirect(url_for('day_phase'))


# 夜间跳转
@app.route('/night')
def night_phase():
    print("现在在night_phase")

    # todo:夜间游戏流程结束
    game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god, app.game_state.civil)
    if not game_continue:
        app.game_state.game_over = True
        app.system_messages.append(end_message)

        return jsonify({
            "success": True,
            "game_over": True,
            "message": end_message,
            "redirect_url": "/room"  # 告诉前端跳转到 room 页面
        })

    player_id = session.get('player_id')
    current_player = next((p for p in players if isinstance(p, Role) and p.player_id == player_id), None)

    message = f"第{app.game_state.day_count}天，夜晚降临"
    app.system_messages.append(message)
    print(message)

    # 没找到或不是人类玩家，就渲染一个等待页面
    if current_player is None or current_player.player_type != PlayerType.HUMAN:
        return render_template('/night/night_ai.html')

    role_type = current_player.role_type

    # 根据身份渲染不同夜间操作界面
    if role_type == RoleType.WEREWOLF and current_player.alive:
        return render_template('/night/wolf.html', players=players, self_id=player_id)
    elif role_type == RoleType.SEER and current_player.alive:
        return render_template('/night/seer.html', players=players)
    elif (role_type == RoleType.VILLAGER or role_type == RoleType.HUNTER) and current_player.alive:
        return render_template('/night/civil.html')
    else:
        return render_template('/room_spectator.html', players=players, system_messages=app.system_messages,
                               show_roles=True)


@app.route('/night_done', methods=['POST'])
def night_done():
    print("现在在night_done（人类玩家）")
    player_id = session.get('player_id')
    game_state = app.game_state

    if not game_state.is_night:
        return jsonify({'success': False, 'error': '不是夜晚'})

    player = next((p for p in players if isinstance(p, Role) and p.player_id == player_id), None)
    if not player:
        return jsonify({'success': False, 'error': '无效玩家'})

    # 只要是人类玩家（活着或死了），都加入 night_done
    if player.player_type == PlayerType.HUMAN:
        if player.alive:
            # 活着的狼人需要传入目标
            if player.role_type == RoleType.WEREWOLF:
                data = request.get_json()
                kill_id = data.get('kill_id')  # 接收前端传来的目标
                if not hasattr(game_state, 'werewolf_votes'):
                    game_state.werewolf_votes = {}
                if kill_id is None:
                    return jsonify({'success': False, 'error': '未选择目标'})
                game_state.werewolf_votes[player_id] = kill_id
                print(f"人类狼人 {player_id} 选择杀 {kill_id}")
        else:
            print(f"已死亡人类玩家 {player_id} 自动完成夜晚操作")

    # 人类玩家操作完成
    game_state.night_done.add(player_id)

    # 若所有人类玩家都完成，则执行 AI 行为
    alive_human_ids = [p.player_id for p in players if p.player_type == PlayerType.HUMAN and p.alive]

    game_state.ai_done = False

    # if game_state.night_done.issuperset(alive_human_ids):
    #     run_ai_night_actions()
    if game_state.night_done.issuperset(alive_human_ids):
        # 用线程异步运行AI，避免阻塞请求
        threading.Thread(target=run_ai_async).start()

    # return jsonify({
    #     'success': True,
    #     'message': '操作已提交',
    #     'redirect': url_for('room')
    # })
    return jsonify({
        'success': True,
        'message': '操作已提交',
        'redirect': None
    })


def run_ai_async():
    run_ai_night_actions()
    app.game_state.ai_done = True


def get_display_name(player):
    return getattr(player, "nickname", f"P{players.index(player) + 1}")


def run_ai_night_actions():
    game_state = app.game_state

    for player in players:
        if not isinstance(player, Role) or not player.alive or player.player_type != PlayerType.AI:
            continue

        print(f"AI处理中: {player.role_type}")

        if player.role_type == RoleType.SEER:
            # AI预言家查验
            targets = [x for x in players if isinstance(x, Role) and x.alive and x.player_id != player.player_id]
            if targets:
                # candidate_names = "、".join([getattr(t, "nickname", f"P{t.player_id}") for t in targets])
                candidate_names = "、".join([
                    getattr(t, "nickname", f"P{players.index(t) + 1}")
                    for t in targets
                ])
                # 获取当前预言家的查验历史
                seer_history = game_state.seer_checked_results.get(player.player_id, [])
                history_text = ""
                if seer_history:
                    history_lines = [
                        f"你曾查验玩家P{get_display_name(target_id)}，TA是{label}。" for target_id, label in seer_history
                    ]
                    history_text = "你的历史查验记录如下：\n" + "\n".join(history_lines) + "\n"
                    print(history_text)
                # 构造 prompt
                day_count = game_state.day_count
                history_text = get_recent_history_text()
                prompt = (
                        player.prompt
                        + "\n" + history_text  # ✅ 添加查验记录
                        + f"现在是第{day_count}天夜晚，你是玩家{get_display_name(player)}，你需要查验玩家身份，必须在以下目标中选择其中一个：{candidate_names}。"
                        + "最终你必须输出“我希望查验XX。”然后输出你的选择理由，字数不要太长"
                        + f"{history_text}"
                )

                result = generate_speech(prompt, model=player.model_name)
                print(f"本结果由{player.model_name}生成\n", result)

                # 提取查验对象
                match = re.search(r"验([^\。\s“”\"']+)", result)
                target_name = match.group(1) if match else None

                # target = next((x for x in targets if getattr(x, "nickname", f"P{x.player_id}") == target_name), None)
                target = next((x for x in targets if get_display_name(x) == target_name), None)
                if not target:
                    print("模型输出未能匹配到目标，默认选择第一个")
                    target = targets[0]

                # 查验并记录结果
                result_label = '狼人' if target.role_type == RoleType.WEREWOLF else '好人'
                app.system_messages.append(
                    f'AI预言家查验了 {get_display_name(target)}，TA是{result_label}'
                )

                if player.player_id not in game_state.seer_checked_results:
                    game_state.seer_checked_results[player.player_id] = []
                game_state.seer_checked_results[player.player_id].append((target.player_id, result_label))
            game_state.night_done.add(player.player_id)


        elif player.role_type == RoleType.WEREWOLF:
            # AI狼人杀人
            targets = [x for x in players if isinstance(x, Role) and x.alive and x.role_type != RoleType.WEREWOLF]

            if targets:
                candidate_names = "、".join([get_display_name(t) for t in targets])
                day_count = game_state.day_count

                # AI狼人生成杀人 prompt
                history_text = get_recent_history_text()
                prompt = player.prompt + f"\n现在是第{day_count}天夜晚，你是玩家{get_display_name(player)}，你是狼人，必须从以下人中选择一位杀死：{candidate_names}。最终你必须输出“我决定杀死XX。”然后输出你的选择理由，字数不要太长"+ f"{history_text}"
                result = generate_speech(prompt, model=player.model_name)
                print(f"本结果由{player.model_name}生成\n", result)

                # todo：狼人杀人正则
                # match = re.search(r"杀死([^\。\s“”\"']+)", result)
                match = re.search(r"杀死\s*([Pp]?\d+)", result)

                target_name = match.group(1) if match else None
                target = next((x for x in targets if get_display_name(x) == target_name), None)

                if not target:
                    print("模型输出未能匹配到目标，默认选择第一个")
                    target = random.choice(targets)
                if not hasattr(game_state, 'werewolf_votes'):
                    game_state.werewolf_votes = {}
                game_state.werewolf_votes[player.player_id] = target.player_id

            game_state.night_done.add(player.player_id)

        else:
            # 其他 AI 玩家
            game_state.night_done.add(player.player_id)

    # === 若所有玩家夜间完成 ===
    all_alive_ids = [p.player_id for p in players if p.alive]
    if game_state.night_done.issuperset(all_alive_ids):
        # 狼人杀人结果
        if hasattr(game_state, 'werewolf_votes'):
            vote_counts = Counter(game_state.werewolf_votes.values())
            if vote_counts:
                most_common = vote_counts.most_common()
                max_votes = most_common[0][1]
                top_targets = [target_id for target_id, count in most_common if count == max_votes]
                kill_target_id = random.choice(top_targets)
                if len(top_targets) > 1:
                    app.system_messages.append("狼人出现平票，随机选择受害者...")

                kill_target = next((p for p in players if isinstance(p, Role) and p.player_id == kill_target_id), None)
                if kill_target and kill_target.alive:
                    kill_target.alive = False
                    app.system_messages.append(
                        f"夜晚过去了，{get_display_name(kill_target)} 遇害身亡。"
                    )

                    # 白天清算猎人死亡事件
                    if kill_target.role_type == RoleType.HUNTER:
                        hunter_index = players.index(kill_target)
                        print(f"{get_display_name(kill_target)} 是猎人，进入猎人开枪流程")
                        app.game_state.hunter_id = hunter_index
                        handle_hunter_shoot(hunter_index)

            del game_state.werewolf_votes

        # 切换为白天
        game_state.is_night = False
        game_state.day_stage = 'none'
        game_state.day_count += 1
        app.system_messages.append(f"第{game_state.day_count}天，天亮了")


# 猎人夜间逻辑
def handle_hunter_shoot(hunter_id):
    hunter = players[hunter_id]
    app.game_state.hunter_shot_pending = True
    app.game_state.hunter_id = hunter_id

    # 如果是AI猎人，立刻执行射击逻辑
    if hunter.player_type.name == "AI":
        # 选择一个非自己且存活的人
        alive_targets = [p for p in players if p.alive and p.player_id != hunter.player_id]
        if not alive_targets:
            print("无人可射击，游戏应该结束")
            app.game_state.hunter_shot_pending = False
            app.game_state.last_words_pending = []
            return

        # todo：AI猎人杀人
        candidate_names = "、".join([get_display_name(p) for p in alive_targets])
        history_text = get_recent_history_text()

        prompt = hunter.prompt + f"\n现在是夜晚，你是玩家{get_display_name(hunter)}，你是猎人，被狼人杀死，你必须从以下人中选择一位开枪击杀：{candidate_names}。最终你必须输出“我决定击杀XX。”然后输出你的选择理由，字数不要太长"+f"{history_text}"

        result = generate_speech(prompt, model=hunter.model_name)
        print(f"本结果由{hunter.model_name}生成\n", result)

        match = re.search(r"杀([^\。\s“”\"']+)", result)
        target_name = match.group(1) if match else None

        shot_player = next((p for p in alive_targets if getattr(p, "nickname", f"P{p.player_id}") == target_name), None)
        if not shot_player:
            print("模型匹配结果", target_name)
            shot_player = random.choice(alive_targets)

        print("模型匹配结果", target_name)
        shot_index = players.index(shot_player)
        shot_player.alive = False

        app.system_messages.append(
            f"{hunter.name}（P{hunter_id + 1}）发动了猎人技能，击杀了{shot_player.name}（P{shot_index + 1}）！"
        )

        app.game_state.hunter_shot_pending = False
        app.game_state.hunter_victim_id = shot_index

    else:
        app.game_state.hunter_die_night = True
        print(f"{hunter.name} 是人类猎人，白天将进入技能清算环节")


def get_player_by_id(player_id):
    if not app.game_state or not app.game_state.players:
        return None
    for player in app.game_state.players:
        if hasattr(player, 'player_id') and player.player_id == player_id:
            return player
    return None


def get_player_name(player_id):
    for i, p in enumerate(players):
        if isinstance(p, Role) and p.player_id == player_id:
            return f"P{i + 1}"
    return player_id


@app.route('/day')
def day_phase():
    print("当前阶段：", app.game_state.day_stage)

    # todo：游戏结束检查
    game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god, app.game_state.civil)
    if not game_continue:
        app.game_state.game_over = True
        app.system_messages.append(end_message)

        return jsonify({
            "success": True,
            "game_over": True,
            "message": end_message,
            "redirect_url": "/room"  # 告诉前端跳转到 room 页面
        })

    if app.game_state.day_stage == 'speech':
        return redirect(url_for('speech_handle'))
    elif app.game_state.day_stage == 'vote':
        message = "现在开始投票放逐阶段"
        app.system_messages.append(message)
        return redirect(url_for('vote_handle'))
    elif app.game_state.day_stage == 'result':
        return redirect(url_for('room'))  # 结果阶段可以展示在 room 页面
    else:
        return redirect(url_for('room'))


@app.route('/day/speech')
def speech_handle():
    global players
    # 发言阶段是否已结束
    if app.game_state.current_speaker_index >= len(app.game_state.speech_order):
        print("发言阶段已结束，进入投票阶段")
        app.game_state.day_stage = 'vote'
        return redirect(url_for('day_phase'))

    current_speaker_id = app.game_state.speech_order[app.game_state.current_speaker_index]
    player = get_player_by_id(current_speaker_id)

    # todo：预言家的发言有额外prompt
    if current_speaker_id != session['player_id']:
        if player.player_type == PlayerType.AI:
            print("当前正在进行AI类型玩家发言")
            alive_players = [p for p in players if p.alive]

            player_info_lines = []
            for p in alive_players:
                player_info_lines.append(f"{get_display_name(p)}")
            player_info = "\n".join(player_info_lines)

            # todo:游戏AI发言阶段
            day_count = app.game_state.day_count
            history = get_recent_history_text()
            prompt = (
                f"{player.prompt}\n"
                f"现在是第{day_count}天白天发言阶段。\n"
                f"以下是仍然存活的玩家：\n{player_info}\n"
                f"请你以玩家身份进行发言，你是玩家{get_display_name(player)}，分析场上情况，可以猜测其他玩家身份，也可以隐瞒自己的身份，最后以“我发言完毕。”结尾。发言字数不超过100字"
                f"{history}"
            )
            print("即将生成")

            speech = generate_speech(prompt, model=player.model_name)
            print(f"本发言由 {player.model_name} 生成：\n{speech}")

            message = f"{get_player_name(player.player_id)} 说：{speech}"
            app.system_messages.append(message)

            app.game_state.current_speaker_index += 1
        return redirect(url_for('speech_handle'))

    # 当前玩家是 AI
    # todo: 对于 预言家 有额外身份信息
    if player.player_type.name == "AI":
        print("当前主控是AI玩家")
        alive_players = [p for p in players if p.alive]

        player_info_lines = []
        for p in alive_players:
            player_info_lines.append(f"{get_display_name(p)}")
        player_info = "\n".join(player_info_lines)

        # todo:游戏AI发言阶段
        day_count = app.game_state.day_count
        history = get_recent_history_text()
        prompt = (
            f"{player.prompt}\n"
            f"现在是第{day_count}天白天发言阶段。\n"
            f"以下是仍然存活的玩家：\n{player_info}\n"
            f"请你以玩家身份进行发言，你是玩家{get_display_name(player)}，分析场上情况，可以猜测其他玩家身份，也可以隐瞒自己的身份，最后以“我发言完毕。”结尾。发言字数不超过100字"
            f"{history}"
        )

        speech = generate_speech(prompt, model=player.model_name)
        print(f"本发言由 {player.model_name} 生成：\n{speech}")

        message = f"{get_player_name(player.player_id)} 说：{speech}"
        app.system_messages.append(message)

        app.game_state.current_speaker_index += 1
        return redirect(url_for('speech_handle'))

    # 当前玩家是 HUMAN，展示发言界面
    return render_template('room.html',
                           players=players,
                           game_state=app.game_state,
                           player_id=session['player_id'],
                           system_messages=app.system_messages,
                           show_roles=True)


@app.route('/submit_speech', methods=['POST'])
def submit_speech():
    speech = request.form.get('speech', '').strip()
    player_id = session.get('player_id')
    player = get_player_by_id(player_id)

    if not player or app.game_state.day_stage != 'speech':
        return redirect(url_for('room'))

    if player.player_id != app.game_state.speech_order[app.game_state.current_speaker_index]:
        return redirect(url_for('room'))

    app.system_messages.append(f"{get_player_name(player_id)} 说：{speech}")
    app.game_state.current_speaker_index += 1

    if app.game_state.current_speaker_index >= len(app.game_state.speech_order):
        app.game_state.day_stage = 'vote'

    return redirect(url_for('speech_handle'))


@app.route('/day/vote', methods=['GET', 'POST'])
def vote_handle():
    global players
    game_state = app.game_state

    # todo：游戏结束排查
    game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god, app.game_state.civil)
    if not game_continue:
        app.game_state.game_over = True
        app.system_messages.append(end_message)

        return jsonify({
            "success": True,
            "game_over": True,
            "message": end_message,
            "redirect_url": "/room"  # 告诉前端跳转到 room 页面
        })

    alive_players = [p for p in players if p.alive]

    # 初始化投票记录结构
    if not hasattr(game_state, 'votes'):
        game_state.votes = {}  # { voter_id: voted_id }

    # 获取当前投票者
    current_index = len(game_state.votes)

    if current_index >= len(alive_players):
        print("已有一个投票结果")
        # 所有人都投过票，开始统计票数
        vote_count = {}
        for voted_id in game_state.votes.values():
            vote_count[voted_id] = vote_count.get(voted_id, 0) + 1

        # 构建详细投票信息
        vote_table = {}
        for voter_id, voted_id in game_state.votes.items():
            vote_table.setdefault(voted_id, []).append(voter_id)

        # 构建展示信息
        vote_summary = [
            {
                'target': f"P{voted + 1}",
                'target_name': players[voted].name,
                'voters': [f"P{v + 1}" for v in voters],
                'count': len(voters)
            }
            for voted, voters in vote_table.items()
        ]

        # todo:构造消息文本美化
        message_lines = ["投票结果：", "被投票者\t\t投票者\t\t票数"]
        for item in vote_summary:
            voters_str = "、".join(item['voters'])
            line = f"{item['target_name']} ({item['target']})\t\t{voters_str}\t\t{item['count']}"
            message_lines.append(line)

        final_message = "\n".join(message_lines)
        print(final_message)

        # 存入系统消息
        app.system_messages.append(final_message)

        # 找出最高票数
        max_votes = max(vote_count.values())
        top_voted = [pid for pid, count in vote_count.items() if count == max_votes]

        if len(top_voted) == 1:
            # 唯一最高票，放逐该玩家
            executed_id = top_voted[0]
            players[executed_id].alive = False
            game_state.executed_player = executed_id
            game_state.votes = {}
            game_state.day_stage = 'result'
            print("已产生被放逐者，当前阶段result")

            message = f"{players[executed_id].name}被放逐！"
            app.system_messages.append(message)

            # TODO：放逐后游戏结束判断
            game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god, app.game_state.civil)
            if not game_continue:
                app.game_state.game_over = True
                app.system_messages.append(end_message)

                return jsonify({
                    "success": True,
                    "game_over": True,
                    "message": end_message,
                    "redirect_url": "/room"  # 告诉前端跳转到 room 页面
                })

            if players[executed_id].role_type == RoleType.HUNTER:
                app.game_state.hunter_shot_pending = True
                app.game_state.hunter_id = executed_id
                # 存活玩家中排除自己
                app.game_state.hunter_targets = [p.player_id for p in players if p.alive and p.player_id != executed_id]
                return redirect(url_for('hunter_shoot'))

            else:
                app.game_state.last_words_pending = [executed_id]

                return redirect(url_for('last_words_handle'))

        else:
            tied_names = [players[pid].name for pid in top_voted]
            tied_names_str = "、".join(tied_names)
            message = f"{tied_names_str} 投票平票，将进行第二轮投票。"
            app.system_messages.append(message)
            # 平票：进行第二轮投票
            if getattr(game_state, 're_vote', False):
                # 已经平票过一次，再次平票则无人被放逐
                game_state.executed_player = None
                game_state.day_stage = 'none'
                game_state.votes = {}
                game_state.re_vote = False
                message = f"依旧产生平票，无人被放逐"
                app.system_messages.append(message)
                app.game_state.is_night = True
                return redirect(url_for('progress_game'))
            else:
                # 开始第二轮投票
                game_state.re_vote = True
                game_state.votes = {}
                game_state.survivors_for_vote = top_voted
                return redirect(url_for('vote_handle'))  # 再次投票

    else:
        current_player = alive_players[current_index]
        print("当前投票者是", current_player)
        if current_player.player_type.name == "AI":
            # TODO：AI玩家投票选择
            # 获取存活玩家及其在 players 中的编号
            alive_players = [(f"P{players.index(p) + 1}", p) for p in players if p.alive]
            player_info = "\n".join([f"{pid}: {p.name}" for pid, p in alive_players])
            history = get_recent_history_text()

            prompt = (
                f"{current_player.prompt}\n"
                f"现在是第{app.game_state.day_count}天白天投票阶段。\n"
                f"以下是仍然存活的玩家：\n{player_info}\n"
                f"请你以玩家身份思考，你是玩家{get_display_name(current_player)}，并决定你要投票给谁。只输出你想投票的玩家姓名即可，不要添加其他内容。"
                f"{history}"
            )

            speech = generate_speech(prompt, model=current_player.model_name)
            print(f"本发言由 {current_player.model_name} 生成：\n{speech}")

            match = re.search(r"\bP\d+\b", speech.strip())
            ai_vote_code = match.group(0) if match else None

            # 找出对应的玩家对象
            voted_player = None
            for pid, p in alive_players:
                if pid == ai_vote_code:
                    voted_player = p
                    break

            # fallback 机制：如果提取失败，就随机投票
            if voted_player is None:
                voted_player = random.choice([p for _, p in alive_players])

            voted_index = players.index(voted_player)
            print(f"AI投票给了： - 玩家名：{players[voted_index].name}")

            game_state.votes[players.index(current_player)] = voted_index
            return redirect(url_for('vote_handle'))
        else:
            # Human玩家，展示投票页面
            if request.method == 'POST':
                voted_index = int(request.form['voted_id'])
                print(f"人类投票给了：PX - 玩家名：{players[voted_index].name}")
                game_state.votes[players.index(current_player)] = voted_index
                return redirect(url_for('vote_handle'))

            print("当前状态", game_state.day_stage)

            return render_template('room.html',
                                   players=players,
                                   player_id=current_index,
                                   game_state=game_state,
                                   system_messages=app.system_messages,
                                   show_roles=True)


@app.route('/day/last_words')
def last_words_handle():
    global players

    pending_list = getattr(app.game_state, 'last_words_pending', [])
    print("pending_list", pending_list)

    if not pending_list:
        print("遗言发表完成")
        # 无遗言玩家，直接进入下一阶段
        app.game_state.executed_player = None
        app.game_state.hunter_victim_id = None
        app.game_state.day_stage = 'none'
        app.game_state.votes = {}
        app.game_state.is_night = True
        app.game_state.night_done = set()
        print("刷新夜间需要的信息")
        return redirect(url_for('progress_game'))

    current_id = pending_list[0]
    app.game_state.executed_player = current_id
    player = players[current_id]
    current_player_id = session.get('player_id')

    # todo：预言家和狼人额外消息
    if player.player_type.name == "AI":
        day_count = app.game_state.day_count
        alive_players = [p for p in players if p.alive or p.player_id == player.player_id]

        player_info_lines = []
        for p in alive_players:
            role_hint = "不明身份"
            if p.player_id == player.player_id:
                role_hint = player.role_type.value
            player_info_lines.append(f"{get_display_name(p)}：{role_hint}，存活")
        player_info = "\n".join(player_info_lines)
        history = get_recent_history_text()

        # TODO: AI 发表遗言
        prompt = (
            f"{player.prompt}\n"
            f"现在是第{day_count}天的遗言阶段，你刚刚被投票处决。\n"
            f"以下是场上的玩家信息：\n{player_info}\n"
            f"请你发表一段遗言，你是玩家{get_display_name(player)}，可以分析局势、指认其他玩家、误导或喊话，最后以“我遗言完毕。”结尾。字数不超过100字"
            f"{history}"
        )

        print("AI玩家正在发表遗言")

        content = generate_speech(prompt, model=player.model_name)
        print(f"本遗言由 {player.model_name} 生成：\n{content}")

        app.system_messages.append(f"{player.name}（P{current_id + 1}）的遗言说：{content}")
        app.game_state.last_words_pending.pop(0)
        return redirect(url_for('last_words_handle'))

    print("真人遗言阶段")
    print("当前阶段", app.game_state.day_stage)
    print("executed_player应该不为none", app.game_state.executed_player)

    return render_template('room.html',
                           players=players,
                           player_id=current_player_id,
                           executed_id=current_id,
                           executed_player=player,
                           game_state=app.game_state,
                           system_messages=app.system_messages,
                           show_roles=True)


# 修改后的，未测试
@app.route('/submit_last_words', methods=['POST'])
def submit_last_words():
    global players

    # 得到的uuid
    submitted_id = request.form['player_id']
    index = next((i for i, p in enumerate(players) if str(p.player_id) == str(submitted_id)), None)
    last_words = request.form['last_words']

    if index not in app.game_state.last_words_pending:
        flash("不是你该说话的时候！", "error")
        return redirect(url_for('room'))

    executed_player = players[index]
    app.system_messages.append(f"{executed_player.name}（P{index + 1}）的遗言说：{last_words}")

    # 从等待列表中移除该玩家
    app.game_state.last_words_pending.remove(index)

    # 如果还有人没说完遗言
    if app.game_state.last_words_pending:
        return redirect(url_for('last_words_handle'))

    # 所有遗言完毕，进入夜晚
    app.game_state.executed_player = None
    app.game_state.hunter_victim_id = None
    app.game_state.day_stage = 'none'
    app.game_state.votes = {}
    app.game_state.is_night = True
    return redirect(url_for('progress_game'))


@app.route('/day/hunter_shoot', methods=['GET', 'POST'])
def hunter_shoot():
    hunter_id = app.game_state.hunter_id
    print("hunter_id", hunter_id)
    hunter = players[hunter_id]

    shot_id = None

    # AI猎人自动发动技能
    if hunter.player_type.name == "AI":
        # todo： AI猎人选择目标
        alive_targets = [p for p in players if p.alive and p.player_id != hunter_id]

        # player_list_info = "\n".join([f"P{p.player_id + 1}（{p.name}）" for p in alive_targets])

        player_info_lines = []
        for p in alive_targets:
            role_hint = "不明身份"
            player_info_lines.append(f"{get_display_name(p)}：{role_hint}，存活")
        player_info = "\n".join(player_info_lines)
        history = get_recent_history_text()

        prompt = (
            f"{hunter.prompt}\n"
            f"你是狼人杀游戏中的猎人，你是玩家{get_display_name(hunter)}，现在你已死亡，可以立即带走一名玩家。\n"
            f"当前仍存活的玩家有：\n{player_info}\n"
            f"请你选择你怀疑是狼人或最有可能对好人不利的一人带走，并简要说明理由，最后返回目标玩家编号（如：3）"
            f"{history}"
        )

        # 生成内容（返回值应为编号）
        response = generate_speech(prompt, model=hunter.model_name)

        # 尝试解析 response，提取 player_id
        shot_id = None
        for p in alive_targets:
            if str(p.player_id + 1) in response:
                shot_id = p.player_id
                break

        # 如果提取失败，fallback
        if shot_id is None:
            print("提取失败，随机选择一个")
            shot_id = alive_targets[0].player_id

        shot_player = players[shot_id]
        players[shot_id].alive = False
        app.system_messages.append(
            f"{hunter.name}（P{hunter_id + 1}）发动了猎人技能，击杀了{shot_player.name}（P{shot_id + 1}）！")

        # TODO：AI猎人杀人游戏结束判断
        game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god, app.game_state.civil)
        if not game_continue:
            app.game_state.game_over = True
            app.system_messages.append(end_message)

            return jsonify({
                "success": True,
                "game_over": True,
                "message": end_message,
                "redirect_url": "/room"  # 告诉前端跳转到 room 页面
            })

        app.game_state.hunter_shot_pending = False
        app.game_state.hunter_victim_id = shot_id

        app.game_state.last_words_pending = [hunter_id, shot_id]

        return redirect(url_for('last_words_handle'))

    # 人类猎人执行射杀
    if request.method == 'POST':
        shot_id = request.form['shot_id']
        print("shot_id", shot_id)

        index = next((i for i, p in enumerate(players) if str(p.player_id) == str(shot_id)), None)

        print("人类猎人击杀目标", index)
        players[index].alive = False
        app.system_messages.append(f"{hunter.name}发动了猎人技能，击杀了{players[index].name}！")

        # TODO：人类猎人杀人游戏结束判断
        game_continue, end_message = check_game_end(app.game_state.wolf, app.game_state.god, app.game_state.civil)
        if not game_continue:
            app.game_state.game_over = True
            app.system_messages.append(end_message)

            return jsonify({
                "success": True,
                "game_over": True,
                "message": end_message,
                "redirect_url": "/room"  # 告诉前端跳转到 room 页面
            })

        app.game_state.hunter_shot_pending = False
        app.game_state.hunter_victim_id = index

        app.game_state.last_words_pending = [hunter_id, index]

        if app.game_state.hunter_die_night == True:
            print("死于夜间，无遗言")
            app.game_state.hunter_die_night = False
            return redirect(url_for('room'))
        else:
            return redirect(url_for('last_words_handle'))

    # GET 请求显示页面
    targets = []
    for i, p in enumerate(players):
        if p.alive and p.player_id != hunter.player_id:
            # 找到这个角色在 players 中的索引
            index = next(idx for idx, player in enumerate(players) if player.player_id == p.player_id)
            targets.append({"player": p, "index": index})

    print("hunter", hunter)
    print("hunter_id", hunter_id)
    print("targets", targets)
    print("最终击杀目标", shot_id)
    return render_template('hunter_shoot.html', hunter=hunter, hunter_id=hunter_id,
                           targets=targets)


# seer页面的函数
@app.route('/get_identity')
def get_identity():
    player_id = request.args.get('player')  # 前端传入 "P1" ~ "P6"

    if not player_id:
        return jsonify({'success': False, 'error': '未识别到玩家 ID，请重新进入游戏'})

    if session.get(f'has_viewed_identity_{player_id}'):
        return jsonify({'success': False, 'error': '你已经查看过身份，不能重复查看'})

    # 🔧 修正匹配字段为 name
    current_player = next((p for p in players if isinstance(p, Role) and p.name == player_id), None)

    if not current_player:
        return jsonify({'success': False, 'error': '身份信息不存在，请确认你已进入房间'})

    # 标记为已查看
    session[f'has_viewed_identity_{player_id}'] = True
    # 只返回“狼人”或“好人”标签
    label = '狼人' if current_player.role_type.name == 'WEREWOLF' else '好人'
    alive = '存活' if current_player.alive else '死亡'

    # 日志记录
    app.system_messages.append(
        f"系统提示：玩家{player_id}被查看了身份：{label}"
    )

    return jsonify({
        'success': True,
        'role': current_player.role_type.name,
        'label': label,
        'if_alive': alive,
        'player_type': current_player.player_type.name,
        'model': current_player.model_name
    })


@app.route('/get_players')
def get_players():
    def serialize_player(p):
        if isinstance(p, Role):
            # 角色玩家序列化，增加name字段
            return {
                'name': get_display_name(p),
                'type': p.player_type.name,
                'role': p.role_type.name if p.role_type else None,
                'alive': p.alive
            }
        elif isinstance(p, dict):
            # 例如AI玩家用model替代名字
            return {
                'name': p.get('nickname', p.get('model', 'unknown')),
                'type': p.get('type', 'AI'),
                'alive': p.get('alive', True)
            }
        else:
            # 其他类型玩家，默认称呼P+序号
            return {
                'name': get_display_name(p),
                'type': 'HUMAN',
                'alive': True
            }

    serialized_players = [serialize_player(p) for p in players]
    return jsonify({'players': serialized_players})


@app.route('/game_status')
def game_status():
    if not app.game_state.game_over:
        # 每次请求时都检查一次游戏是否结束
        game_continue, end_message = check_game_end(
            app.game_state.wolf, app.game_state.god, app.game_state.civil
        )
        if not game_continue:
            app.game_state.game_over = True
            app.system_messages.append(end_message)

            return jsonify({
                "success": True,
                "game_over": True,
                "message": end_message,
                "redirect_url": "/room"  # 告诉前端跳转到 room 页面
            })

    # 如果已经结束了，就继续返回最后信息
    return jsonify({
        "success": True,
        "game_over": app.game_state.game_over,
        "message": app.system_messages[-1] if app.system_messages else "",
        "redirect_url": "/room" if app.game_state.game_over else None
    })


@app.route('/check_status')
def check_status():
    return jsonify({
        "game_over": app.game_state.game_over,
        "message": getattr(app.game_state, 'end_message', '')
    })

@app.route('/night_status')
def night_status():
    alive_human_ids = [p.player_id for p in players if p.player_type == PlayerType.HUMAN and p.alive]
    all_done = app.game_state.night_done.issuperset(alive_human_ids)

    if all_done and app.game_state.ai_done:  # 假设 run_ai_night_actions 会设置 ai_done = True
        return jsonify({'redirect': url_for('room')})
    return jsonify({'status': 'waiting'})

@app.route("/room")
def room_page():
    return render_template("room.html")

if __name__ == '__main__':
    app.run(debug=True)
