from Game.Process import Night_public
from Process import create_role_six, Initialize, check_game_end, Night, Daytime

if __name__ == '__main__':
    # 创建角色（六人版）
    players = create_role_six()

    print("角色创建完成！")
    # 进入流程，初始化
    wolf, god, civil = Initialize(players)  # 分类角色阵营

    day_count = 1  # 初始第一天

    # 判定结束条件
    while check_game_end(wolf, god, civil):
        print("🚩 游戏继续")

        # 夜间行动
        print(f"\n🌙 第 {day_count} 天 - 夜晚")
        Night_public(wolf, god, civil, day_count)
        if check_game_end(wolf, god, civil) == False:
            print("检测到夜间行动结束")
            break

        # 白天行动
        print(f"\n☀️ 第 {day_count} 天 - 白天")
        Daytime(wolf, god, civil, day_count)

        day_count += 1
    print("🎮 游戏结束")

