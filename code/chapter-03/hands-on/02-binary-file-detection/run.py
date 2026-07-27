"""动手试 02：给 Read 不同类型的文件。

分别读 .ts 文本、.png 图片和不存在的路径。
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from tools import ReadFileTool

read = ReadFileTool()

cases = [
    ("src/tools/execution.ts", "TypeScript 文本文件"),
    ("docs/assets/openclaw-banner-light.png", "PNG 图片"),
    ("this/does/not/exist.ts", "不存在的路径"),
]

for path, label in cases:
    print(f"\n{'='*50}")
    print(f"读取：{path}（{label}）")
    print('='*50)
    result = read(path=path)
    if result["exit_code"] == 0:
        stdout = result["stdout"]
        lines = stdout.splitlines()
        print(f"  成功，返回 {len(lines)} 行")
        for line in lines[:3]:
            print(f"  {line}")
        if len(lines) > 3:
            print(f"  ... ({len(lines)-3} more lines)")
    else:
        print(f"  拒绝：{result['stderr']}")
