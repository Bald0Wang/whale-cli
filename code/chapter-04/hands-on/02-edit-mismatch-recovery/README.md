# 02 · Edit 写错了 old_string 会怎样

故意给 Edit 一个和文件内容不完全一致的 old_string，看工具怎么报错、模型怎么修正。

```bash
cd openclaw
python ../code/chapter-04/hands-on/02-edit-mismatch-recovery/run.py
```

工具不会猜着改——匹配不到就拒绝落盘，返回文件中最相似的代码片段。模型看到这个提示以后，通常能一次修正 old_string。

如果工具只返回"not found"没有任何提示，模型就只能盲猜下一次该写什么，可能连试三次都改不对。

→ 对应第 4 章 §7
