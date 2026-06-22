import random
from collections import Counter
from Game.role import RoleType, Role, PlayerType
from player.AI_Player import generate_speech
import re


def extract_kill_player(ai_response, player_names):
    for player in player_names:
        name = player.name
        pattern = rf"我希望杀掉{name}"
        if re.search(pattern, ai_response):
            return name
    return None


def Wolf_kill(wolf, god, civil, day_count, join_team):
    # 提示词中加入狼队的所有人
    if join_team:
        wolf_names = "、".join([w.name for w in wolf if w.alive])
        for w in wolf:
            w.prompt += f'''作为狼人，您的队伍有{wolf_names}（包括你自己），你的目标是存活到最后并消灭其他好人阵营。请结合同伴的发言、现状和潜在威胁，引导舆论，合理安排投票对象，伪装成好人，投给你认为有可能带来威胁的玩家。请注意，在白天发言阶段，请不要轻易透露身份。'''

    # 所有存活角色
    potential_targets = [p for p in god + civil + wolf if p.alive]

    # 每个狼人投票
    votes = []
    candidate_names = "、".join([p.name for p in potential_targets])
    for w in wolf:
        if w.alive:
            if w.player_type == PlayerType.AI:
                print("AI狼人开始投票")
                choose_prompt = w.prompt + f"\n现在是第{day_count}天夜晚，你需要杀死场上的玩家，必须在以下目标中选择其中一个：{candidate_names}。最终你必须输出“我希望杀掉XX。”然后输出你的选择理由"
                result = generate_speech(choose_prompt, model=w.model_name)
                print(f"本结果由{w.model_name}生成\n", result)
                target_name = extract_kill_player(result, potential_targets)
                if not target_name:
                    print("未能提取到类似的查验目标，随机选择")
                    target = random.choice(potential_targets)
                    votes.append(target.player_id)
                else:
                    target = next((p for p in potential_targets if p.name == target_name), random.choice(potential_targets))
                    votes.append(target.player_id)
                print(f"🐺 {w.name} 投票要杀 {target.name}")
            elif w.player_type == PlayerType.HUMAN:
                print(f"\n现在是第{day_count}天夜晚，你需要杀死场上的玩家，必须在以下目标中选择其中一个：{candidate_names}。")
                while True:
                    target_name = input("请输入你要预言的玩家名字（如 P1）：").strip()
                    if target_name in potential_targets:
                        break
                    else:
                        print("❌ 输入不在目标池中，请重新输入！")
                    # 根据输入选择玩家对象
                target = next(p for p in potential_targets if p.name == target_name)
                votes.append(target.player_id)
                print(f"🐺 {w.name} 投票要杀 {target.name}")

    # 统计票数
    vote_count = Counter(votes)

    # 找出票数最多的玩家 ID（若平票随机选择）
    max_votes = vote_count.most_common()
    top_vote = max_votes[0][1]
    top_targets = [pid for pid, v in max_votes if v == top_vote]
    chosen_id = random.choice(top_targets)

    # 查找目标对象 允许自刀
    chosen_target = next((p for p in god + civil + wolf if p.player_id == chosen_id), None)

    print(f"今晚，玩家{chosen_target.name}被杀")

    # 将刀人信息加入所有存活狼人玩家的 prompt
    for w in wolf:
        if w.alive:
            w.prompt += f"\n🗡️ 第{day_count}天夜晚，你们选择了刀掉 {chosen_target.name}。"
    return chosen_target


def extract_predict_player(ai_response, player_names):
    for player in player_names:
        # 在文本中查找类似 “查验 P2” 或 “选择了 P2” 的表达
        name = player.name
        pattern = rf"(查验|选择|查看|锁定)[^\n]*({name})"
        if re.search(pattern, ai_response):
            return name
    return None


