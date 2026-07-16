# 19. 四种 Loop 模式：让 Agent 按条件持续工作

本章导航：

- 新增机制：在默认回合 Loop 外，引入目标、定时和事件触发的运行方式。
- 正式入口：`src/whale_cli/loops/`、`src/whale_cli/ui/shell/loop_commands.py`。
- 验证方式：`./.venv/bin/python -m pytest tests/test_loop_modes.py tests/test_loop_commands.py -q`。
- 本章不展开：Loop 记录不会持久化，目标评估也不是确定性验证器。

04 章讲的是一次 Agent Loop：用户提问，模型调用工具，工具结果回到模型，直到模型给出答案。这个循环已经够解决大量短任务。

有些任务需要把“什么时候开始”和“什么时候停下”也交给系统管理。本章把 Loop 按这两个问题分成四种模式：回合驱动、目标驱动、定时驱动和事件驱动。

## 前置知识

- 先读 [04-AgentLoopv0-从聊天到会做事的循环.md](04-AgentLoopv0-从聊天到会做事的循环.md)，理解一次 `Soul.run()` 如何完成模型和工具的闭环。
- 先读 [12-Hooks-把自动化护栏挂在循环外.md](12-Hooks-把自动化护栏挂在循环外.md)，理解事件如何由 `HookEngine` 发出。
- 定时或事件循环会在后台运行。执行会修改文件或运行命令的任务前，先读 06 章的审批边界。

## 四种模式一览

| 模式 | 触发方式 | 停止条件 | 适合的任务 | Whale CLI 入口 |
|---|---|---|---|---|
| 回合驱动 | 用户发送普通消息 | 本次 `Soul.run()` 完成、失败、中止或达到步数上限 | 探索、决策、一次改动 | 普通输入 |
| 目标驱动 | 用户手动定义任务和完成条件 | 评估器返回 PASS，或达到轮数上限 | 有明确验收条件的修复与验证 | `/goal` |
| 定时驱动 | 到达固定时间间隔 | 达到运行次数，或用户取消 | 周期性检查、轮询队列 | `/loop` |
| 事件驱动 | Hook 事件发生 | 每次事件内的目标完成或达到轮数上限；例程本身由用户取消 | 工具失败恢复、压缩后检查、持续分诊 | `/routine` |

不要为了“更像 Agent”而给所有任务套长循环。先使用普通回合；只有当触发条件或停止条件需要系统维护时，才选择其他三种。

## 1. 回合驱动：当前默认模式

在 REPL 中输入普通文本，就是一次回合驱动循环：

```text
请只读探索这个项目，找出测试命令并解释依据。
```

`LoopManager.run_turn()` 调用一次 runner，runner 最终调用 `Soul.run()`。`Soul.run()` 会返回 `LoopOutcome`：

```text
completed  模型给出最终文本
failed     模型调用或运行时异常
aborted    用户在安全检查点中止
max_steps  工具调用一直继续，达到上限
```

这里“完成”只表示这一回合停止，不表示某个业务目标一定已经满足。想验证“所有测试都通过”时，需要目标驱动模式。

## 2. 目标驱动：把完成条件写出来

命令格式：

```text
/goal <最大轮数> :: <完成条件> :: <任务>
```

示例：

```text
/goal 3 :: tests/test_todo.py 全部通过 :: 修复 Todo 状态校验失败，并运行对应测试
```

每轮任务结束后，Whale CLI 会发起一个不带工具的评估请求。评估器只能返回 `PASS` 或 `CONTINUE` 加简短理由：

```text
任务 -> Soul.run() -> 本轮结果
                       |
                       v
                 目标评估器
                   |       |
                 PASS   CONTINUE
                   |       |
                 结束   反馈写回下一轮
```

目标要尽量可检查。`所有测试通过`、`文件包含指定文本`、`退出码为 0` 比“把代码写好”“页面看起来更漂亮”更容易判断。当前评估器仍使用模型判断；更可靠的做法是把测试、截图或脚本结果写进 Skill，让模型基于可观察证据完成判断。

## 3. 定时驱动：在间隔内重复同一个任务

命令格式：

```text
/loop <间隔> <最大运行次数> :: <任务>
```

间隔支持 `s`、`m`、`h`：

```text
/loop 5m 4 :: 检查当前项目的待办队列，只在有变化时汇报
```

这条命令会创建一个内存中的后台循环。它首次等待 5 分钟，随后最多运行 4 次。查看或取消：

```text
/loops
/loop cancel <loop_id>
```

定时循环适合输入会变化、任务本身不变的场景，例如检查 CI、轮询外部队列或生成周期性摘要。它不适合一次性的代码修复。

### 后台审批规则

