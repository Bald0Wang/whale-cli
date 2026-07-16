"""Learner profile: the narrow, explicit input for personalization."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .store import LearningStore


REQUIRED_PROFILE_FIELDS = ("level", "goal", "weekly_hours")


class LearnerProfileService:
    def __init__(self, store: LearningStore) -> None:
        self.store = store

    def get(self) -> dict[str, Any]:
        return self.store.read()["profile"]

    def missing_fields(self) -> list[str]:
        profile = self.get()
        return [field for field in REQUIRED_PROFILE_FIELDS if not profile.get(field)]

    def update(
        self,
        *,
        level: str,
        goal: str,
        weekly_hours: float,
        topics: list[str] | None = None,
        learning_style: str = "",
    ) -> dict[str, Any]:
        if not level.strip() or not goal.strip():
            raise ValueError("level and goal cannot be empty")
        if weekly_hours <= 0 or weekly_hours > 80:
            raise ValueError("weekly_hours must be between 0 and 80")
        normalized_topics = sorted({topic.strip() for topic in topics or [] if topic.strip()})

        def apply(state: dict[str, Any]) -> None:
            state["profile"] = {
                "level": level.strip(),
                "goal": goal.strip(),
                "weekly_hours": weekly_hours,
                "topics": normalized_topics,
                "learning_style": learning_style.strip(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        return self.store.update(apply)["profile"]
