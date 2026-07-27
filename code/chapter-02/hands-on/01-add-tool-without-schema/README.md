# 01 · 函数写好了，模型知道吗

`list_dir` 函数已经写好，但故意没注册到 Toolset。问模型"看看 src/tools 下有什么"。

```bash
cd openclaw
python ../code/chapter-02/hands-on/01-add-tool-without-schema/run.py
```

模型不知道 `list_dir` 存在，只能用 `read_file`。或者它猜到了名字想调用，但 Toolset 找不到，返回错误。

→ 对应第 2 章 §1 和 §2
