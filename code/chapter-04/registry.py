"""第 4 章 · Tool 基类、ok/err 返回协议与 Toolset 注册表。

和 ch03 的差异：ok() 支持 changed_files 参数，Write/Edit 用来报告修改了哪些文件。
"""
from typing import Any


class Tool:
    """工具基类：每个工具继承它，带上 schema 和执行逻辑。"""

    name: str = ""
    description: str = ""
    schema: dict = {}

    def __call__(self, **kwargs) -> dict:
        raise NotImplementedError


def ok(
    stdout: str = "",
    changed_files: list[str] | None = None,
) -> dict:
    return {
        "stdout": stdout,
        "stderr": "",
        "exit_code": 0,
        "changed_files": changed_files or [],
    }


def err(stderr: str) -> dict:
    return {"stdout": "", "stderr": stderr, "exit_code": 1}


def _validate_args(
    args: dict,
    schema: dict,
) -> str | None:
    parameters = schema["function"]["parameters"]
    properties = parameters.get("properties", {})
    required = parameters.get("required", [])

    for field in required:
        if field not in args:
            return f"缺少必需参数 '{field}'"

    for field, value in args.items():
        definition = properties.get(field)

        if definition is None:
            available = ", ".join(properties.keys())
            return (
                f"未知参数 '{field}'。"
                f"可用参数：{available}"
            )

        expected = definition.get("type")

        if expected == "string" and not isinstance(value, str):
            return f"参数 '{field}' 应为 string"

        if expected == "integer" and not isinstance(value, int):
            return f"参数 '{field}' 应为 integer"

        if expected == "boolean" and not isinstance(value, bool):
            return f"参数 '{field}' 应为 boolean"

    return None


class Toolset:
    """工具注册表：管理所有工具的注册、查找和执行。"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        if tool.name in self._tools:
            raise ValueError(f"工具名重复注册：{tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def all_schemas(self) -> list[dict]:
        return [t.schema for t in self._tools.values()]

    def run(self, name: str, args: dict) -> dict:
        tool = self._tools.get(name)

        if tool is None:
            available = ", ".join(self._tools.keys())
            return err(
                f"Error: 工具 '{name}' 不存在。"
                f"当前可用工具：{available}"
            )

        error = _validate_args(args, tool.schema)

        if error:
            return err(f"Error: {name} 参数校验失败：{error}")

        try:
            return tool(**args)
        except Exception as exc:
            return err(
                f"Error: {name} 执行失败："
                f"{type(exc).__name__}: {exc}"
            )
