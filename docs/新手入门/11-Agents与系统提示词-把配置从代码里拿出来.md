# 11. Agents 与系统提示词：把“角色”从代码里拿出来

本章导航：

- 新增机制：从 agent spec 与模板构造系统提示词，而不是把整段 prompt 固定在 Python 中。
- 正式入口：`src/whale_cli/agents/`、`src/whale_cli/soul/soul.py`。
- 验证方式：`./.venv/bin/python -m pytest tests/test_skills_and_agents.py -q`。
- 本章不展开：热更新、完整 agentspec 校验和多 agent 路由尚未实现。

前 10 章里，Whale CLI 已经能跑：有 REPL、有会话、有工具、有审批、有 todo、有压缩。

但它还有一个明显的教学版取舍：**系统提示词写在 `Soul._build_system_prompt()` 里**。这对入门很好，因为你一眼能看见 agent 的行为约束；但一旦你想支持 `coder` / `plan` / `explore` 这类不同角色，硬编码就会开始拖后腿。

生产级参考实现的做法是：agent 不是一个写死的类，而是一份可加载的规格。

## 本章目标（验收标准）

读完这一章，你应该能回答：

- 为什么成熟 CLI Agent 会把 agent 定义拆成 `agent.yaml` + `system.md`
- 生产级参考实现的 `Runtime` / `Agent` / `load_agent()` 大概在解决什么问题
- Whale CLI 如果继续进化，应该先补哪一层，而不是一上来做完整插件系统

本章是进阶结构篇，重点是结构设计，不要求你立刻改完所有代码。

## 生产级参考实现里的真实结构

生产级参考实现的默认 agent 大致长这样：

```text
production_cli/
├── agents/
│   └── default/
│       ├── agent.yaml
│       ├── coder.yaml
│       ├── explore.yaml
│       ├── plan.yaml
│       └── system.md
├── soul/
│   ├── agent.py       # Runtime / Agent / load_agent
│   └── agent_loop.py    # 真正跑 loop 的 soul
└── tools/
```

关键点不是文件名，而是职责拆分：

| 层 | 负责什么 |
|---|---|
| `agent.yaml` | 这个 agent 叫什么、能用哪些工具、有哪些子 agent、用哪个 system prompt |
| `system.md` | agent 的长期行为约束，用模板变量注入运行时上下文 |
| `Runtime` | 当前会话的环境：工作目录、模型、审批、skills、background manager、subagent store |
| `Agent` | 已加载完成的 agent：`name + system_prompt + toolset + runtime` |
| `AgentLoop` | 不关心 agent 是怎么加载的，只负责拿着 agent 跑循环 |

这就是成熟实现和入门实现的第一道分界线：**入门版把角色、工具、运行时放在一个类里；成熟版先把它们拆成可组合对象。**

## Whale CLI 现在在哪里

Whale CLI 当前是更适合教学的结构：

```text
Soul.__init__()
  ├── 创建 LLMClient
  ├── 创建 TodoStore
  ├── 创建 Toolset
  ├── 绑定 Approval
  └── _build_system_prompt()
```

好处是清楚，坏处是：

- 只能有一个默认 agent
- 工具集不能按角色切换
- system prompt 无法被项目配置覆盖
- 想做 `plan` / `coder` / `explore` 会把 `Soul` 越塞越大

## 教学版应该怎么补

不要一步到位复刻生产级参考实现。Whale CLI 下一步只需要三件事：

```text
src/whale_cli/
├── agents/
│   ├── default/
│   │   ├── agent.yaml
│   │   └── system.md
│   └── loader.py
└── soul/
    └── soul.py
```

最小 `agent.yaml` 可以只有这些字段：

```yaml
name: default
system_prompt: system.md
tools:
  - ReadFile
  - Glob
  - Grep
  - WriteFile
  - Edit
  - Bash
  - SearchWeb
  - FetchURL
  - TodoWrite
  - GetDate
```

最小 `system.md` 则保留现在 `_build_system_prompt()` 里的核心内容，但把动态字段留成占位：

```markdown
You are Whale, a helpful coding agent running in the terminal.

Work dir: {{ work_dir }}
OS: {{ os_info }}
Now: {{ now }}

Available tools:
{{ tools }}

Guidelines:
- Explore before assuming.
- Track multi-step tasks with TodoWrite.
- Verify after changing files.
```