def Seer_pre(wolf, god, civil, day_count, ini_message):
    print("🔮 预言家开始查验...")

    # 找到预言家对象
    seers = [p for p in god if p.role_type == RoleType.SEER and p.alive]
    if not seers:
        print("预言家已死亡，无法查验。")
        return

    seer = seers[0]
    if ini_message:
        ini = (
            "你扮演的角色是预言家（Seer），你的任务是查验并识别出狼人并引导村民投票将其处决。"
            "结合你查验过的玩家身份、昨晚的查验结果、他人的发言表现和投票行为，推断谁可能是狼人，投票给你认为最可疑的玩家。保护好好人阵营。"
            "请注意：你的目标是带领好人阵营获胜，狼人会试图迷惑其他玩家甚至杀害你。"
            "你要时刻谨慎思考，保护好自己，发挥查验能力，隐藏身份，引导投票。"
        )
        seer.prompt += ini

    # 目标池：所有活着的玩家，排除自己，且未查验过
    others = [
        p for p in wolf + god + civil
        if p.alive and p != seer and p.player_id not in seer.checked_ids
    ]

    if not others:
        print("无可查验目标。")
        if seer.player_type == PlayerType.AI:
            seer.prompt += f"\n第{day_count}天夜晚，无可查验目标。"

    candidate_names = "、".join([p.name for p in others])

    if seer.player_type == PlayerType.AI:
        print("AI预言家开始预言")
        choose_prompt = seer.prompt + f"\n现在是第{day_count}天夜晚，你需要查验玩家身份，必须在以下目标中选择其中一个：{candidate_names}。最终你必须输出“我希望查验XX。”然后输出你的选择理由"
        result = generate_speech(choose_prompt, model = seer.model_name)
        print(f"本结果由{seer.model_name}生成\n", result)
        target_name = extract_predict_player(result, others)
        if not target_name:
            print("未能提取到类似的查验目标，随机选择")
            target = random.choice(others)
        else:
            target = next((p for p in others if p.name == target_name), random.choice(others))

    elif seer.player_type == PlayerType.HUMAN:
        print(f"现在是第{day_count}天夜晚，你需要查验玩家身份，请在以下目标中选择：{candidate_names}")
        while True:
            target_name = input("请输入你要预言的玩家名字（如 P1）：").strip()
            if target_name in others:
                break
            else:
                print("❌ 输入不在目标池中，请重新输入！")
        target = next(p for p in others if p.name == target_name)
    print(f"🔍 预言家 {seer.name} 查验了 {target.name}")

    seer.checked_ids.append(target.player_id)

    # 返回查验结果
    if target.role_type in [RoleType.WEREWOLF, RoleType.WOLFKING]:
        result = "狼人"
    else:
        result = "好人"

    print(f"🔎 查验结果：{target.name} 是 {result}")

    seer.prompt += f"\n第{day_count}天夜晚，你查验了 {target.name}，他的身份是：{result}"
    return


def Hunter_kill(wolf, god, civil, day_count):
    for hunter in god:
        if hunter.role_type == RoleType.HUNTER and not hunter.alive and not hunter.has_used_hunter:
            print(f"🏹 猎人 {hunter.name} 死亡，准备发动技能...")

            # 随机选择一个目标反杀（不包括自己、只杀活人）
            all_others = [p for p in wolf + god + civil if p.alive and p != hunter]
            if not all_others:
                print("没有可供反杀的目标。")
                return

            candidate_names = "、".join([p.name for p in all_others])
            if hunter.player_type == PlayerType.AI:
                print("AI猎人开始行动")
                choose_prompt = hunter.prompt + f"\n现在是第{day_count}天白天，你已死亡，你可以选择是否枪杀一名玩家，请在以下名单中选择：{candidate_names}。若不想使用枪，请说“不使用”。你必须说出：我希望杀掉XX 或 不使用。"
                result = generate_speech(choose_prompt, model=hunter.model_name)
                print(f"本结果由{hunter.model_name}生成\n", result)
                target_name = extract_predict_player(result, all_others)
                if not target_name:
                    print("未能提取到类似的查验目标，不发动技能")
                else:
                    target = next((p for p in all_others if p.name == target_name), random.choice(all_others))
                    print(f"💥 猎人带走了 {target.name}！")
                    target.kill()

            elif hunter.player_type == PlayerType.HUMAN:
                print(f"现在是第{day_count}天白天，你已死亡，作为猎人，请结合之前的所有信息，在名单{candidate_names}中杀死你认为的狼人玩家；如果不确定谁是狼人，也可以不发动技能，并输入“不发动”")
                while True:
                    target_name = input("请输入你要杀死的玩家名字（如 P1），或输入“不发动”：").strip()

                    if target_name == "不发动":
                        print("你选择了不发动技能。")

                    if any(p.name == target_name for p in all_others):
                        target = next(p for p in all_others if p.name == target_name)
                        print(f"💥 猎人带走了 {target.name}！")
                        target.kill()
                    else:
                        print(f"输入无效，'{target_name}' 不在候选名单中。请重新输入。")
            # 标记猎人已使用技能
            hunter.has_used_hunter = True
    return


