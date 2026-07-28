# 01 · Write 和 Edit 各自适合什么场景

让模型分别用 Write 创建一个新文件，再用 Edit 修改已有文件中的一行。对比两种工具的行为差异。

```bash
cd openclaw
python ../code/chapter-04/hands-on/01-write-vs-edit/run.py
```

Write 需要模型输出完整文件内容。Edit 只需要给出 old_string 和 new_string，其余代码不动。如果让 Write 去改一个已有文件，模型得把整个文件重新输出一遍——这时候很容易漏掉几行。

→ 对应第 4 章 §1-§3
