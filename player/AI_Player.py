import requests
import re
import json  # 确保导入json库，因为scope的请求体需要用到

# 定义你的模型列表
models = ["qwen2:7b", "deepseek-r1:7b", "scope"]

def generate_speech(prompt: str, model: str = "qwen2:7b") -> str:
    """
    生成狼人杀中某位玩家的白天发言内容，根据模型选择不同的API。

    参数:
    - prompt: 玩家发言的提示词内容。
    - model: 使用的语言模型（默认为 qwen2:7b，可选 deepseek-r1:7b, scope）。

    返回:
    - 发言内容（字符串）
    """
    if model == "scope":
        SCOPE_API_URL = "http://localhost:8000/get_best_action_from_script/"
        # --- 调用 scope API 的逻辑 ---
        print(f"检测到模型为 'scope'，正在调用远程 API: {SCOPE_API_URL}")
        headers = {"Content-Type": "application/json"}
        data = {"prompt": prompt}

        try:
            # 增加超时时间，因为远程 MCTS 可能需要更长时间
            response = requests.post(SCOPE_API_URL, headers=headers, json=data, timeout=300)
            response.raise_for_status()  # 如果状态码不是 2xx，则抛出 HTTPError

            result = response.json()
            best_action = result.get("best_action", "").strip()

            if best_action:
                print(f"Scope API 返回的 Best Action: {best_action}")
                return best_action
            else:
                return "Scope API 没有生成有效的行动。"

        except requests.exceptions.Timeout:
            return "Scope API 请求超时。API 响应时间过长。"
        except requests.exceptions.ConnectionError:
            return "Scope API 连接错误。请确保远程 FastAPI 服务器正在运行，并且防火墙和安全组已正确配置，以及 IP 地址正确。"
        except requests.exceptions.HTTPError as http_err:
            return f"Scope API HTTP 错误发生: {http_err} - {response.text}"
        except requests.exceptions.RequestException as e:
            return f"Scope API 请求发生未知错误: {str(e)}"
        except json.JSONDecodeError:
            return f"Scope API 无法解析 JSON 响应: {response.text}"

    else:
        # --- 调用 Ollama API 的原有逻辑（qwen2:7b, deepseek-r1:7b）---
        print(f"检测到模型为 '{model}'，正在调用本地 Ollama API。")
        url = "http://127.0.0.1:11434/api/generate"

        data = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(url, json=data)
            if response.status_code == 200:
                result = response.json()
                raw_text = result.get("response", "").strip()
                # 🔍 去除 <think>...</think> 区域（适用于 deepseek-r1）
                raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL)

                if raw_text:
                    clean_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
                    return "\n".join(clean_lines)
                else:
                    return "模型没有生成有效的回答。"
            else:
                return f"请求失败，状态码：{response.status_code}"
        except requests.exceptions.RequestException as e:
            return f"请求错误：{str(e)}"


if __name__ == "__main__":
    # 示例用法
    prompt_common = "你是预言家，你在玩狼人杀，请发言，说明你的验人结果。"
    prompt_scope = '''你现在在玩狼人杀游戏，请完全代入你的角色。此模式共有六个玩家，包括两头狼、一个预言家、一个猎人、两个村民。你是一个预言家。你的目标是每晚查验一名玩家的身份，并根据查验结果引导好人阵营。你需要警惕狼人对你的攻击。在白天，你可以公布查验结果，但要小心狼人的反预言家操作。你的身份是【预言家】。--- 当前游戏状态 ---**天数**：第2天**阶段**：发言阶段**存活玩家**：P1、P2、P4、P5、P6**你的角色名**：P6--- 历史信息 (最新10条) ---1. P1 说：我们全部都知道P5是一个狼人；2. P2 说：大家好，我是P2。在这场游戏中，我们有两头狼、一个预言家、一个猎人、两个村民。我们目前的存活玩家有P1、P2、P4、P5、P6。我们需要分析局势，猜测其他玩家的身份或隐瞒自己的真实身份。

首先，我们需要关注P5，因为他已经被认为是一个狼人。我们应该尽量与他保持距离，避免被他捉弄。同时，我们也需要关注P1，因为他可能是预言家，可能会对我们的身份产生疑虑。

关于自己的身份，我只能说我会尽我所能为团队服务。我们需要保持冷静，分析情况，并与其他狼人配合，共同达到目标。让我们在这场游戏中展示出我们的智慧和团队精神。；3. P4 说：P4: 大家好，我是P4。我们需要保持冷静，分析局势，并尽可能地隐藏自己的身份。让我们开始分析其他玩家的行为和言论，找出可能是狼人的人。同时，我们也要注意自己的言论和行为，避免泄露自己的身份。；4. P5 说：我是猎人，我的目标是帮助好人阵营。在发言时，我需要根据场上情况判断谁是好人，谁是狼人，并在关键时刻使用我的技能。我的身份是P5。；--- 你的额外角色信息 ---你的历史查验记录如下：你曾查验玩家P2，TA是狼人。请汇报你的查验结果，通过其他人的反应找出狼人。--- 行动指令 ---请你以**玩家P6的身份**进行发言。你的发言应包含对当前场上局势的分析，可以猜测其他玩家身份或隐瞒自己的真实身份。**重要提示：** - 发言字数请限制在**100字以内**。请立即开始你的发言。你的发言是**对局势的分析、对他人的猜测或为自己辩解**，而不是对指令的回复或提问。你的发言：'''

    # # --- 测试 deepseek-r1:7b (Ollama) ---
    # print("\n--- 测试 deepseek-r1:7b ---")
    # speech_deepseek = generate_speech(prompt=prompt_common, model="deepseek-r1:7b")
    # print(speech_deepseek)
    #
    # # --- 测试 qwen2:7b (Ollama) ---
    # print("\n--- 测试 qwen2:7b ---")
    # speech_qwen = generate_speech(prompt=prompt_common, model="qwen2:7b")
    # print(speech_qwen)

    # --- 测试 scope API ---
    # !!!重要!!! 请替换 SCOPE_API_URL 中的 YOUR_SERVER_PUBLIC_IP 为你的实际IP或域名
    print("\n--- 测试 scope ---")
    speech_scope = generate_speech(prompt=prompt_scope, model="scope")
    print(speech_scope)
