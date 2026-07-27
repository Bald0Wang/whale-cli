# 02 · 改一句描述，模型就换了选择

同一个 `list_dir` 工具，换三种 description 跑同一个任务：

- "列出目录下的文件和子目录" → 模型大概率选它
- "处理目录" → 模型可能犹豫
- "删除目录中的文件" → 模型可能不敢碰

```bash
cd openclaw
python ../code/chapter-02/hands-on/02-schema-description-matters/run.py
```

工具的代码一行没变，只改了一句 description。

→ 对应第 2 章 §8
