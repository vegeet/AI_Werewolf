from enum import Enum
import random

class RoleType(Enum):
    VILLAGER = "Villager"
    WEREWOLF = "Werewolf"
    # 狼枪
    WOLFKING = "WolfKing"
    # 预言家
    SEER = "Seer"
    WITCH = "Witch"
    HUNTER = "Hunter"
    IDIOT = "Idiot"

class PlayerType(Enum):
    HUMAN = "Human"
    AI = "AI"

class Role:
    def __init__(self, player_id, name, model_name, role_type: RoleType, player_type: PlayerType):
        self.player_id = player_id         # 玩家编号
        self.name = name                   # 玩家昵称
        self.role_type = role_type         # 玩家身份
        self.player_type = player_type     # 玩家类型（真人 / AI）
        self.prompt = ""                   # 每个玩家的个性化 prompt，默认为空字符串
        self.alive = True                  # 是否存活
        self.has_voted = False             # 是否投票
        self.is_sheriff = False            # 是否是警长（1.5票）
        self.checked_ids = []              # 记录已查验的玩家ID(预言家专用)
        self.has_used_hunter = False       # 是否使用过技能（猎人专用）
        self.model_name = model_name       # AI玩家的模型名称
        self.antidote = True               # 女巫解药
        self.poison = True                 # 女巫毒药

    def kill(self):
        self.alive = False
        print(f"{self.name} 已死亡，身份是 {self.role_type.value}。")

    def vote(self, candidates):
        # AI 玩家随机选择一个候选人投票
        target = random.choice(candidates)
        self.has_voted = True
        return target  # 返回的是 Role 对象

    def reset_status(self):
        """每个白天或黑夜开始前重置状态"""
        self.has_voted = False

    def __repr__(self):
        return (
            f"<Role name={self.name}, id={self.player_id}, role={self.role_type.value}, "
            f"type={'AI' if self.player_type == PlayerType.AI else 'HUMAN'}, "
            f"model={self.model_name}, alive={self.alive}>"
        )

