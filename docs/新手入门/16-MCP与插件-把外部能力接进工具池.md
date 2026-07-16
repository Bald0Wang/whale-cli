# 16. MCP：把远端工具接进 Whale CLI

本章导航：

- 新增机制：发现 MCP server 的远端工具，并适配为经过 Approval 与 Toolset 的本地 Tool。
- 正式入口：`src/whale_cli/mcp/`、`src/whale_cli/soul/soul.py`。
- 验证方式：`./.venv/bin/python -m pytest tests/test_mcp.py -q`。
- 本章不展开：OAuth 交互回调、健康检查、重连和连接池尚未实现。

插件是当前进程里的 Python `Tool`；MCP（Model Context Protocol）让工具留在独立 server 中。Whale CLI 不需要知道 server 的业务细节，只要完成一条固定链路：读取配置、连接并发现工具、把工具转成项目自己的 `Tool`、在模型请求时转发调用。

这一章的代码已经可运行，不是只放一个接口名：项目附带真实 stdio echo server，并有从 `Soul` 到远端 server 再返回模型的回归测试。

## 前置知识

- [05-Toolsv0-最小工具箱.md](05-Toolsv0-最小工具箱.md)：`Tool`、schema 和统一结果。
- [06-Toolsv1-写文件与跑命令.md](06-Toolsv1-写文件与跑命令.md)：审批不等于沙箱。
- [11-Agents与系统提示词-把配置从代码里拿出来.md](11-Agents与系统提示词-把配置从代码里拿出来.md)：工具为什么会进入模型的系统提示词和 tools 参数。

> 安全提示：配置一个 MCP server，等于允许 Whale CLI 启动本地命令，或向远端服务发送模型生成的参数。只配置可信来源；审批只能拦住一次调用，不能把不可信 server 变安全。

## 本章目标

完成后，你应该能：

1. 用项目配置启动一个真实 stdio MCP server。
2. 看懂 `mcp__<server>__<tool>` 如何进入 `Toolset`。
3. 解释 MCP 调用为什么仍要经过 Approval、Hook 和标准错误格式。
4. 区分已实现的 stdio / HTTP / SSE 与尚未完成交互授权的 OAuth。

## 先看完整数据流

```text
.whale_cli/mcp.json
        |
        v
load_mcp_server_configs()
        |
        v
load_mcp_tools_with_lifecycle()
        |
        +--> MCPClient.start()
        |      FastMCP Client -> initialize -> list_tools
        |
        v
MCPToolAdapter
  mcp__<server>__<tool> + OpenAI function schema
        |
        v
Soul._default_tools() -> Toolset
        |
        v
模型 tool_call -> Approval -> MCPToolAdapter.__call__()
        |
        v
MCPClient.call_tool() -> FastMCP tools/call -> 标准 Tool result -> Soul
```

关键点是：MCP 工具不是直接暴露给模型的特殊通道。发现后，它和 `Bash`、本地 plugin 一样放进 `Toolset`，所以参数解析、`PreToolUse` / `PostToolUse` Hook、审批和工具结果回填都沿用现有运行时。

## 1. 跑通真实 stdio server

项目提供了最小但真实的 server：

```text
examples/mcp_echo_server.py
```

它用 `FastMCP` 暴露 `echo(text)`。在项目根目录执行：

```bash
source .venv/bin/activate
mkdir -p .whale_cli
cp mcp.example.json .whale_cli/mcp.json
whale-cli
```

示例配置采用 Claude Desktop 同样的 `mcpServers` 映射格式：

```json
{
  "mcpServers": {
    "echo-server": {
      "transport": "stdio",
      "command": "python",
      "args": ["examples/mcp_echo_server.py"],
      "env": {},
      "timeout_s": 30
    }
  }
}
```

然后输入：

```text
请调用 mcp__echo_server__echo，把 "hello mcp" 原样返回。
```

默认 safe 模式会显示审批提示。确认后，最终结果应包含 `echo:hello mcp`。`command` 和相对 `args` 以启动 Whale CLI 时的当前项目目录为准；先激活 `.venv`，能保证 server 和 CLI 使用同一套依赖。

