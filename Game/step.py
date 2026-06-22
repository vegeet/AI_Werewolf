from collections import defaultdict
from Game.role import RoleType, PlayerType
import random
from Game.skill import Hunter_kill
from player.AI_Player import generate_speech
import re


def extract_vote_player(ai_response, player_names):
    discard_keywords = ["弃票", "弃权", "不投票", "放弃投票", "没有投票", "选择弃票"]
    if any(keyword in ai_response for keyword in discard_keywords):
        return None

    for player in player_names:
        name = player.name
        pattern = rf"(投票给|投给|投)[^\n]*({name})"
        if re.search(pattern, ai_response):
            return player
    return None


def Vote_banished(wolf, god, civil, day_count):
    print("🗳️ 进入白天投票阶段...")

    def conduct_vote(round_num, Candidates, alive_players, day_count):
        print(f"\n📢 第 {round_num} 轮投票开始：")
        vote_result = defaultdict(int)
        vote_log = []  # 记录每一票，用于最终输出

        for voter in alive_players:
            candidates = [p for p in Candidates if p != voter and p.alive]
            if not candidates:
                continue

            candidates_name = '、'.join([p.name for p in candidates])
            if voter.player_type == PlayerType.HUMAN:
                print(f"\n候选人名单：{candidates_name}")
                while True:
                    vote_name = input(f"{voter.name}（你）请投票，若弃票，请输入“弃票”；或在名单中挑选玩家 {candidates_name} 输入玩家名称（如 P1）进行投票：").strip()
                    if vote_name == "弃票":
                        vote_log.append(f"{voter.name} 弃票")
                        print(f"{voter.name} 弃票")
                        break
                    selected = next((p for p in candidates if p.name == vote_name), None)
                    if selected:
                        vote_result[selected] += 1
                        vote_log.append(f"{voter.name} 投票给了 {selected.name}")
                        print(f"{voter.name} 投票给了 {selected.name}")
                        break
                    else:
                        print("❌ 输入不合法，请重新输入。")
            else:
                # AI生成发言并投票
                ai_statement = generate_speech(voter.prompt + f"现在你需要投票，请在名单中挑选玩家名单： {candidates_name}，也可以选择弃票。必须输出 我投票给xx或者我弃票",
                                               model=voter.model_name)

                selected = extract_vote_player(ai_statement, candidates)
                if selected:
                    vote_result[selected] += 1
                    vote_log.append(f"{voter.name} 投票给了 {selected.name}")
                    print(f"{voter.name} 说：{ai_statement}")
                    print(f"{voter.name} 投票给了 {selected.name}")
                else:
                    vote_log.append(f"{voter.name} 弃票")
                    print(f"{voter.name}弃票")
                    print(f"AI发言：{ai_statement}")

        vote_summary = f"\n📊 第 {day_count} 个白天第 {round_num} 轮投票结果：\n"
        for line in vote_log:
            vote_summary += line + "\n"

        if not vote_result:
            result_msg = "⚠️ 所有人都弃票，无人被放逐。\n"
            vote_summary += result_msg
            # 写入每位玩家 prompt
            for p in alive_players:
                p.prompt += vote_summary
            return None, 0

        max_votes = max(vote_result.values())
        top_voted = [p for p, v in vote_result.items() if v == max_votes]

        if len(top_voted) == 1:
            result_msg = f"✅ {top_voted[0].name} 获得最高票（{max_votes} 票），将被放逐。\n"
        else:
            tied_names = "、".join([p.name for p in top_voted])
            result_msg = f"⚖️ 出现平票！{tied_names} 获得最高票（{max_votes} 票），请进行下一轮投票。\n"

        vote_summary += result_msg

        # 将结果加入所有玩家的 prompt 中
        for p in alive_players:
            p.prompt += vote_summary

        return top_voted

    alive_players = [p for p in wolf + god + civil if p.alive]
    Candidates = [p for p in wolf + god + civil if p.alive]
    # 第一轮投票
    top_voted = conduct_vote(round_num=1, Candidates = Candidates,
                             alive_players = alive_players, day_count = day_count)

    if len(top_voted) == 1:
        # 有明确被放逐者
        target = top_voted[0]
        print(f"🪦 {target.name} 被投票放逐出局！")
        banished_act(target, wolf, god, civil, day_count)
    elif top_voted == None:
        print("没有有效票，今日无放逐玩家")
    else:
        print("⚖️ 票数相同，进入第二轮投票...")
        # 第二轮投票（只在平票者中投）
        Candidates = top_voted
        second_voted = conduct_vote(round_num=2, Candidates = Candidates,
                                    alive_players = alive_players, day_count=day_count)

        if len(second_voted) == 1:
            target = second_voted[0]
            print(f"🪦 {target.name} 在第二轮投票中被放逐！")
            banished_act(target, wolf, god, civil, day_count)
        else:
            print("❌ 第二轮仍然平票，今天无放逐。")
    return


