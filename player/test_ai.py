import re

stdout_example = """action selected by online agent: 在这场游戏中，我们的目标是找出狼人并保护好人。根据当前局势，我们可以从以下几个方面进行分析：

1. P1 表示自己是好人，这是一个正面信息。但我们仍需要谨慎，因为他可能是狼人的诱饵。
2. P2 的信息出现了问题，这可能是因为服务器错误。我们应该关注这个问题，并在适当的时候采取行动。
3. P3 表示自己是猎人，他的目标是帮助好人阵营。这是一个积极的信息，我们可以相互支持。

在这个阶段，我们应该关注以下几点：

1. 观察 P1 的行为，看是否有狼人的嫌疑。
2. 关注 P2 的信息，并寻求其他玩家的帮助解决服务器错误。
3. 与 P3 合作，共同保护好人。

我是预言家，我的目标是查验玩家的身份并引导好人阵营。我们需要密切关注每个玩家的行为，并在适当的时候采取行动。   time taken: 0.041600942611694336"""

# 匹配 "action selected by online agent: " 后面到 "   time taken:" 之前的所有字符（包括换行符）
match = re.search(r"action selected by online agent: (.*?)[\s]*time taken:", stdout_example, re.DOTALL)

if match:
    best_action = match.group(1).strip()
    print(f"成功解析到 best_action: {best_action}")
else:
    print("错误: 未能在脚本输出中找到 'action selected by online agent'。")