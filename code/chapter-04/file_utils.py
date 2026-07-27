"""第 4 章 · 文件操作工具函数。

atomic_write_text：原子写入，文件只会处于旧版本或新版本，不会半成品。
find_closest_excerpt：Edit 零匹配时找到最接近的代码片段。
find_match_lines：Edit 多处匹配时返回各起始行号。
"""
import difflib
import os
import tempfile
from pathlib import Path


def atomic_write_text(
    path: Path,
    content: str,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )

    temp_path = Path(temp_name)

    try:
        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())

        os.replace(
            temp_path,
            path,
        )

    except Exception:
        temp_path.unlink(
            missing_ok=True,
        )
        raise


def find_closest_excerpt(
    text: str,
    old_string: str,
) -> str | None:
    file_lines = text.splitlines()
    target = old_string.splitlines()[0].strip()

    normalized = [
        line.strip()
        for line in file_lines
    ]

    matches = difflib.get_close_matches(
        target,
        normalized,
        n=1,
        cutoff=0.35,
    )

    if not matches:
        return None

    matched = matches[0]
    index = normalized.index(matched)

    start = max(0, index - 2)
    end = min(
        len(file_lines),
        index + 3,
    )

    return "\n".join(
        f"{line_no + 1:>5}  "
        f"{file_lines[line_no]}"
        for line_no in range(start, end)
    )


def find_match_lines(
    text: str,
    old_string: str,
) -> list[int]:
    locations = []
    start = 0

    while True:
        index = text.find(
            old_string,
            start,
        )

        if index == -1:
            break

        line_no = (
            text.count("\n", 0, index)
            + 1
        )

        locations.append(line_no)
        start = index + 1

    return locations
