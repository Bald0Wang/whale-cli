# 18. 进阶收束：Whale CLI 扩展路线

本章导航：

- 新增机制：没有新增运行时模块；把现有能力、边界和下一步工程顺序放在同一张路线图中。
- 正式入口：本章回看 `src/whale_cli/` 各模块与 `tests/`。
- 验证方式：`./.venv/bin/python -m pytest -q`；真实模型测试需显式设置 `RUN_E2E=1`。
- 本章不展开：不会把路线图中的生产差距伪装成当前功能。

到这里，Whale CLI 的教程已经不只是“能跑一个 agent loop”。

它有两层：

- Part 1：把最小 CLI Agent 跑起来
- Part 2：理解成熟的生产级参考实现为什么需要 agents、hooks、subagents、background、skills、plugins、AGENTS.md 和不同的 Loop 模式

这一章把两层收束起来。

## 全局架构回顾

![Whale CLI 整体架构](images/whale-cli-architecture.svg)

---

## Whale CLI 的边界

Whale CLI 不应该变成一个小号生产级参考实现。

它的目标是教学：

- 每个模块能单独读懂
- 每个机制能单独验证
- 不为了生产完整性牺牲可读性
- 代码量控制在新手能通读的范围内

所以有些东西应该刻意简化。

## 结构对照

下表描述的是当前代码，不是待办清单。“生产差距”表示继续工程化时才需要补的能力。

| 能力 | Whale CLI 当前教学实现 | 生产差距 |
|---|---|---|
| Agent loop | `Soul.run()` 负责一轮模型/工具闭环；`LoopManager` 提供回合、目标、定时、事件四种模式 | async step/turn 生命周期、并发调度、恢复策略、观测指标 |
| LLM | OpenAI 兼容客户端；支持环境变量、配置文件、model/base_url 覆盖 | 多 provider capability、retry、限流、流式与成本追踪 |
| Toolset | Python `Tool` 注册表，内置工具、本地 plugin 和 MCP（stdio / HTTP / SSE）都进入同一个 Toolset | 远端工具连接池、健康检查与并发调度 |
| Approval | 同步 ask / 会话内批准 / yolo；后台循环在 safe 模式下拒绝危险工具 | 细粒度策略、权限冒泡、审计记录、afk 规则 |
| Todo | `TodoWrite` 整体替换当前 Soul 内存清单 | 持久化、恢复、依赖图、状态注入 |
| Compaction | 字符估算、LLM 摘要、保留 system 和最近消息 | 多层 compact、精确 token、错误恢复、独立 Session Note |
| Agent config | `agent.yaml` + `system.md` + `AgentSpec` 已实现 | 多 agent type、热更新、完整 YAML 校验 |
| Hooks | 同步 callback engine、标准事件 payload、allow/block/append | matcher、timeout、外部/wire hook、配置加载 |
| Skills | project/user/builtin 多来源发现、去重、索引注入 | 模型可调用的按需全文加载、flow skill、插件 skill |
| Subagents | 前台干净上下文；explore/coder 两类工具集 | background、resume、持久化 store、并行团队 |
| Background | daemon thread + Bash 进程、JSON 状态和输出文件 | worker 进程、heartbeat、chunk streaming、重启接管 |
| MCP | stdio / HTTP / SSE 配置、工具发现、schema 适配、tools/call、标准错误转换和 Soul 生命周期关闭 | OAuth 交互回调、deferred loading、健康检查、重连与连接池 |
| Project context | `AGENTS.md` root-to-leaf 合并，leaf-first 预算 | 热刷新、多格式规则、冲突诊断 |

## 接下来最值得实现的 5 步

已有教学模块不需要重复实现。若要继续把 Whale CLI 往生产可用方向推进，建议按这个顺序：

1. **WorkspaceSandbox**
   统一校验文件路径和 Bash 工作目录。先解决“审批不等于隔离”的问题。

2. **持久化 Todo 与 Session Note**
   让任务状态和关键决策能随会话恢复，并为 SessionStore 补独立回归测试。

3. **LLM 可靠性层**
   为 provider 能力、超时、retry 和错误分类建立明确接口，保持 `Soul` 不依赖具体模型服务。

4. **MCP 生命周期与 transport 扩展**
   三种 MCP transport 已经可用；下一步补 OAuth 交互回调、健康检查、重连和连接池。

5. **持久化调度与 worker**
   把定时/事件 Loop 从进程内线程升级为可恢复任务，并补 heartbeat、日志分块和取消语义。

这 5 步都建立在当前教学版模块之上，不会推翻已经讲清的主循环。

## 不建议立刻做的东西

这些不是不重要，而是不适合作为下一步：

- 完整 MCP transport
- OAuth
- 多 UI wire protocol
- 后台 worker 进程
- subagent resume
- 插件市场
- 多后端文件系统

它们都很有价值，但会把教学主线打散。

## 最后记住一句话

Whale CLI 的核心不是“复制生产级参考实现”。

它应该回答一个更基础的问题：

```text
一个能干活的 CLI Agent，最小可理解结构是什么？
```

