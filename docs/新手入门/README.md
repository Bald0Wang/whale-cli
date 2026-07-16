# 新手入门（按大纲逐章完成版）

本目录是 Whale CLI 的分章讲义。每章对应一个可独立验收的能力模块，并在末尾给出源码位置、测试入口和当前边界。

阅读时请区分四种标签：当前实现、教学简化、扩展练习、生产差距。教程会讲成熟 CLI Agent 的常见结构，但不会把尚未实现的能力写成 Whale CLI 的现成功能。

从 11 章开始是进阶结构篇：它拆开 agents、hooks、subagents、background tasks、skills、plugins、MCP、AGENTS.md 和附件输入等机制。16 章已接入 stdio、Streamable HTTP 和 SSE MCP；OAuth 交互回调、健康检查和连接池仍属于后续扩展。

维护或改写章节时，请使用 [教程小节标准化写作模板](../教程小节标准化写作模板.md)。它规定了章节范围、代码映射、测试、边界和交付检查方式。

## 先选学习路线

| 读者情况 | 建议阅读 | 目标 |
|---|---|---|
| 第一次使用 CLI Agent | 00 -> 01 | 能启动、能观察一次工具调用 |
| 想理解 Agent 核心 | 02 -> 06 | 能追踪会话、模型调用、循环和工具分发 |
| 想完成小型 coding agent | 07 -> 10 | 能维护 Todo、处理长对话并完成可复现 Demo |
| 想构建垂直学习 Agent | 21 -> 27 | 能把领域资料、学习档案、知识结构、复习和项目陪学串成闭环 |

## 阅读顺序

### Part 1：从会用到会做（当前代码已实现）

| # | 文件 | 主题 | 对应代码 |
|---|---|---|---|
| 00 | `00-为什么要做这个CLI.md` | 动机与设计目标 | — |
| 01 | `01-5分钟体验-能帮你做什么.md` | 安装、配置、首次运行 | `ui/shell/main.py` |
| 02 | `02-REPL与会话-把聊天框做成系统.md` | REPL + 会话持久化 | `storage/session_store.py` |
| 03 | `03-最小LLMClient-先打通对话.md` | LLM 客户端与配置 | `llm/client.py` |
| 04 | `04-AgentLoopv0-从聊天到会做事的循环.md` | ReAct 循环 | `soul/soul.py` |
| 05 | `05-Toolsv0-最小工具箱.md` | 只读工具（read/grep/glob） | `tools/file/*` |
| 06 | `06-Toolsv1-写文件与跑命令.md` | 读写工具 + 权限审批 | `tools/file/edit_tool.py`, `soul/approval.py` |
| 07 | `07-TodoList-把计划变成可追踪任务.md` | 任务追踪 | `tools/todo/`, `soul/todo_store.py` |
| 08 | `08-Skills-把套路沉淀成能力包.md` | Skill 发现与索引注入 | `skill/discovery.py` |
| 09 | `09-SessionNote与上下文压缩-稳态系统.md` | 上下文压缩；Session Note 为扩展 | `soul/compaction.py`, `prompts/compact.md` |
| 10 | `10-Part1结尾-Demo清单.md` | 阶段总结与 Demo | — |

### Part 2：Whale CLI 进阶结构篇（教学版已实现）

| # | 文件 | 主题 | Whale CLI 对应代码 |
|---|---|---|---|
| 11 | `11-Agents与系统提示词-把配置从代码里拿出来.md` | agent 规格、system prompt 模板、Runtime | `agents/`, `soul/soul.py` |
| 12 | `12-Hooks-把自动化护栏挂在循环外.md` | hook 事件与扩展点 | `hooks/`, `soul/toolset.py` |
| 13 | `13-Subagents-把复杂任务交给干净上下文.md` | 子 agent、独立上下文、权限冒泡 | `subagents/`, `tools/agent/` |
| 14 | `14-BackgroundTasks-让慢任务后台跑.md` | 后台任务、状态机、输出落盘 | `background/`, `tools/background/` |
| 15 | `15-Skills进阶-按来源分层发现.md` | skills 分层发现与按需加载 | `skill/`, `skills/` |
| 16 | `16-MCP与插件-把外部能力接进工具池.md` | 本地 plugin + MCP transport + 生命周期 | `plugin/`, `mcp/`, `tools/base.py` |
| 17 | `17-AGENTS与项目上下文-让仓库规则自动生效.md` | 项目规则自动注入 | `context/project.py` |
| 18 | `18-进阶收束-WhaleCLI扩展路线.md` | Whale CLI 的能力边界与扩展路线 | 全局结构 |
| 19 | `19-四种Loop模式-让Agent按条件持续工作.md` | 回合、目标、定时、事件四种循环 | `loops/`, `ui/shell/` |
| 20 | `20-附件与文件输入-让多格式资料进入任务.md` | 文件选择、上传管理、摘要注入与格式边界 | `webui/server.py`, `webui/src/App.jsx` |
| 21 | `21-Datawhale学习规划Subagent-用知识库做垂直路线.md` | 本地知识库检索 + Datawhale 项目建议与学习路线 | `subagents/datawhale.py`, `subagents/runner.py` |
| 22 | `22-学习者档案-先知道要帮谁.md` | 本地学习者档案与缺失字段 | `learning/profile.py`, `learning/store.py` |
| 23 | `23-双链知识图谱-把学过的东西连起来.md` | 概念节点、前置关系、Obsidian Wiki 与 WebUI 图谱 | `learning/knowledge.py`, `learning/wiki.py`, `webui/server.py` |
| 24 | `24-动态学习路线-下一步只做一件事.md` | 基于依赖的动态学习路线 | `learning/roadmap.py` |
| 25 | `25-间隔复习-让学过的内容留下来.md` | 本地间隔复习与回忆评分 | `learning/review.py` |
| 26 | `26-项目陪学-从推荐到本地练习.md` | 练习计划、受控克隆与工作区边界 | `learning/projects.py` |
| 27 | `27-学习档案与社区反馈-把进步留下来.md` | 学习证据、报告与贡献草稿 | `learning/portfolio.py` |

## 如何验证每章

Part 1 每章末尾都给出可运行的验证命令。整体上：

```bash
# 单元测试（默认，秒级，不打真实模型）
./.venv/bin/python -m pytest

# 端到端测试（需要 API Key + 网络，约 20 秒）
RUN_E2E=1 ./.venv/bin/python -m pytest tests/test_e2e.py -v
```

建议按章节运行离线测试：03 用 `tests/test_llm_client.py`，04 用 `tests/test_soul_integration.py`，05-06 用 `tests/test_toolset.py` 和 `tests/test_file_tools.py`，07 用 `tests/test_todo.py`，09 用 `tests/test_compaction.py`，11-18 直接使用各章末尾的精确命令。

## 配置 API Key

复制 `config.example.json` 到 `~/.whale/config.json`，填入你的 Step Plan Key：

```json
{
  "llm": {
    "api_key": "你的-step-plan-key",
    "base_url": "https://api.stepfun.com/step_plan/v1",
    "model": "step-3.7-flash",
    "max_context_tokens": 256000,
    "vision_enabled": true,
    "vision_detail": "low"
  }
}
```

或设置环境变量 `STEP_API_KEY`。详见 `03-最小LLMClient.md`。