## 2. 配置格式：从最常用开始

默认路径是当前工作目录的 `.whale_cli/mcp.json`。设置 `WHALE_MCP_CONFIG` 可以改为另一个文件，这适合把包含密钥的配置放在项目外面。

### stdio

| 字段 | 作用 | 要求 |
|---|---|---|
| 映射 key | server 名 | 必填，成为本地工具名前缀 |
| `transport` | 连接方式 | `stdio`，省略时可由 `command` 推断 |
| `command` | 启动命令 | 必填 |
| `args` | 命令参数 | 字符串数组，默认 `[]` |
| `env` | 传给子进程的环境变量 | 字符串键值对，默认 `{}` |
| `timeout_s` | 发现或单次调用的超时秒数 | 正数，默认 30 |

旧版 `{"servers": [{"name": "...", ...}]}` 也能读取，便于兼容已有教程；新配置优先使用 `mcpServers`。

### Streamable HTTP 与 SSE

当前客户端也能创建 HTTP 和 SSE transport。下面是 HTTP 的最小形状：

```json
{
  "mcpServers": {
    "project-api": {
      "transport": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": {"Authorization": "Bearer replace-with-a-secret"},
      "timeout_s": 30
    }
  }
}
```

将 `transport` 改为 `sse` 就是 SSE endpoint。未写 `transport` 而写了 `url` 时，当前实现按 HTTP 处理。

一些 MCP 服务配置使用 `type` 而不是 `transport`。Whale CLI 也兼容它，例如下面这类 SSE 配置会按 `sse` 连接；同时存在时以 `transport` 为准：

```json
{
  "mcpServers": {
    "amap-maps": {
      "type": "sse",
      "url": "https://example.com/sse"
    }
  }
}
```

`headers` 会原样发送，**不会**替换 `${ENV_VAR}` 之类的占位符。因此不要把真实密钥提交到仓库；把配置文件放在仓库外并通过 `WHALE_MCP_CONFIG` 指向它，或使用 server 支持的其他本地凭据方式。

OAuth 只完成了 token storage 和 provider 装配；交互式浏览器回调尚未实现。也就是说，`"auth": "oauth"` 目前不是可交付的登录流程。需要 OAuth 的 server 请先使用其 API key header 方式，或补完回调处理后再启用。

## 3. 远端工具怎样变成本地 Tool

MCP 的 `list_tools()` 返回工具名、描述和 JSON schema。`MCPToolAdapter` 将它变成项目已有的 Tool 合约：

```python
class MCPToolAdapter(Tool):
    def __init__(self, server_name, remote_tool, client):
        self.name = f"mcp__{safe(server_name)}__{safe(remote_tool.name)}"
        self.description = remote_tool.description
        self.schema = {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": remote_tool.input_schema,
            },
        }
        self.approval_action = f"call MCP tool ({server_name})"
```

例如 `echo-server` 的 `echo` 会成为：

```text
mcp__echo_server__echo
```

名字保留 server 前缀，避免两个 server 都有 `search` 工具时发生冲突。连字符等特殊字符会转成下划线。

## 4. 调用、审批和错误结果

模型发起 `mcp__...` tool call 后，执行顺序是：

1. `Toolset` 解析模型给出的 JSON 参数。
2. `Approval` 根据 `approval_action` 询问、拒绝或在 `/yolo` 模式自动允许。
3. `MCPToolAdapter` 调用 `MCPClient.call_tool()`。
4. `MCPClient` 用 FastMCP client 进入 transport session，执行远端 `tools/call`。
5. adapter 把结果转换为 Whale CLI 的统一字典，`Soul` 再把它作为 `role="tool"` 消息交还模型。

| 远端情况 | Whale CLI 工具结果 |
|---|---|
| 正常文本内容 | `stdout`，`exit_code=0` |
| 仅有结构化内容 | JSON 写入 `stdout`，`exit_code=0` |
| MCP 返回 `isError` | `stderr`，`exit_code=1` |
| Python `TimeoutError` | `stderr="MCP call timed out"`，`exit_code=124` |
| 连接、协议或 server 异常 | `stderr="MCP call failed: ..."`，`exit_code=1` |

