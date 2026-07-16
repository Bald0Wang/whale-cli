"""A small, inspectable spaced-repetition scheduler for learned concepts."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .store import LearningStore
from ..storage.session_store import SessionStore


_INTERVALS = (1, 3, 7, 14, 30, 60)


class ReviewScheduler:
    def __init__(self, store: LearningStore) -> None:
        self.store = store

    def review(self, *, concept_id: str, rating: int, today: date | None = None) -> dict[str, Any]:
        if not 0 <= rating <= 5:
            raise ValueError("rating must be between 0 and 5")
        current_day = today or date.today()

        def apply(state: dict[str, Any]) -> None:
            if concept_id not in state["knowledge_nodes"]:
                raise ValueError(f"unknown concept: {concept_id}")
            previous = state["reviews"].get(concept_id, {"stage": 0, "attempts": 0})
            stage = 0 if rating < 3 else min(int(previous["stage"]) + 1, len(_INTERVALS) - 1)
            state["reviews"][concept_id] = {
                "concept_id": concept_id,
                "rating": rating,
                "stage": stage,
                "attempts": int(previous["attempts"]) + 1,
                "reviewed_on": current_day.isoformat(),
                "due_on": (current_day + timedelta(days=_INTERVALS[stage])).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        state = self.store.update(apply)
        schedule = self.schedule(today=current_day)
        self._write_outputs(schedule)
        return state["reviews"][concept_id]

    def due(self, today: date | None = None) -> list[dict[str, Any]]:
        current_day = today or date.today()
        state = self.store.read()
        due_cards = []
        for card in state["reviews"].values():
            due_on = str(card.get("due_on", ""))
            if due_on and date.fromisoformat(due_on) <= current_day:
                node = state["knowledge_nodes"].get(card["concept_id"], {})
                due_cards.append({**card, "title": node.get("title", card["concept_id"])})
        return sorted(due_cards, key=lambda card: card["due_on"])

    def sync_from_conversations(
        self,
        *,
        session_store: SessionStore | None = None,
        force: bool = False,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Seed review cards from explicit mentions in persisted chat records.

        This is deliberately lexical rather than model-driven: only titles or
        IDs already owned by ``KnowledgeMap`` can become cards, and no rating
        is inferred from a conversation.
        """
        current_day = today or date.today()
        state = self.store.read()
        last_scan = str(state["review_sync"].get("last_scanned_on", ""))
        if not force and last_scan == current_day.isoformat():
            schedule = self.schedule(today=current_day)
            self._write_outputs(schedule)
            return {"scanned": False, "reason": "already_scanned_today", **schedule}

        source = session_store or SessionStore(str(self.store.workspace / ".whale_cli"))
        matches: dict[str, dict[str, Any]] = {}
        scanned_sessions = 0
        scanned_messages = 0
        for session in source.list_sessions(limit=80):
            scanned_sessions += 1
            for message in source.load_messages(session.session_id, limit=400):
                if message.get("role") not in {"user", "assistant"}:
                    continue
                content = str(message.get("content", "")).casefold()
                if not content:
                    continue
                scanned_messages += 1
                for node_id, node in state["knowledge_nodes"].items():
                    title = str(node.get("title", "")).casefold()
                    if (title and title in content) or node_id.casefold() in content:
                        record = matches.setdefault(node_id, {"hits": 0, "last_seen_at": "", "session_ids": set()})
                        record["hits"] += 1
                        record["session_ids"].add(session.session_id)
                        timestamp = str(message.get("timestamp", ""))
                        if timestamp > record["last_seen_at"]:
                            record["last_seen_at"] = timestamp

        scanned_at = datetime.now(timezone.utc).isoformat()

        def apply(current: dict[str, Any]) -> None:
            for node_id, signal in matches.items():
                existing = current["reviews"].get(node_id)
                if existing is None:
                    current["reviews"][node_id] = {
                        "concept_id": node_id,
                        "rating": None,
                        "stage": 0,
                        "attempts": 0,
                        "reviewed_on": "",
                        "due_on": current_day.isoformat(),
                        "created_from": "conversation_scan",
                        "conversation_hits": signal["hits"],
                        "last_seen_at": signal["last_seen_at"],
                        "updated_at": scanned_at,
                    }
                else:
                    existing["conversation_hits"] = signal["hits"]
                    existing["last_seen_at"] = signal["last_seen_at"]
                    existing["updated_at"] = scanned_at
            current["review_sync"] = {
                "last_scanned_on": current_day.isoformat(),
                "last_scanned_at": scanned_at,
                "scanned_sessions": scanned_sessions,
                "scanned_messages": scanned_messages,
                "matched_concepts": sorted(matches),
            }

        self.store.update(apply)
        schedule = self.schedule(today=current_day)
        self._write_outputs(schedule)
        return {"scanned": True, "matched_concepts": sorted(matches), **schedule}

    def feedback(self, *, today: date | None = None) -> dict[str, Any]:
        """Write a learner-readable Markdown checkpoint from the current schedule."""
        schedule = self.schedule(today=today)
        self._write_feedback(schedule)
        return {
            "path": schedule["feedback_path"],
            "content": self.render_feedback(schedule),
            "due_count": len(schedule["due"]),
        }

    def detail(
        self,
        concept_id: str,
        *,
        session_store: SessionStore | None = None,
        max_materials: int = 6,
        today: date | None = None,
    ) -> dict[str, Any]:
        """Return local notes, graph links, and short matching chat excerpts."""
        if max_materials < 1:
            raise ValueError("max_materials must be positive")
        state = self.store.read()
        node = state["knowledge_nodes"].get(concept_id)
        if node is None:
            raise ValueError(f"unknown concept: {concept_id}")

        related = []
        for edge in state["knowledge_links"]:
            if edge["source"] == concept_id:
                other = state["knowledge_nodes"].get(edge["target"], {})
                related.append({"direction": "outgoing", "relation": edge["relation"], "title": other.get("title", edge["target"]), "concept_id": edge["target"]})
            elif edge["target"] == concept_id:
                other = state["knowledge_nodes"].get(edge["source"], {})
                related.append({"direction": "incoming", "relation": edge["relation"], "title": other.get("title", edge["source"]), "concept_id": edge["source"]})

        source = session_store or SessionStore(str(self.store.workspace / ".whale_cli"))
        title = str(node.get("title", "")).casefold()
        needle = concept_id.casefold()
        materials = []
        for session in source.list_sessions(limit=80):
            for message in source.load_messages(session.session_id, limit=400):
                if message.get("role") not in {"user", "assistant"}:
                    continue
                content = str(message.get("content", "")).strip()
                normalized = content.casefold()
                if not content or (title not in normalized and needle not in normalized):
                    continue
                excerpt = content if len(content) <= 900 else content[:900].rstrip() + "\n\n[片段已截断]"
                materials.append(
                    {
                        "session_id": session.session_id,
                        "session_title": session.title or "未命名会话",
                        "timestamp": str(message.get("timestamp", "")),
                        "role": str(message.get("role", "assistant")),
                        "content": excerpt,
                    }
                )
        materials.sort(key=lambda item: item["timestamp"], reverse=True)
        review = state["reviews"].get(concept_id, {})
        return {
            "concept_id": concept_id,
            "title": node["title"],
            "kind": node.get("kind", "concept"),
            "mastery": node.get("mastery", 0),
            "summary": node.get("note", "") or "知识地图中还没有补充摘要；可在对话中要求 Whale 记录你的理解。",
            "related": related,
            "materials": materials[:max_materials],
            "material_count": len(materials),
            "review": review,
            "memory": self._memory_curve(review, today=today),
        }

    def _memory_curve(self, review: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
        """Provide a transparent teaching estimate, never a memory measurement."""
        current_day = today or date.today()
        stage = min(max(int(review.get("stage", 0)), 0), len(_INTERVALS) - 1)
        interval_days = _INTERVALS[stage]
        reviewed_on = str(review.get("reviewed_on", ""))
        rating = review.get("rating")
        last_review = None
        try:
            last_review = date.fromisoformat(reviewed_on) if reviewed_on else None
        except ValueError:
            last_review = None

        has_rating = isinstance(rating, int) and 0 <= rating <= 5 and last_review is not None
        elapsed_days = max((current_day - last_review).days, 0) if last_review else 0
        horizon_days = max(7, interval_days * 2, elapsed_days + 2)
        personal_points = [
            {"day": day, "retention": round(100 * (0.5 ** (day / interval_days)), 1)}
            for day in range(horizon_days + 1)
        ]
        reference_days = (0, 1, 3, 7, 14, 30)
        reference_points = [
            {"day": day, "retention": round(100 * (0.5 ** day), 1)}
            for day in reference_days
        ]
        due_on = str(review.get("due_on", ""))
        return {
            "mode": "estimate" if has_rating else "baseline",
            "last_rating": rating if has_rating else None,
            "last_reviewed_on": last_review.isoformat() if last_review else "",
            "next_review_on": due_on,
            "interval_days": interval_days,
            "elapsed_days": elapsed_days if has_rating else None,
            "current_retention": personal_points[min(elapsed_days, horizon_days)]["retention"] if has_rating else None,
            "today_day": min(elapsed_days, horizon_days) if has_rating else None,
            "horizon_days": horizon_days,
            "personal_points": personal_points,
            "reference_points": reference_points,
            "disclaimer": "这是按复习间隔和你自己输入的评分生成的教学估计，不是对真实记忆能力的测量。",
        }

    def schedule(self, *, today: date | None = None) -> dict[str, Any]:
        """Render the current review table from the local JSON state."""
        current_day = today or date.today()
        state = self.store.read()
        cards: list[dict[str, Any]] = []
        for concept_id, card in state["reviews"].items():
            due_on = str(card.get("due_on", ""))
            if not due_on:
                continue
            node = state["knowledge_nodes"].get(concept_id, {})
            due_day = date.fromisoformat(due_on)
            cards.append(
                {
                    **card,
                    "title": node.get("title", concept_id),
                    "mastery": node.get("mastery", 0),
                    "status": "due" if due_day <= current_day else "upcoming",
                    "days_until_due": (due_day - current_day).days,
                }
            )
        cards.sort(key=lambda card: (card["due_on"], card["title"]))
        return {
            "version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "table_path": ".whale_cli/learning/review-schedule.json",
            "feedback_path": ".whale_cli/learning/review-feedback.md",
            "last_sync": state["review_sync"],
            "due": [card for card in cards if card["status"] == "due"],
            "upcoming": [card for card in cards if card["status"] == "upcoming"],
            "cards": cards,
        }

    def render_feedback(self, schedule: dict[str, Any]) -> str:
        """Render a compact Markdown checklist without inferring learner ratings."""
        generated_on = str(schedule.get("generated_at", ""))[:10] or date.today().isoformat()
        due = list(schedule.get("due", []))
        upcoming = list(schedule.get("upcoming", []))
        lines = [
            "# Whale 间隔复习反馈",
            "",
            f"生成日期：{generated_on}",
            "",
            "这是一张本地复习清单。先不看笔记回忆，再由你自己记录 0 到 5 的评分。",
            "",
            "## 今日复习",
            "",
        ]
        if due:
            for card in due:
                lines.extend(
                    [
                        f"- [ ] {card['title']}",
                        f"  - 当前阶段：{int(card.get('stage', 0)) + 1}；历史评分：{card.get('rating') if card.get('rating') is not None else '未评分'}。",
                        "  - 回忆提示：不用笔记解释这个概念的用途、关键步骤，以及它和已学内容的关系。",
                        f"  - 评分后可对 Whale 说：`我刚复习了 {card['title']}，请记录回忆评分 4。`",
                    ]
                )
        else:
            lines.append("- [x] 今天没有到期卡片。可从后续安排中任选一个概念做预习，或继续学习路线。")

        lines.extend(["", "## 后续安排", ""])
        if upcoming:
            for card in upcoming:
                lines.append(f"- [ ] {card['title']}：{card['due_on']}（{card['days_until_due']} 天后）")
        else:
            lines.append("- 暂无后续安排。先在知识地图中记录概念，或检索本地聊天记录。")

        lines.extend(
            [
                "",
                "## 说明",
                "",
                "- 评分 0 到 2 会回到 1 天后的短间隔；评分 3 到 5 会进入下一阶段。",
                "- 勾选框用于你的笔记管理；真正的复习完成以 Whale 中记录的回忆评分为准。",
                f"- 机器可读复习表：`{schedule['table_path']}`。",
            ]
        )
        return "\n".join(lines) + "\n"

    def _write_outputs(self, schedule: dict[str, Any]) -> None:
        self._write_table(schedule)
        self._write_feedback(schedule)

    def _write_table(self, schedule: dict[str, Any]) -> None:
        target = self.store.path.parent / "review-schedule.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)

    def _write_feedback(self, schedule: dict[str, Any]) -> None:
        target = self.store.path.parent / "review-feedback.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(self.render_feedback(schedule), encoding="utf-8")
        temporary.replace(target)
