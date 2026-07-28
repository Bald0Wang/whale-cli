# 02 · 给 Read 一张 PNG 会怎样

分别拿 `.ts` 文本文件、`.png` 图片和一个不存在的路径喂给 `read_file`。

```bash
cd openclaw
python ../code/chapter-03/hands-on/02-binary-file-detection/run.py
```

`.ts` 正常返回带行号的内容。`.png` 直接拒绝——"二进制格式，read_file 只处理文本文件"。路径不存在的也拒绝。

不拦的话，模型会收到一堆乱码，以为自己看到了代码。

→ 对应第 3 章 §5-§6
