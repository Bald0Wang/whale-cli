# 02 · 故意破坏循环

Agent Loop 里每一步都有它的理由。这组脚本逐个拿掉关键步骤，看程序怎么崩。

```bash
cd openclaw

# 不保存模型的工具请求，直接追加 tool result
python ../code/chapter-01/hands-on/02-break-the-loop/01_skip_assistant_message.py

# tool result 不带 tool_call_id
python ../code/chapter-01/hands-on/02-break-the-loop/02_missing_tool_call_id.py

# 只允许循环跑 1 轮
python ../code/chapter-01/hands-on/02-break-the-loop/03_only_one_turn.py
```

前两个会直接报错——API 要求消息顺序和 ID 配对严格一致。第三个不会报错，但任务做不完。

→ 对应第 1 章 §9
