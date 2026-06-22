from Game.role import Role, RoleType, PlayerType
from Game.skill import Wolf_kill, Seer_pre, Hunter_kill, Witch_act
from Game.step import Vote_banished, Speech_Nbadge
import random

def create_role_six():
    # 六人版：两狼一猎一预两民
    players = [
        Role(1, "P1", "qwen2:7b", RoleType.WEREWOLF, PlayerType.AI),
        Role(2, "P2", "deepseek-r1:7b", RoleType.WEREWOLF, PlayerType.AI),
        Role(3, "P3", "qwen2:7b", RoleType.SEER, PlayerType.AI),
        Role(4, "P4", "deepseek-r1:7b", RoleType.HUNTER, PlayerType.AI),
        Role(5, "P5", "qwen2:7b", RoleType.VILLAGER, PlayerType.AI),
        Role(6, "P6", "deepseek-r1:7b", RoleType.VILLAGER, PlayerType.AI),
    ]

    for player in players:
            prompt_role = f'''\n你现在的玩家名字是{player.name}，不需要说明策略，不需要分析游戏机制，只像在游戏中说话一样表达观点。本局你的身份是{player.role_type}。'''
            base_prompt = '''请根据你的身份，以及推理结果，发言说出你的想法。发言不要透露你身份（除非你是预言家想自爆）。保持逻辑清晰，语气自然。'''
            player.prompt = base_prompt + prompt_role
    return players


# def create_role():
#     role_types = [
#         RoleType.WEREWOLF, RoleType.WEREWOLF,
#         RoleType.SEER,
#         RoleType.HUNTER,
#         RoleType.VILLAGER, RoleType.VILLAGER
#     ]
#     random.shuffle(role_types)
#
#     role_list = []
#     for i in range(6):
#         player_name = f"P{i + 1}"
#         role = Role(
#             player_id=i+1,
#             name=player_name,
#             model_name="",
#             role_type=role_types[i],
#             player_type=None  # 由 index 逻辑填入
#         )
#         role_list.append(role)
#
#     return role_list
def create_role():
    # 定义初始角色池
    role_types = [
        RoleType.WEREWOLF, RoleType.WEREWOLF,
        RoleType.SEER,
        RoleType.HUNTER,
        RoleType.VILLAGER, RoleType.VILLAGER
    ]

    # 移除猎人，打乱剩余角色
    role_types.remove(RoleType.WEREWOLF)
    random.shuffle(role_types)

    # 把猎人插入到第一个位置
    role_types.insert(0, RoleType.WEREWOLF)

    role_list = []
    for i in range(6):
        player_name = f"P{i + 1}"
        role = Role(
            player_id=i + 1,
            name=player_name,
            model_name="",
            role_type=role_types[i],
            player_type=None  # 由 index 逻辑填入
        )
        role_list.append(role)

    return role_list





def Initialize(players):
    wolf = []
    god = []
    civil = []
    # 阵营
    for player in players:
        # 狼阵营
        if player.role_type == RoleType.WEREWOLF or player.role_type == RoleType.WOLFKING:
            wolf.append(player)
        # 神阵营
        elif player.role_type == RoleType.SEER or player.role_type == RoleType.HUNTER or player.role_type == RoleType.WITCH or player.role_type == RoleType.IDIOT:
            god.append(player)
        # 民阵营
        elif player.role_type == RoleType.VILLAGER:
            civil.append(player)

    return wolf, god, civil


def check_game_end(wolf, god, civil):
    # 判断各阵营是否还有存活玩家
    wolf_alive = any(p.alive for p in wolf)
    good_alive = any(p.alive for p in god + civil)  # 所有好人（神+民）

    if not wolf_alive:
        return False, "游戏结束，好人阵营获胜！"
    elif not good_alive:
        return False, "游戏结束，狼人阵营获胜！"
    return True, ""


def Night(wolf, god, civil, day_count):
    # 重置状态 存活
    for p in wolf + god + civil:
        if p.alive:
            p.reset_status()

    # 输入初始信息
    ini_me = False
    if day_count == 1:
        ini_me =True

    # 预言家行动
    Seer_pre(wolf, god, civil, day_count, ini_me)

    # 狼人阵营行动
    print("\n")
    target = Wolf_kill(wolf, god, civil, day_count, ini_me)

    # 女巫行动
    target_list = Witch_act(wolf, god, civil, day_count, target, ini_me)
    return target_list


def Night_public(wolf, god, civil, day_count):
    # 夜间行动
    target_list = Night(wolf, god, civil, day_count)

    if not target_list:
        night_event = f"第{day_count}天夜晚是平安夜，没有人死亡。\n"
        print(night_event)
    else:
        for player in target_list:
            player.kill()
        names = "、".join([p.name for p in target_list])
        night_event = f"第{day_count}天夜晚里，{names}死亡。\n"
        print(night_event)

    for p in wolf + god + civil:
        if p.alive:
            p.prompt += f"\n🕯️ {night_event}"
    return


def Daytime(wolf, god, civil, day_count):
    # 猎人行动
    Hunter_kill(wolf, god, civil, day_count)
    # 狼枪行动
    # 判断游戏结束
    if check_game_end(wolf, god, civil) == False:
        print("检测到夜间行动结束")
        return

    ini = False
    if day_count == 1:
        ini = True

    # 轮番发言
    Speech_Nbadge(wolf, god, civil, day_count, ini)

    # 开始投票
    banished = Vote_banished(wolf, god, civil, day_count)

    for p in god:
        if p.role_type == RoleType.SEER:
            print(f"\n预言家的prompt：{p.prompt}\n")
    return