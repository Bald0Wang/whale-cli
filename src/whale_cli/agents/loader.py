from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class AgentSpec:
    name: str
    system_prompt_path: Path
    tools: List[str]


def default_agent_dir() -> Path:
    return Path(__file__).resolve().parent / "default"


def _parse_simple_yaml(path: Path) -> Dict[str, object]:
    """Parse the tiny YAML subset used by Whale CLI agent specs."""
    data: Dict[str, object] = {}
    current_list: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_list:
            cast_list = data.setdefault(current_list, [])
            if isinstance(cast_list, list):
                cast_list.append(stripped[2:].strip())
            continue
        current_list = None
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = value.strip('"').strip("'")
        else:
            data[key] = []
            current_list = key
    return data


def load_agent_spec(agent_file: str | Path | None = None) -> AgentSpec:
    path = Path(agent_file) if agent_file else default_agent_dir() / "agent.yaml"
    data = _parse_simple_yaml(path)
    system_prompt = str(data.get("system_prompt") or "system.md")
    tools = data.get("tools") or []
    if not isinstance(tools, list):
        tools = []
    return AgentSpec(
        name=str(data.get("name") or "default"),
        system_prompt_path=(path.parent / system_prompt).resolve(),
        tools=[str(t) for t in tools],
    )


def render_system_prompt(spec: AgentSpec, args: Dict[str, str]) -> str:
    text = spec.system_prompt_path.read_text(encoding="utf-8")
    for key, value in args.items():
        text = text.replace("{{ " + key + " }}", value)
        text = text.replace("{{" + key + "}}", value)
    return text.strip() + "\n"
