# AI_Werewolf
我们制作了一个6人版AI狼人杀，目前是用的本地模型（如deepseek-r1:7b），用api会有更佳体验。
游玩方式：run app.py

项目结构：
Game：
role.py：定义了狼人杀游戏中的角色类（Role）及其相关枚举类型，主要用来保存玩家信息（身份、状态、投票、技能等）与定义 AI 行为（如随机投票）。
Process.py：提供角色建模、角色生成、按身份划分阵营等功能，明确分为夜晚（释放技能）与白天（发言投票），实时检测是否满足游戏结束条件。

player:
AI_Player.py：调用本地模型，根据prompt生成发言。

static：用于存放静态资源
templates：用于存放前端模板文件

app.py:游戏完整流程 包含多种技能的释放、游戏流程的推进、前后端的交互。

AI_Werewolf 
We developed a 6-player version of an AI-powered Werewolf game. It currently uses a local large language model (e.g., deepseek-r1:7b). For a smoother experience, it's recommended to use API-based cloud models.
How to play: Run app.py to start the game.

Project Structure
Game (Game Logic Module)
role.py: Defines the Role class used in the game, along with enums for role types (e.g., Villager, Werewolf) and player types (AI or Human). This file stores player information (identity, status, votes, skills, etc.) and implements basic AI behavior such as random voting.

Process.py: Handles role creation, assignment, and grouping into camps (Werewolves, Special Roles, Villagers). Separates the game flow into night (skill usage) and day (speech and voting) phases, with real-time checks for game-ending conditions.

player (AI Behavior Module)
AI_Player.py: Uses a local language model to generate AI player speeches based on custom prompts.

static (Static Resources)
Stores frontend static files such as CSS, JavaScript, and images.

templates (Frontend Templates)
Contains HTML templates used to render the game interface via the backend.

app.py (Main Application)
The main entry point of the game, integrating the full gameplay flow, skill execution, and frontend-backend interactions. Running this file launches the complete AI Werewolf experience.

