# 01 · 一次读完 vs 分段读

`setup-inference.ts` 有 2897 行。一次全读进去，和分 200 行一段读，差别有多大？

```bash
cd openclaw
python ../code/chapter-03/hands-on/01-full-file-vs-range/run.py
```

全读：约 1.7 万 token 塞进上下文，模型也许能答对，但后面每一轮都要带着这些内容。分段读前 200 行：只用 1200 token，但目标函数在第 309 行，这次看不到。再读 201-400 行：找到了。

Read 的关键不是"能不能读到"，是"该返回多少"。

→ 对应第 3 章 §1-§2