def banished_act(banished, wolf, god, civil, day_count):
    # 被投票者说遗言或者发动技能（白痴、猎人、狼枪）
    print("等待被放逐的玩家发动技能")
    # 判断身份
    # 标志：是否继续存活（白痴用）
    survived = False

    if banished.role_type == RoleType.HUNTER:
        print(f"🎯 {banished.name} 是猎人，死亡前可以带走一个人！")
        Hunter_kill(wolf, god, civil, day_count)

    elif banished.role_type == RoleType.WOLFKING:
        print(f"🐺 {banished.name} 是狼王，死亡时可以带走一个人！")
        Hunter_kill(wolf, god, civil, day_count)  # 可复用猎人技能

    # 白痴技能待完善
    elif banished.role_type == RoleType.IDIOT:
        if not getattr(banished, 'idiot_used', False):
            print(f"🛡️ {banished.name} 是白痴，首次放逐免死！")
            banished.idiot_used = True
            survived = True
            banished.can_vote = False  # 白痴不能再投票
        else:
            print(f"⚰️ {banished.name} 是白痴，已失去免死权，出局！")
            banished.kill()

    # 普通人或非免死角色直接死亡
    if not survived:
        banished.kill()

    # 说遗言（AI or 玩家输入）
    print(f"\n📝 {banished.name} 的遗言：")
    if banished.player_type == PlayerType.AI:
        print(f"{banished.name}（AI）：我真的是好人，你们投错人了！")
    else:
        input_text = input(f"{banished.name}（你）请输入遗言：")
        print(f"{banished.name}（你）：{input_text}")
    return


def Speech_Nbadge(wolf, god, civil, day_count, ini):
    # 无警徽发言版
    # 随机抽取活着的人作为发言人
    # 获取所有存活玩家，并按 player_id 排序

    alive_players = [p for p in wolf + god + civil if p.alive]
    alive_players.sort(key=lambda x: x.player_id)

    if ini:
        for p in alive_players:
            if p.role_type == RoleType.VILLAGER:
                p.prompt += '''你是普通村民，没有特殊技能。你需要通过发言、投票、死亡情况等间接信息判断谁可能是狼人，并尽量投票处决狼人，保护好人阵营。留意那些发言模糊或行为异常的玩家。\n'''
            elif p.role_type == RoleType.HUNTER:
                p.prompt += '''你是猎人，若你被投票处决或夜间被杀，可带走一名玩家。投票时请谨慎思考，避免误伤好人，并观察哪些玩家可能是狼人队伍的一员，以备不测之需。\n'''

    c_prompt = f"现在是第{day_count}天白天发言阶段，请根据当前局势发言并分析，尽量不要透露自己的身份，并尽力说服其他玩家认同自己的观点。\n"
    for p in alive_players:
        p.prompt += c_prompt


    # 随机选择一个发言起点
    start_player = random.choice(alive_players)
    start_index = alive_players.index(start_player)

    print(f"\n🎤 从 {start_player.name} 开始发言：")

    n = 0

    # 顺序发言，从 start_index 到末尾，再从头发言到 start_index-1
    for i in range(len(alive_players)):
        current_index = (start_index + i) % len(alive_players)
        player = alive_players[current_index]

        if player.player_type == PlayerType.AI:
            result = generate_speech(player.prompt, model=player.model_name)
            print(f"第{day_count}天白天发言，{player.name}说：{result}")
            speech_text = result
        else:
            input_text = input(f"{player.name}（你）发言，请输入：")
            print(f"第{day_count}天白天发言，{player.name}说：{input_text}")
            speech_text = input_text


        # 💬 将发言同步到所有其他存活玩家的 prompt
        for p in alive_players:
            if p != player:
                p.prompt += f"{player.name} 说：{speech_text}"
                if n == 0:
                    n += 1
                    print(p.prompt)

    print("🗣️ 所有玩家发言完毕。下面进入投票环节\n")
    return