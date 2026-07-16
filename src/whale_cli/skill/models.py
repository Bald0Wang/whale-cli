from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SkillScope = Literal["project", "user", "builtin"]


@dataclass(frozen=True)
class SkillRoot:
    path: Path
    scope: SkillScope


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path
    scope: SkillScope
