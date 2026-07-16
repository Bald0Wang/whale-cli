# 06. Tools v1：写文件 + 跑命令（进入 coding agent）

本章导航：

- 新增机制：写文件、编辑文件和运行 Bash，并通过 Approval 请求确认。
- 正式入口：`src/whale_cli/security/`、`src/whale_cli/tools/file/`、`src/whale_cli/tools/bash/`、`src/whale_cli/soul/approval.py`。
- 验证方式：`./.venv/bin/python -m pytest tests/test_approval.py tests/test_toolset.py tests/test_file_tools.py tests/test_workspace_security.py -q`。
- 本章不展开：系统级沙箱、容器隔离和最小系统权限仍是生产差距。

到这一步，你的 Agent 才算真正“能干活”。

因为从这里开始，它不只是看代码、解释代码，而是能：
- 改代码
- 跑测试
- 根据结果继续修

也就是你想要的那句：**形成闭环**。

---

## 本章目标（验收标准）

完成下面这条，就算通过：

- “加一行日志 + 运行单测”能一次跑通

如果一次跑不通也没关系，关键是：
- 它能把失败信息读懂
- 它知道下一步该改哪里
- 它能把改动和验证串起来

---

## Tools v1 要补齐的两类能力

### 1) 写入工具：write / edit / patch（至少两种路径）

为什么建议至少两种：
- `write` 很直接，但容易误覆盖
- `edit` 更适合小范围改动
- `patch/diff` 最适合“先看差异再应用”，也更适合审计

最稳的组合通常是：
- v1 先做 `write + edit`
- 再逐步引入 `patch`（配合 diff 展示）

### 2) 命令工具：bash

bash 是 coding agent 的核心工具之一。

它让 Agent 能做三件非常实际的事：
- 跑测试
- 跑格式化/静态检查
- 快速探索项目（列目录、搜索、查看文件）

但也因为它太强，所以风险也最大。

---

## 当前实现的安全边界

当前代码有两层边界：执行前询问，以及工具自身的 workspace 检查。它们能显著缩小教学 CLI 的误操作范围，但仍不是操作系统级沙箱。先把这件事说清楚，读者才知道什么能放心试，什么仍要谨慎。

### 当前已有：默认 ask

只要是这两类动作，默认都要 ask：
- 写文件
- 运行命令

`WriteFile`、`Edit` 和 `Bash` 都声明了 `approval_action`。`Toolset` 在调用前把动作交给 `Approval`，用户可以单次同意、在本会话内持续同意或拒绝。

### 当前已有：限制工作目录（workspace）

`security/workspace.py` 把启动时的当前目录固定为 workspace：
- `WriteFile` 和 `Edit` 先调用 `Path.resolve()`，再确认真实路径仍位于 workspace 内。
- 已存在的符号链接也会被解析，因此 `workspace/link -> /outside` 不能被用来绕过写入限制。
- `Bash` 和 `BackgroundStart` 都在 workspace 中启动；命令不再经过 `shell=True` 的 shell 解释。

安全路径既可以是相对路径，也可以是位于 workspace 内的绝对路径；目标落在目录外时，工具返回 `exit_code=1`，不会写入。

### 当前已有：危险命令策略

命令先由 `shlex` 拆成参数列表，再用 `shell=False` 执行。当前策略会拒绝：
- 删除命令：`rm`、`rmdir`、`del`、`erase`、`rd`、`shred`。
- shell 控制符和重定向：`>`, `>>`, `<`, `|`, `&&` 等。
- 命令中的父目录、绝对路径、家目录和 Windows 驱动器根路径。
- 嵌套 shell 与 `git reset --hard`、`git clean -f` 等明显破坏性 Git 操作。

这是一组可审计的**命令策略**，不是万能解析器。任意可执行文件仍可能自行访问系统资源，例如解释器中的自定义脚本。因此，审批和策略都不能替代容器、用户权限或系统沙箱。

---

## 本章验收脚本（直接复制）

这里给你一条很稳的验收路径，能把“写文件 + 跑命令 + 观察结果”串起来。

### Step 1：让它先提出方案

```text
请在不修改代码的前提下，提出一个最小改动：在启动流程里加一行日志。
然后给出验证方式（怎么跑测试/怎么运行）。
```

### Step 2：确认后执行

```text
可以开始改动，但写文件或运行命令之前都要先问我确认。
每次执行后用 2 句话总结结果。
```

### Step 3：让它跑一次测试

```text
现在运行单测。若失败，请根据失败信息给出下一步修复，并再次跑测试。
```

你要观察的不是它一次就成功，而是它有没有把闭环跑起来：
- 改动 → 测试 → 失败 → 修 → 再测 → 收束

