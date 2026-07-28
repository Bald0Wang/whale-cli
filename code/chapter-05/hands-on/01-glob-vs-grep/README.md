# 01 · Glob 和 Grep 各找什么

Glob 按文件名找，Grep 按内容找。分别跑一次，看返回结果的差异。

```bash
cd openclaw
python ../code/chapter-05/hands-on/01-glob-vs-grep/run.py
```

Glob `src/**/*.test.ts` 返回测试文件的路径列表，不打开文件。Grep `formatToolExecutorRef` 返回包含这个函数名的每一行，带文件路径和行号。

两个工具回答的问题不同：Glob 回答"哪些文件的名字符合模式"，Grep 回答"哪些文件的内容包含关键词"。

→ 对应第 5 章 §2-§4
