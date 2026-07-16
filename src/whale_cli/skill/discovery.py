from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ..context.project import find_project_root
from .models import Skill, SkillRoot


def builtin_skills_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "skills"


def default_skill_roots(work_dir: str | os.PathLike[str] | None = None) -> List[SkillRoot]:
    root = find_project_root(work_dir)
    home = Path.home()
    candidates = [
        SkillRoot(root / ".whale_cli" / "skills", "project"),
        SkillRoot(root / ".agents" / "skills", "project"),
        SkillRoot(home / ".whale_cli" / "skills", "user"),
        SkillRoot(home / ".agents" / "skills", "user"),
        SkillRoot(builtin_skills_dir(), "builtin"),
    ]
    return [r for r in candidates if r.path.is_dir()]


def _parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    rest = text[text.find("\n", end + 4) + 1 :]
    data: Dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data, rest


def _fallback_description(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return " ".join(stripped.split())[:160]
    return ""


def _skill_from_file(path: Path, scope: str) -> Skill:
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    name = meta.get("name") or path.parent.name
    description = meta.get("description") or _fallback_description(body)
    return Skill(name=name, description=description, path=path, scope=scope)  # type: ignore[arg-type]


def discover_skills(roots: Iterable[SkillRoot] | None = None) -> List[Skill]:
    """Discover skills, keeping the first occurrence by name.

    Roots are expected to be ordered highest priority first. The default order
    is project > user > builtin.
    """
    found: Dict[str, Skill] = {}
    for root in roots or default_skill_roots():
        for skill_file in sorted(root.path.glob("*/SKILL.md")):
            try:
                skill = _skill_from_file(skill_file, root.scope)
            except OSError:
                continue
            if skill.name not in found:
                found[skill.name] = skill
    return list(found.values())


def format_skills_for_prompt(skills: Iterable[Skill]) -> str:
    lines = []
    for skill in skills:
        desc = f": {skill.description}" if skill.description else ""
        lines.append(f"- {skill.name} ({skill.scope}){desc}")
    return "\n".join(lines)


def read_skill_text(name: str, roots: Iterable[SkillRoot] | None = None) -> str:
    for skill in discover_skills(roots):
        if skill.name == name:
            return skill.path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Skill not found: {name}")
