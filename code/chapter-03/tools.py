"""第 3 章 · 工具定义：ReadFileTool（完整版）+ ListDirTool。

和 ch02 的差异：
- ReadFileTool 升级：行范围、行号、二进制检测（detect_file_kind + magic bytes）、
  长行截断、文件头元信息、继续提示
- 返回值从 str 改为 dict（ok/err）
"""
from pathlib import Path

from registry import Tool, ok, err


DEFAULT_WINDOW_LINES = 200
MAX_LINE_CHARS = 2000

IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".ico",
}

ARCHIVE_EXTENSIONS = {
    ".zip",
    ".tar",
    ".gz",
    ".7z",
}

OFFICE_EXTENSIONS = {
    ".docx",
    ".pptx",
    ".xlsx",
}


def detect_file_kind(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        return "image"

    if suffix == ".pdf":
        return "pdf"

    if suffix in OFFICE_EXTENSIONS:
        return "office"

    if suffix in ARCHIVE_EXTENSIONS:
        return "archive"

    head = path.read_bytes()[:16]

    if head.startswith(b"\x89PNG"):
        return "image"

    if head.startswith(b"\xff\xd8\xff"):
        return "image"

    if head.startswith(b"%PDF"):
        return "pdf"

    if b"\x00" in head:
        return "binary"

    return "text"


def truncate_line(line: str) -> tuple[str, bool]:
    if len(line) <= MAX_LINE_CHARS:
        return line, False

    shortened = (
        line[:MAX_LINE_CHARS]
        + f" ... <truncated, original {len(line)} chars>"
    )
    return shortened, True


class ReadFileTool(Tool):
    name = "read_file"
    description = (
        "读取当前项目中的文本文件，返回带行号的内容。"
        "可用 start_line 和 end_line 指定读取范围。"
        "读取大文件时应优先分段读取，不要一次请求全文。"
    )
    schema = {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "读取当前项目中的文本文件，返回带行号的内容。"
                "可用 start_line 和 end_line 指定读取范围。"
                "读取大文件时应优先分段读取，不要一次请求全文。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要读取的文件路径",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "起始行，默认是第 1 行",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": (
                            "结束行；省略时最多读取 200 行"
                        ),
                    },
                },
                "required": ["path"],
            },
        },
    }

    def __call__(
        self,
        *,
        path: str,
        start_line: int = 1,
        end_line: int | None = None,
    ) -> dict:
        file_path = Path(path)

        if not file_path.exists():
            return err(f"Error: 文件不存在 {path}")

        if not file_path.is_file():
            return err(f"Error: 不是文件 {path}")

        kind = detect_file_kind(file_path)

        if kind == "image":
            return err(
                f"Error: 检测到图片文件 {path}，"
                "read_file 只返回文本内容。"
            )

        if kind == "pdf":
            return err(f"Error: 检测到 PDF {path}，需要文档解析器。")

        if kind == "office":
            return err(f"Error: 检测到 Office 文档 {path}，需要文档解析器。")

        if kind in {"archive", "binary"}:
            return err(f"Error: {path} 看起来是二进制文件，拒绝读取。")

        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return err(f"Error: {path} 不是有效的 UTF-8 文本")

        lines = text.splitlines()
        total = len(lines)

        if total == 0:
            return ok(f"# {path} (empty file)")

        start = max(1, start_line)

        if start > total:
            return err(
                f"Error: start_line={start} 超出文件范围，"
                f"文件共有 {total} 行。"
            )

        if end_line is None:
            end = min(total, start + DEFAULT_WINDOW_LINES - 1)
        else:
            end = min(total, end_line)

        if end < start:
            return err(f"Error: end_line={end} 小于 start_line={start}")

        selected = lines[start - 1:end]
        output = [f"# {path} ({total} lines, showing {start}-{end})"]
        truncated_lines = []

        for line_no, line in enumerate(selected, start=start):
            safe_line, was_truncated = truncate_line(line)
            if was_truncated:
                truncated_lines.append(line_no)
            output.append(f"{line_no:>5}  {safe_line}")

        if end < total:
            output.append(
                f"\n# More: {total - end} lines remain. "
                f"Continue with start_line={end + 1}."
            )

        if truncated_lines:
            values = ", ".join(str(n) for n in truncated_lines)
            output.append(f"\n# Note: long lines truncated: {values}")

        return ok("\n".join(output))


class ListDirTool(Tool):
    name = "list_dir"
    description = (
        "列出指定目录下的文件和子目录。"
        "当不知道文件路径，需要先查看目录结构时使用。"
    )
    schema = {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": (
                "列出指定目录下的文件和子目录。"
                "当不知道文件路径，需要先查看目录结构时使用。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要查看的目录，默认是当前目录",
                    }
                },
            },
        },
    }

    def __call__(self, *, path: str = ".") -> dict:
        target = Path(path)

        if not target.exists():
            return err(f"Error: 目录不存在 {path}")

        if not target.is_dir():
            return err(f"Error: {path} 不是目录")

        try:
            items = sorted(target.iterdir())
        except Exception as exc:
            return err(f"Error: {type(exc).__name__}: {exc}")

        return ok("\n".join(
            item.name + ("/" if item.is_dir() else "")
            for item in items
        ))
