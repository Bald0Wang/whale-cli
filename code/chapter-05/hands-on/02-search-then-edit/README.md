# 02 · 不给路径，让模型自己找到代码再改

不告诉模型文件在哪，只说"找到 formatToolExecutorRef，把冒号改成斜杠"。看完整的 Grep → Read → Edit 链路。

```bash
cd openclaw
python ../code/chapter-05/main.py "在 TypeScript 文件中搜索 formatToolExecutorRef 函数的定义，然后把冒号分隔符改成斜杠"
```

模型先 Grep 定位到 `src/tools/execution.ts` 第 11 行，再 Read 看完整函数，最后 Edit 逐个替换四个 case 分支。整条链路自动完成。

记得跑完以后 `git checkout -- src/tools/execution.ts` 恢复文件。

→ 对应第 5 章 §12
