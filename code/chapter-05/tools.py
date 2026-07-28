"""第 5 章 · 搜文件：Glob 与 Grep。

和 ch04 的差异：
- 新增 GlobTool：按文件名模式搜索，跳过 IGNORE_DIRS
- 新增 GrepTool：正则搜索文件内容，优先用 ripgrep，回退纯 Python
- 搜索结果有全局上限（MAX_GLOB_RESULTS / MAX_GREP_RESULTS）并告知截断
"""
import re
import shutil
import subprocess
from pathlib import Path

from registry import Tool, ok, err
from file_utils import (
    atomic_write_text,
    find_closest_excerpt,
    find_match_lines,
)


# ── 常量 ──

DEFAULT_WINDOW_LINES = 200
MAX_LINE_CHARS = 2000
MAX_GLOB_RESULTS = 500
MAX_GREP_RESULTS = 200

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

IGNORE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}


def should_ignore(
    file_path: Path,
    root: Path,
) -> bool:
    relative = file_path.relative_to(root)

    return any(
        part in IGNORE_DIRS
        for part in relative.parts
    )


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


# ── ReadFile（ch03 版本）──

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


# ── ListDir（ch02 版本）──

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


# ── WriteFile（ch04 版本）──

class WriteFileTool(Tool):
    name = "write_file"
    description = (
        "创建新的 UTF-8 文本文件，"
        "或有意替换整个文件。"
        "局部修改已有文件时应使用 edit_file。"
        "覆盖已有文件必须设置 overwrite=true。"
    )
    schema = {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "创建新的 UTF-8 文本文件，"
                "或有意替换整个文件。"
                "局部修改已有文件时应使用 edit_file。"
                "覆盖已有文件必须设置 overwrite=true。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目标文件路径",
                    },
                    "content": {
                        "type": "string",
                        "description": "文件的完整新内容",
                    },
                    "overwrite": {
                        "type": "boolean",
                        "description": (
                            "是否允许覆盖已有文件，"
                            "默认是 false"
                        ),
                    },
                },
                "required": [
                    "path",
                    "content",
                ],
            },
        },
    }

    def __call__(
        self,
        *,
        path: str,
        content: str,
        overwrite: bool = False,
    ) -> dict:
        file_path = Path(path)
        existed_before = file_path.exists()

        if existed_before:
            if not file_path.is_file():
                return err(f"{path} 不是普通文件。")

            if not overwrite:
                return err(
                    f"{path} 已经存在。"
                    "局部修改请使用 edit_file；"
                    "如果确实要替换整个文件，"
                    "请设置 overwrite=true。"
                )

        try:
            atomic_write_text(file_path, content)
        except Exception as exc:
            return err(
                f"写入 {path} 失败："
                f"{type(exc).__name__}: {exc}"
            )

        action = "Replaced" if existed_before else "Created"

        return ok(
            f"{action} {path}: "
            f"{len(content)} characters",
            changed_files=[path],
        )


# ── EditFile（ch04 版本）──

class EditFileTool(Tool):
    name = "edit_file"
    description = (
        "在已有 UTF-8 文本文件中执行局部替换。"
        "old_string 必须与当前文件精确匹配，"
        "并且只能出现一次。"
        "请从最近一次 Read 的结果中复制准确内容，"
        "并包含足够上下文使匹配唯一。"
    )
    schema = {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "在已有 UTF-8 文本文件中执行局部替换。"
                "old_string 必须与当前文件精确匹配，"
                "并且只能出现一次。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "要修改的文件路径",
                    },
                    "old_string": {
                        "type": "string",
                        "description": (
                            "文件中当前存在的原始内容；"
                            "必须精确且唯一"
                        ),
                    },
                    "new_string": {
                        "type": "string",
                        "description": "替换后的新内容",
                    },
                },
                "required": [
                    "path",
                    "old_string",
                    "new_string",
                ],
            },
        },
    }

    def __call__(
        self,
        *,
        path: str,
        old_string: str,
        new_string: str,
    ) -> dict:
        file_path = Path(path)

        if not file_path.exists():
            return err(f"文件不存在：{path}")

        if not file_path.is_file():
            return err(f"{path} 不是普通文件")

        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return err(
                f"{path} 不是 UTF-8 文本，"
                "不能使用 edit_file 修改。"
            )

        count = text.count(old_string)

        if count == 0:
            excerpt = find_closest_excerpt(text, old_string)

            message = (
                f"old_string 在 {path} "
                "中未找到。"
            )

            if excerpt:
                message += (
                    "\n当前文件中较接近的位置：\n"
                    + excerpt
                )

            return err(message)

        if count > 1:
            locations = find_match_lines(text, old_string)

            values = ", ".join(
                str(line) for line in locations[:10]
            )

            return err(
                f"old_string 在 {path} "
                f"中匹配到 {count} 处。"
                f"起始行：{values}。"
                "请加入更多上下文，使匹配唯一。"
            )

        new_text = text.replace(old_string, new_string, 1)

        try:
            atomic_write_text(file_path, new_text)
        except Exception as exc:
            return err(
                f"修改 {path} 失败："
                f"{type(exc).__name__}: {exc}"
            )

        old_lines = old_string.count("\n") + 1
        new_lines = new_string.count("\n") + 1

        return ok(
            f"Applied edit to {path}: "
            f"{old_lines} lines -> "
            f"{new_lines} lines",
            changed_files=[path],
        )


