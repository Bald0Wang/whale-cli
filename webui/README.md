# Whale CLI WebUI

基于 React + Vite 的本地工作台，使用 Vaka Chat 的轻量聊天工作区风格，展示 Whale CLI 的聊天、工具调用、审批、workspace 策略与 Agent Loop 轨迹。

```bash
cd webui
npm install
npm run build
cd ..
python webui/server.py
```

打开 `http://127.0.0.1:8765`。

- 没有 API Key 时，可浏览工作台、架构图、学习地图和学习图谱。
- 设置 `STEP_API_KEY`（或配置 `~/.whale/config.json`）后，可从工作台发起真实 Agent 任务。
- `Safe` 模式会在写入或命令工具前显示浏览器审批；`YOLO` 只跳过审批，不会绕过 workspace 路径检查与命令策略。
- 左侧“历史会话”直接读取 CLI 使用的 `.whale_cli/sessions`，选择后会恢复相应消息。
- 顶部设置按钮可在本机切换 API Key、Base URL、模型和上下文预算；接口只返回密钥掩码，不会把原始 Key 发送回页面。
- 按 `/` 或 `Cmd/Ctrl + K` 打开指令面板，可快速新建会话、切换模式、打开设置或填入常用任务。
- 左侧“学习图谱”直接镜像项目内 `KnowledgeMap`，约每 2.5 秒自动刷新；点击节点可即时预览对应的 Obsidian Markdown。使用 `LearningWiki` 同步后，才会将同一份图谱写入 `learning-wiki/` 供 Obsidian 打开或镜像到外部 vault。
- 左侧“学习路线”先显示无写入的路线预览，只有点击“确认生成路线”才会保存 JSON 快照；当前路线的待办项需用户点击“确认已完成”才能更新，历史路线只读。
- 左侧“间隔复习”每天自动检索一次本地会话中已知的知识点，也可手动扫描；复习表保存为 `.whale_cli/learning/review-schedule.json`，网页支持查看到期卡并记录 0-5 回忆评分。

此服务仅监听 `127.0.0.1`，设计目标是本地学习与开发，不是多用户部署服务。

开发时可在两个终端分别运行：

```bash
# 终端 1：Whale API
python webui/server.py

# 终端 2：React 开发服务器（自动代理 /api）
cd webui && npm run dev
```
