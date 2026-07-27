# 03 · 不给路径，模型会怎样

问一个模糊的问题——"这个项目怎么启动？"——不告诉它任何文件路径。只有 `read_file`，没有 `list_dir`。

```bash
cd openclaw
python ../code/chapter-01/hands-on/03-unknown-path-failure/run.py
```

模型只能猜：`src/main.py`、`data.txt`、`script.py`……大部分不存在，最终触发 `max_turns` 限制。

换个模型结果可能完全不同。qwen-max 读了 README 和 package.json 以后开始乱猜 Python 文件；deepseek-chat 可能 3 轮就答对了。同样的工具，不同模型差距很大。

→ 对应第 1 章 §10
