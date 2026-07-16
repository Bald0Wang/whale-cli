from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from typing import List

from ..tools.base import Tool


def default_plugins_dir() -> Path:
    return Path(os.getcwd()) / ".whale_cli" / "plugins"


def _load_attr(entry: str, base_dir: Path):
    module_name, attr = entry.split(":", 1)
    module_path = base_dir / module_name
    spec = importlib.util.spec_from_file_location(f"whale_cli_plugin_{base_dir.name}_{module_path.stem}", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load plugin module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, attr)


def load_plugin_tools(plugins_dir: str | Path | None = None) -> List[Tool]:
    """Load project-local plugin tools.

    Each plugin directory may contain:

        plugin.json  {"entry": "tool.py:EchoTool"}
        tool.py      class EchoTool(Tool): ...
    """
    root = Path(plugins_dir) if plugins_dir else default_plugins_dir()
    if not root.is_dir():
        return []
    tools: List[Tool] = []
    for plugin_dir in sorted(root.iterdir()):
        manifest = plugin_dir / "plugin.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            cls = _load_attr(str(data["entry"]), plugin_dir)
            tool = cls()
            if not isinstance(tool, Tool):
                raise TypeError(f"{cls!r} is not a Tool")
        except Exception:
            continue
        tools.append(tool)
    return tools