# ── Glob（本章新增）──

class GlobTool(Tool):
    name = "glob"
    description = "按文件名模式搜索文件路径。"
    schema = {
        "type": "function",
        "function": {
            "name": "glob",
            "description": "按文件名模式搜索文件路径。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "glob 模式，如 **/*.ts",
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索起始目录，默认当前目录",
                    },
                },
                "required": ["pattern"],
            },
        },
    }

    def __call__(
        self, *, pattern: str, path: str = "."
    ) -> dict:
        root = Path(path).resolve()

        if not root.exists():
            return err(f"Error: 路径不存在：{path}")

        if not root.is_dir():
            return err(f"Error: {path} 不是目录")

        matches = []

        for file_path in sorted(root.glob(pattern)):
            if not file_path.is_file():
                continue

            if should_ignore(file_path, root):
                continue

            matches.append(
                str(file_path.relative_to(root))
            )

            if len(matches) >= MAX_GLOB_RESULTS:
                break

        if not matches:
            return ok(f"没有文件匹配模式：{pattern}")

        output = "\n".join(matches)

        if len(matches) >= MAX_GLOB_RESULTS:
            output += (
                f"\n\n# 显示前 {MAX_GLOB_RESULTS} 条匹配。"
                "还有更多结果，请缩小 path 或 pattern。"
            )

        return ok(output)


# ── Grep（本章新增）──

def grep_with_ripgrep(
    pattern: str,
    path: str,
    glob_pattern: str | None,
    case_insensitive: bool,
) -> str | None:
    rg = shutil.which("rg")

    if rg is None:
        return None

    command = [
        rg,
        "--no-heading",
        "--line-number",
        "--color=never",
    ]

    if case_insensitive:
        command.append("--ignore-case")

    if glob_pattern:
        command.extend([
            "--glob",
            glob_pattern,
        ])

    command.extend([
        pattern,
        path,
    ])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return (
            "Error: 搜索超过 20 秒。"
            "请缩小搜索目录、文件类型或关键词范围。"
        )

    if result.returncode == 0:
        return result.stdout

    if result.returncode == 1:
        return "没有匹配结果"

    return None


def grep_with_python(
    pattern: str,
    root: Path,
    glob_pattern: str,
    case_insensitive: bool,
) -> str:
    flags = re.IGNORECASE if case_insensitive else 0

    try:
        regex = re.compile(pattern, flags)
    except re.error as exc:
        return f"Error: 正则表达式无效：{exc}"

    matches = []

    for file_path in sorted(root.glob(glob_pattern)):
        if not file_path.is_file():
            continue

        if should_ignore(file_path, root):
            continue

        try:
            text = file_path.read_text(
                encoding="utf-8"
            )
        except (
            UnicodeDecodeError,
            PermissionError,
            OSError,
        ):
            continue

        for line_no, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            if regex.search(line):
                relative = file_path.relative_to(root)
                matches.append(
                    f"{relative}:{line_no}:"
                    f"{line.rstrip()}"
                )

                if len(matches) >= MAX_GREP_RESULTS:
                    break

        if len(matches) >= MAX_GREP_RESULTS:
            break

    if not matches:
        return "没有匹配结果"

    return "\n".join(matches)


class GrepTool(Tool):
    name = "grep"
    description = "用正则表达式搜索文件内容。"
    schema = {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "用正则表达式搜索文件内容。",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "搜索关键词或正则表达式",
                    },
                    "path": {
                        "type": "string",
                        "description": "搜索目录，默认当前目录",
                    },
                    "glob": {
                        "type": "string",
                        "description": "文件过滤模式，如 **/*.ts",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "是否忽略大小写",
                    },
                },
                "required": ["pattern"],
            },
        },
    }

    def __call__(
        self,
        *,
        pattern: str,
        path: str = ".",
        glob: str = "**/*",
        case_insensitive: bool = False,
    ) -> dict:
        root = Path(path).resolve()

        if not root.exists():
            return err(f"Error: 路径不存在：{path}")

        result = grep_with_ripgrep(
            pattern, str(root), glob, case_insensitive
        )

        if result is not None:
            lines = result.splitlines()

            if len(lines) > MAX_GREP_RESULTS:
                lines = lines[:MAX_GREP_RESULTS]
                lines.append(
                    f"\n# 显示前 {MAX_GREP_RESULTS} 条匹配。"
                    "还有更多结果，请缩小 path、glob 或 pattern。"
                )

            return ok("\n".join(lines))

        result = grep_with_python(
            pattern, root, glob, case_insensitive
        )

        if result.startswith("Error:"):
            return err(result)

        lines = result.splitlines()

        if len(lines) >= MAX_GREP_RESULTS:
            lines.append(
                f"\n# 显示前 {MAX_GREP_RESULTS} 条匹配。"
                "还有更多结果，请缩小 path、glob 或 pattern。"
            )

        return ok("\n".join(lines))