通用 MCP 返回中没有可信的“本地文件变更列表”，因此 `changed_files` 目前总是空数组。远端 server 可能改了数据，但 CLI 不应猜测它改了哪些文件。

## 5. 生命周期：为什么 Soul 需要 close

`load_mcp_tools_with_lifecycle()` 返回两部分：工具列表和 `MCPLifecycle`。`Soul` 保存 lifecycle；REPL 在退出、`/clear` 或 `/session load` 前调用 `agent.close()`，释放各 MCP client 的 transport 资源。

当前教学实现是同步的：每次发现和每次 `tools/call` 都会进入一次 FastMCP 异步上下文，再退出。它比常驻异步 session 更容易阅读和测试，但不等于生产环境的连接池、健康检查或自动重连。不要把它描述成“每个工具调用永久长连接”。

## 6. Plugin 与 MCP 的边界

| 问题 | Plugin | MCP |
|---|---|---|
| 工具代码位置 | 当前项目的 Python 文件 | 独立进程或远端 server |
| 发现方式 | 扫描 `plugin.json` 并 import 类 | 连接后调用 `list_tools()` |
| 执行方式 | 直接调用本地对象 | 发送 MCP `tools/call` |
| 常见失败 | import、参数、Python 异常 | 启动、连接、超时、远端错误 |
| 安全边界 | 与 CLI 同一进程权限 | 外部命令或网络服务，仍需审批 |

它们共用 `Toolset`，只说明模型看到的接口一致；不表示它们具有同样的部署和信任边界。

## 本章模块化代码

- `src/whale_cli/mcp/models.py`：三种 transport 共用的配置、远端工具和调用结果。
- `src/whale_cli/mcp/client.py`：基于 FastMCP 的同步外观，负责 transport、发现、调用与结果转换。
- `src/whale_cli/mcp/adapter.py`：把远端工具变为本地 `Tool`。
- `src/whale_cli/mcp/loader.py`：读取配置、兼容两种 JSON 形状，并管理 `MCPLifecycle`。
- `src/whale_cli/soul/soul.py`：把 MCP tools 放入默认工具池，并暴露 `Soul.close()`。
- `src/whale_cli/ui/shell/main.py`：退出、清空和切换会话时关闭当前 agent 的 MCP lifecycle。
- `examples/mcp_echo_server.py`：真实 stdio MCP server，供学习和回归测试使用。

## 本章测试

```bash
./.venv/bin/python -m pytest tests/test_mcp.py -q
```

测试从浅到深覆盖：

1. fake client：schema、命名、远端错误、Approval 和 lifecycle 关闭。
2. 配置解析：Claude Desktop 风格 `mcpServers` 的 HTTP 配置。
3. 真实 stdio echo server：`list_tools()` 与 `tools/call`。
4. 完整 Soul 回合：脚本化模型选择远端工具，真实 server 返回结果，模型再给出最终回答。

## 当前边界

- stdio、Streamable HTTP 和 SSE transport 已有实现；只对项目内 stdio echo server 做了真实 server 回归。
- OAuth provider 的交互回调未实现，不能作为可用的登录方案。
- 没有 health check、重连退避、并发连接池或资源 / prompts 接入。
- 配置错误和发现失败会打印 `[MCP] ... skipped`，不会阻止 CLI 启动；启动日志是排查第一入口。
- 所有 MCP 工具默认需要审批。后台 Loop 在 safe 模式下会拒绝它们，只有显式 `/yolo` 才允许无人值守调用。

## 本章小结

MCP 把远端工具适配成当前项目的 Tool 合约，因此审批、Hook 和结果回填不需要重写。transport 已覆盖 stdio、HTTP 和 SSE，但 OAuth 回调和连接健康管理仍未完成。下一章转回仓库内部规则，说明 `AGENTS.md` 怎样进入系统提示词。

下一章：[17-AGENTS与项目上下文-让仓库规则自动生效.md](17-AGENTS与项目上下文-让仓库规则自动生效.md)。
