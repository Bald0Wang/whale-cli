# 01 · 加不加 tools，模型行为完全不同

同一句话问两遍。第一遍不给模型任何工具，第二遍加上 `read_file`。

```bash
cd openclaw
python ../code/chapter-01/hands-on/01-no-tools-vs-with-tools/run.py
```

第一遍，模型会让你自己把文件内容粘过来。第二遍，它直接返回一段 `tool_calls` JSON，请求调用 `read_file`。

什么都没变——同一个模型，同一句话。只是请求里多了一份工具说明。

→ 对应第 1 章 §1