def Witch_act(wolf, god, civil, day_count, target, ini):
    # 死亡列表
    target_list = []
    target_list.append(target)

    # 找出活着的女巫
    witches = [p for p in god if p.role_type == RoleType.WITCH and p.alive]
    if not witches:
        print("女巫已死亡，无法行动。")
        return target_list

    witch = witches[0]
    print(f"🧙‍♀️ 女巫行动阶段")

    # 女巫有解药且目标非女巫
    if target and witch.antidote and target != witch:
        print(f"第{day_count}晚，狼人想杀死的是：{target.name}")
        choice = input(f"你要救 {target.name} 吗？输入 y/n：").strip().lower()
        if choice == "y":
            print(f"🧪 女巫使用了解药，救回了 {target.name}！")
            witch.antidote = False
            # 今晚是平安夜, 清空目标
            target_list = []
            return target_list
        else:
            print("女巫选择不使用解药。")
            poison_P = Witch_act_poison(wolf, god, civil, day_count, witch, target)
            if poison_P:
                target_list.append(poison_P)
            return target_list
    # 女巫有解药但是目标是女巫
    elif target and witch.antidote and target == witch:
        print(f"第{day_count}狼人想杀死的是：{target.name}")
        print("你无法自救")
        poison_P = Witch_act_poison(wolf, god, civil, day_count, witch, target)
        if poison_P:
            target_list.append(poison_P)
        return target_list
    # 女巫无解药，但是有毒药
    elif not witch.antidote and witch.poison:
        poison_P =Witch_act_poison(wolf, god, civil, day_count, witch, target)
        if poison_P:
            target_list.append(poison_P)
        return target_list
    else:
        print("你没有可用的药")
        return target_list

def Witch_act_poison(wolf, god, civil, day_count, witch, target):
    all_others = [p for p in wolf + god + civil if p != witch and p.alive]
    target_poison = False  # 默认不毒杀

    if not all_others:
        print("无可毒杀目标。")
        return target_poison

    candidate_names = "、".join([p.name for p in all_others])
    if witch.player_type == PlayerType.HUMAN:
        # 人类玩家交互输入
        while True:
            choice = input(f"你要毒杀谁？以下是活人名单：{candidate_names}（输入名字如 P3，或输入“不使用”）：").strip()

            if choice.lower() == "不使用":
                print("女巫没有使用毒药。")
                target_poison = False
                break  # 合法输入，退出循环

            # 查找目标是否在名单中
            target_poison = next((p for p in all_others if p.name == choice), None)
            if target_poison:
                print(f"💀 女巫使用毒药毒死了 {target_poison.name}！")
                target_poison.alive = False
                witch.poison = False
                break  # 合法输入，退出循环
            else:
                print("❌ 输入不合法，请重新输入！")

    elif witch.player_type == PlayerType.AI:
        print("🤖 AI女巫开始判断是否使用毒药...")
        # 构造 prompt 让 AI 女巫选择目标
        poison_prompt = witch.prompt + f"\n现在是第{day_count}天夜晚，你可以选择是否毒杀一名玩家，请在以下名单中选择：{candidate_names}。若不想使用毒药，请说“不使用”。你必须说出：我想毒杀XX 或 不使用。"

        ai_output = generate_speech(poison_prompt, model=witch.model_name)
        print(f"本结果由{witch.model_name}生成：\n{ai_output}")

        extracted_name = extract_kill_player(ai_output, [p.name for p in all_others])
        if extracted_name and extracted_name.lower() != "不使用":
            target_poison = next((p for p in all_others if p.name == extracted_name), None)
            if target_poison:
                print(f"💀 AI女巫使用毒药毒死了 {target_poison.name}！")
                target_poison.alive = False
                witch.poison = False
        else:
            print("AI女巫没有使用毒药。")
            target_poison = False

    return target_poison