而生产级参考实现回答的是另一个问题：

```text
一个面向真实用户、真实仓库、真实长任务的 CLI Agent，
需要哪些生产级 harness 机制？
```

两者不是竞争关系。

Whale CLI 是显微镜，生产级参考实现是完整机器。先用显微镜看清每个零件，再去理解机器为什么这样运转。

---

## 本章模块化代码

最后把 11-17 章新增模块放到一张代码地图里。读源码时按这个顺序走，不容易迷路。

```text
src/whale_cli/
├── agents/
│   ├── default/agent.yaml     # 默认 agent 可用工具
│   ├── default/system.md      # system prompt 模板
│   └── loader.py              # AgentSpec + render_system_prompt
├── hooks/
│   ├── engine.py              # HookEngine / HookResult
│   └── events.py              # PreToolUse / PostToolUse / Compact payload
├── subagents/
│   └── runner.py              # child Soul，干净上下文
├── background/
│   ├── manager.py             # 后台 bash 线程
│   ├── models.py              # TaskSpec / TaskRuntime
│   └── store.py               # 任务状态与输出落盘
├── skill/
│   ├── models.py              # Skill / SkillRoot
│   └── discovery.py           # project > user > builtin
├── plugin/
│   └── loader.py              # plugin.json → Tool 实例
├── mcp/
│   ├── loader.py              # mcpServers 配置、发现与生命周期
│   ├── client.py              # stdio / HTTP / SSE transport
│   └── adapter.py             # 远端工具 → 本地 Tool
├── loops/
│   ├── models.py              # LoopMode / LoopOutcome / LoopRecord
│   └── manager.py             # 回合、目标、定时、事件循环
└── context/
    └── project.py             # AGENTS.md root→leaf 合并
```

最终这些模块都在 `Soul` 里汇合：

```python
class Soul:
    def __init__(self, ...):
        self.llm = llm or LLMClient()
        self.todos = TodoStore()
        self.approval = approval or Approval()
        self.hooks = hook_engine or HookEngine()
        self.background = background or BackgroundTaskManager()
        self._mcp_lifecycle = MCPLifecycle()

        default_tools, self._mcp_lifecycle = _default_tools(
            self.todos, self.llm, self.approval, self.background
        )
        self.toolset = Toolset(default_tools, hook_engine=self.hooks, session_id=session_id, cwd=os.getcwd())
        self.toolset.set_approver(self.approval.as_approver())
        self.messages = [{"role": "system", "content": self._build_system_prompt(...)}]

    def close(self) -> None:
        self._mcp_lifecycle.close()
```

这个片段省略了 `tools` 自定义注入分支和 session 恢复。需要注意的是：默认工具池现在返回“工具列表 + MCP lifecycle”，不是只返回工具列表；REPL 负责在替换 Soul 或退出时关闭它。

## 当前能力矩阵

| 能力 | 当前状态 | 下一步 |
|---|---|---|
| 会话消息 | JSONL 恢复已实现 | 加独立 SessionStore 回归测试 |
| Todo | 当前 Soul 内存态 | 持久化、恢复和任务依赖 |
| 工具审批 | 单次或会话内确认 | workspace 沙箱和命令策略 |
| 插件 | 本地 Python Tool 加载 | 诊断、签名和隔离 |
| MCP | stdio / HTTP / SSE server 配置、发现、调用与 Soul 生命周期关闭已实现 | OAuth 交互回调、健康检查、重连与连接池 |
| 上下文压缩 | 内存摘要和最近消息保留 | 独立 Session Note 和精确 token 计数 |
| Loop 模式 | 回合、目标、定时、事件；记录仅在进程内 | 持久化调度、云端 routine、可恢复 worker |

## 建议的毕业项目

只选一个完成，不要同时开工：

1. 持久化 Todo：定义 JSONL 格式，恢复会话时恢复 Todo，并补回归测试。
2. WorkspaceSandbox：统一校验文件路径和 Bash cwd，明确处理绝对路径、符号链接和 `..`。
3. MCP 连接管理：为现有多 transport client 增加健康检查、重连与连接池，并补真实 HTTP / SSE server 回归。

## 最终回归

```bash
./.venv/bin/python -m pytest
```

真实模型端到端测试必须显式启用 `RUN_E2E=1`。离线测试全过只能证明运行时契约没有回归，不能证明模型在每个提示词下都会选择同一种工具或给出同样的措辞。

## 本章小结

Whale CLI 的主线仍是 `Soul.run()`：模型决定，Toolset 分发，工具结果回填。11 至 19 章增加的是可配置 prompt、事件、子上下文、后台任务、分层技能、MCP、项目规则和不同触发方式。它们的共同代价是状态和生命周期更复杂，因此每加一个模块都要有对应的测试与明确边界。

下一章：[19-四种Loop模式-让Agent按条件持续工作.md](19-四种Loop模式-让Agent按条件持续工作.md)。它把已有的 Agent Loop、Hook 和后台执行组合成回合、目标、定时和事件四种运行方式。
