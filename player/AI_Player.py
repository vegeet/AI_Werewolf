import requests
import re

model = ["qwen2:7b", "deepseek-r1:7b"]
def generate_speech(prompt, model="qwen2:7b"):
    """
    生成狼人杀中某位玩家的白天发言内容。

    参数:
    - player_name: 玩家名称（如 "P1"）
    - role: 该玩家的角色（如 "狼人", "预言家", "村民"）
    - model: 使用的语言模型（默认为 qwen2:7b）

    返回:
    - 发言内容（字符串）
    """
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
    prompt = "你是预言家，你在玩狼人杀"
    speech = generate_speech(prompt=prompt, model="deepseek-r1:7b")
    print(speech)