后台线程不能安全地与 REPL 同时读取 `stdin`。因此在默认安全模式下，定时和事件循环遇到需要审批的工具会被拒绝，并把拒绝结果回给模型。只有用户显式执行 `/yolo` 后，后台循环才会自动批准危险工具。

这是一条很窄的自动化通道。开启 `/yolo` 前，要先确认任务、工作目录和最大运行次数。

## 4. 事件驱动：发生某件事后再开始

命令格式：

```text
/routine <Hook事件> <最大轮数> :: <完成条件> :: <任务>
```

示例：

```text
/routine PostToolUseFailure 2 :: 已给出可执行的恢复方案 :: 检查失败工具的 stderr，说明原因并提出下一步
```

当前运行时会发出这些事件：

```text
UserPromptSubmit
PreToolUse
PostToolUse
PostToolUseFailure
PreCompact
PostCompact
```

`/routine` 把例程注册到当前 `agent.hooks`。事件发生时，LoopManager 会把事件名和 payload 加入任务提示，再运行一次目标循环。若同一例程仍在处理上一次事件，新事件不会再启动并发副本。

例程会一直保留到 `/loop cancel <loop_id>`、`/clear` 或 `/session load <id>`。后两种操作会取消现有例程，避免旧会话的 Hook 继续驱动新会话。

## 真实调用链

```text
普通输入
  -> LoopManager.run_turn()
  -> Soul.run()

/goal
  -> parse_goal_command()
  -> LoopManager.run_goal()
  -> Soul.run() + tool-free goal evaluator

/loop
  -> parse_time_command()
  -> LoopManager.create_time_loop()
  -> daemon thread -> tick() -> Soul.run()

/routine
  -> parse_proactive_command()
  -> HookEngine.on(event)
  -> LoopManager.trigger_proactive()
  -> background goal loop -> Soul.run()
```

核心代码位于：

- `src/whale_cli/loops/models.py`：模式、状态、运行结果和记录。
- `src/whale_cli/loops/manager.py`：四种模式的生命周期、次数上限、取消和 Hook 绑定。
- `src/whale_cli/ui/shell/loop_commands.py`：严格解析命令，避免把自然语言猜成调度参数。
- `src/whale_cli/ui/shell/main.py`：把命令接进 REPL。
- `src/whale_cli/soul/approval.py`：后台线程默认拒绝需要交互审批的动作。

## 本章模块化代码

目标模式的核心不在“多跑几次”，而在每次结束后拿到一个可判断的结果：

```python
record = loop_manager.run_goal(
    task_prompt="修复 Todo 状态校验失败",
    goal="tests/test_todo.py 全部通过",
    max_turns=3,
    evaluator=evaluate_goal,
)
```

定时模式保留手动 `tick()`，因此不必等待真实时间就能测试调度行为：

```python
record = loop_manager.create_time_loop(
    "检查队列",
    interval_seconds=300,
    max_runs=4,
    autostart=False,
)
loop_manager.tick(record.loop_id)
```

事件模式将 Hook 与目标循环组合，而不是修改 `Soul.run()`：

```python
record = loop_manager.register_proactive(
    hooks,
    event_name="PostToolUseFailure",
    task_prompt="检查失败工具输出",
    goal="恢复方案已给出",
    max_turns=2,
    evaluator=evaluate_goal,
)
```

## 本章测试与边界

```bash
./.venv/bin/python -m pytest \
  tests/test_loop_modes.py \
  tests/test_loop_commands.py \
  tests/test_approval.py \
  tests/test_soul_integration.py -q
```

当前实现有四个明确边界：

- 循环记录只保存在进程内；重启 CLI 后不会恢复定时循环或例程。
- 目标评估器是额外一次模型调用，可能误判；重要目标应以测试、脚本或其他确定性证据为准。
- 定时循环按固定间隔运行，没有云端调度、cron 持久化或错过执行后的补偿机制。
- 事件循环只消费当前进程中的 Hook 事件，不会自动接收 GitHub、CI 或消息队列事件。

## 自测题

1. 为什么“模型回答了”不等于目标模式中的“目标完成了”？
2. 为什么后台循环在安全模式下要拒绝危险工具，而不是等待 `input()`？
3. `PostToolUseFailure` 例程和定时循环的触发条件有什么不同？

答案：目标模式还会检查完成条件；后台线程与 REPL 争用输入会破坏交互；前者由一次运行时事件触发，后者由时间间隔触发。

## 本章小结

普通回合仍是默认选择；目标、定时和事件模式只在系统需要维护触发条件或停止条件时使用。四种模式共享同一个 `Soul.run()`，区别在于谁触发它、何时评估结果以及记录何时取消。课程到这里结束，后续练习应从 18 章的毕业项目中选一个，并先补对应测试。