这样做以后，`Soul` 不再负责“定义 agent 是谁”，只负责“让 agent 跑起来”。

## 实现顺序建议

1. 新增 `agents/default/system.md`，先把当前 system prompt 文本搬进去。
2. 新增 `agents/default/agent.yaml`，声明默认工具清单。
3. 新增 `agents/loader.py`，把 yaml + system.md 渲染成一个小 dataclass。
4. `Soul.__init__()` 接受 `agent_spec`，按 spec 组装 toolset 和 prompt。
5. 保留 `_build_system_prompt()` 作为 fallback，避免配置坏了 CLI 直接不能用。

## 本章验收

做到这一章，不看功能数量，看结构是否变轻：

- 改 system prompt 不需要改 `soul.py`
- 禁用某个工具只改 `agent.yaml`
- 新增 `plan` agent 不需要复制一份 `Soul`
- `Soul` 的职责能用一句话说清：维护消息、调用模型、执行工具、回填结果

## 和生产级参考实现的差距

生产级参考实现的 agent loader 还会做更多事：

- 加载 `AGENTS.md`
- 发现并格式化 skills
- 组装工作目录 listing
- 注入 OS / shell / 当前时间
- 加载插件工具和 MCP 工具
- 注册内置 subagent 类型

Whale CLI 这一章只拿其中最重要的一刀：**把 agent 规格从 loop 里拆出去。**

这一步做完，后面的 hooks、skills、subagents、MCP 才有位置可以挂。

---

## 本章模块化代码

这一章对应 `agents/` 目录。目标是把“默认 agent 是谁、能用哪些工具、系统提示词是什么”从 `Soul` 里拆出来。

### 1. agent.yaml

文件：`src/whale_cli/agents/default/agent.yaml`

```yaml
name: default
system_prompt: system.md
tools:
  - ReadFile
  - Glob
  - Grep
  - WriteFile
  - Edit
  - Bash
  - SearchWeb
  - FetchURL
  - TodoWrite
  - GetDate
  - Agent
  - BackgroundStart
  - BackgroundList
  - BackgroundOutput
```

### 2. AgentSpec 数据结构

文件：`src/whale_cli/agents/loader.py`

```python
@dataclass(frozen=True)
class AgentSpec:
    name: str
    system_prompt_path: Path
    tools: list[str]
```

### 3. 加载规格并渲染 system.md

```python
def load_agent_spec(agent_file: str | Path | None = None) -> AgentSpec:
    path = Path(agent_file) if agent_file else default_agent_dir() / "agent.yaml"
    data = _parse_simple_yaml(path)
    system_prompt = str(data.get("system_prompt") or "system.md")
    tools = data.get("tools") or []
    return AgentSpec(
        name=str(data.get("name") or "default"),
        system_prompt_path=(path.parent / system_prompt).resolve(),
        tools=[str(t) for t in tools],
    )


def render_system_prompt(spec: AgentSpec, args: dict[str, str]) -> str:
    text = spec.system_prompt_path.read_text(encoding="utf-8")
    for key, value in args.items():
        text = text.replace("{{ " + key + " }}", value)
        text = text.replace("{{" + key + "}}", value)
    return text.strip() + "\n"
```

### 4. `Soul` 如何使用它

```python
spec = load_agent_spec()
system_prompt = render_system_prompt(spec, {
    "os_info": os_info,
    "tools": "\n".join(tool_lines),
    "agents_md": agents_md,
    "skills": skills,
    "now": now_iso,
})
```

这个拆分让“改角色”变成改文件，而不是改主循环。

## 本章测试与边界

```bash
./.venv/bin/python -m pytest tests/test_skills_and_agents.py -q
```

当前 `agent.yaml` 使用的是教学用的简单解析器，只支持本项目需要的少量键和值，不等于完整 YAML 解析。`Soul._build_system_prompt()` 在加载或渲染失败时会使用内置 fallback prompt；这能让 CLI 启动，但也可能掩盖配置错误，因此修改 agent 文件后应主动验证渲染结果。

## 本章小结

Agent 配置把“角色、可用工具和系统提示”从主循环中拆出来。当前模板仍由 `Soul` 在启动时渲染，失败时会退回内置 prompt。下一章只增加事件回调，让不改主循环的规则也能观察和干预运行时。

下一章：[12-Hooks-把自动化护栏挂在循环外.md](12-Hooks-把自动化护栏挂在循环外.md)。