再做两个失败实验：拒绝一次审批；让 `Edit` 使用不存在的 `old_string`。前者应返回 exit code 126，后者应返回工具错误而不写入文件。

---

## 一点经验：为什么很多工具系统会“看起来能用，但很不稳”

常见原因是两类：

1) 写入太粗暴
- 只会整段覆盖写
- 没 diff、没定位、没最小修改

2) bash 没护栏
- 能跑，但你不敢让它跑

所以 Tools v1 的关键不是“加工具”，而是“把可控性带进来”。

---

## 参考阅读

1. OpenAI：Function calling / Tools（工具定义与调用方式）
   `https://platform.openai.com/docs/guides/function-calling`
2. Anthropic：Tool use overview（工具调用与结果回填）
   `https://docs.anthropic.com/en/docs/build-with-claude/tool-use/overview`
3. OpenCode：Permissions（allow/ask/deny 的权限模型）
   `https://opencode.ai/docs/permissions`

> 注：主流 CLI 把 bash 当作核心工具，但必须配护栏。OpenCode 的权限模型就是针对这类风险动作设计的。

---

## 本章模块化代码

Tools v1 的重点是“能改变世界”，所以每个危险工具都带 `approval_action`。

### 1. 写文件工具

文件：`src/whale_cli/tools/file/write_tool.py`

```python
class WriteFileTool(Tool):
    name = "WriteFile"
    description = "Write content to a file."
    approval_action = "edit file"

    def __call__(self, *, path: str, content: str, mode: str = "overwrite") -> dict:
        target = resolve_workspace_path(path, self.workspace)

        if mode == "append":
            with target.open("a", encoding="utf-8") as f:
                f.write(content)
        else:
            with target.open("w", encoding="utf-8") as f:
                f.write(content)

        return {"stdout": f"Successfully wrote to {path}", "stderr": "", "exit_code": 0, "changed_files": [path]}
```

### 2. Bash 工具

文件：`src/whale_cli/tools/bash/bash_tool.py`

```python
class BashTool(Tool):
    name = "Bash"
    description = "Execute a shell command on the local machine."
    approval_action = "run command"

    def __call__(self, *, command: str) -> dict:
        tokens = parse_workspace_command(command)
        result = subprocess.run(
            tokens,
            shell=False,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "stdout": result.stdout or "(No output)",
            "stderr": result.stderr or "",
            "exit_code": result.returncode,
            "changed_files": [],
        }
```

### 3. 审批如何接进去

文件：`src/whale_cli/soul/toolset.py`

```python
if tool.approval_action and self._approver is not None:
    allowed = self._approver(tool.approval_action, f"{name}({args_str})")
    if not allowed:
        return {
            "stdout": "",
            "stderr": f"Error: {name} was rejected by the user.",
            "exit_code": 126,
            "changed_files": [],
        }
```

工具自己只声明“我危险”，真正是否允许执行，由 `Toolset + Approval` 决定。

### 4. workspace 解析和命令策略

文件：`src/whale_cli/security/workspace.py`

```python
def resolve_workspace_path(path: str | Path, workspace: str | Path | None = None) -> Path:
    root = workspace_root(workspace)
    requested = Path(path).expanduser()
    candidate = requested if requested.is_absolute() else root / requested
    resolved = candidate.resolve(strict=False)
    resolved.relative_to(root)  # 越界时抛出 WorkspaceViolation
    return resolved

def parse_workspace_command(command: str) -> list[str]:
    tokens = shlex.split(command)
    # 拒绝 rm、重定向、外部路径、嵌套 shell 和破坏性 Git 操作。
    return tokens
```

`resolve()` 是这个版本的关键：它检查的是符号链接解析后的真实位置，不是原始字符串里有没有 `..`。

## 本章测试与边界

```bash
./.venv/bin/python -m pytest tests/test_approval.py tests/test_toolset.py tests/test_file_tools.py tests/test_workspace_security.py -q
```

审批顺序是 `PreToolUse hook -> Approval -> Tool -> PostToolUse/PostToolUseFailure`。其中 Hook 阻止返回 125，用户拒绝返回 126，workspace 或命令策略拒绝返回 1。三者都只是可观察的控制点，不能替代容器、操作系统权限或真正的系统沙箱。

## 本章小结

写文件和执行命令使 Agent 能改变项目，因此它们必须走统一的审批链，并被 workspace 与命令策略约束。审批回答“这一次是否允许”，策略回答“是否符合当前边界”，两者都不等于系统级隔离。下一章把多步任务的进度独立保存，避免模型只用一段自然语言记计划。

下一章：[07-TodoList-把计划变成可追踪任务.md](07-TodoList-把计划变成可追踪任务.md)。
