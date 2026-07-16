import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    title: str
    created_at: str
    updated_at: str


class SessionStore:
    """
    Minimal session storage backed by JSON Lines (jsonl).

    Layout:
    - <base_dir>/sessions/index.jsonl
    - <base_dir>/sessions/<session_id>.jsonl

    index.jsonl is append-only. The latest record for a session_id wins.
    """

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.sessions_dir = os.path.join(self.base_dir, "sessions")
        self.index_path = os.path.join(self.sessions_dir, "index.jsonl")
        os.makedirs(self.sessions_dir, exist_ok=True)

        if not os.path.exists(self.index_path):
            # Create an empty index file so reads don't special-case.
            with open(self.index_path, "w", encoding="utf-8") as f:
                f.write("")

    def _session_path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"{session_id}.jsonl")

    @staticmethod
    def _is_valid_session_id(session_id: str) -> bool:
        return len(session_id) == 32 and all(char in "0123456789abcdef" for char in session_id)

    def create_session(self, title: str = "") -> str:
        session_id = uuid.uuid4().hex
        now = _utc_now_iso()
        record = {
            "session_id": session_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }
        self._append_index_record(record)
        # Touch the session file.
        session_path = self._session_path(session_id)
        if not os.path.exists(session_path):
            with open(session_path, "w", encoding="utf-8") as f:
                f.write("")
        return session_id

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        return self._get_session_info(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Permanently remove one session file and hide it from the index."""
        if not self._is_valid_session_id(session_id):
            raise ValueError("invalid session id")
        info = self._get_session_info(session_id)
        if info is None:
            return False
        try:
            os.remove(self._session_path(session_id))
        except FileNotFoundError:
            pass
        self._append_index_record(
            {
                "session_id": info.session_id,
                "title": info.title,
                "created_at": info.created_at,
                "updated_at": _utc_now_iso(),
                "deleted": True,
            }
        )
        return True

    def set_session_title(self, session_id: str, title: str) -> None:
        """
        Update a session title by appending a new index record.
        The latest record for a session_id wins.
        """
        now = _utc_now_iso()
        info = self._get_session_info(session_id)
        if info is None:
            record = {
                "session_id": session_id,
                "title": title,
                "created_at": now,
                "updated_at": now,
            }
        else:
            record = {
                "session_id": info.session_id,
                "title": title,
                "created_at": info.created_at,
                "updated_at": now,
            }
        self._append_index_record(record)

    def touch_session(self, session_id: str) -> None:
        now = _utc_now_iso()
        info = self._get_session_info(session_id)
        if info is None:
            record = {
                "session_id": session_id,
                "title": "",
                "created_at": now,
                "updated_at": now,
            }
        else:
            record = {
                "session_id": info.session_id,
                "title": info.title,
                "created_at": info.created_at,
                "updated_at": now,
            }
        self._append_index_record(record)

    def list_sessions(self, limit: Optional[int] = None) -> List[SessionInfo]:
        latest: Dict[str, Dict[str, Any]] = {}
        with open(self.index_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                sid = rec.get("session_id")
                if not sid:
                    continue
                latest[sid] = rec

        sessions: List[SessionInfo] = []
        for sid, rec in latest.items():
            if rec.get("deleted"):
                continue
            sessions.append(
                SessionInfo(
                    session_id=sid,
                    title=rec.get("title", "") or "",
                    created_at=rec.get("created_at", "") or "",
                    updated_at=rec.get("updated_at", "") or rec.get("created_at", "") or "",
                )
            )

        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        if limit is not None:
            sessions = sessions[:limit]
        return sessions

    def get_latest_session_id(self) -> Optional[str]:
        sessions = self.list_sessions(limit=1)
        if not sessions:
            return None
        return sessions[0].session_id

    def load_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        path = self._session_path(session_id)
        if not os.path.exists(path):
            return []

        messages: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except Exception:
                    continue
                if isinstance(msg, dict):
                    messages.append(msg)

        if limit is not None:
            messages = messages[-limit:]
        return messages

    def append_message(self, session_id: str, message: Dict[str, Any]) -> None:
        self.touch_session(session_id)
        path = self._session_path(session_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False))
            f.write("\n")

    def _append_index_record(self, record: Dict[str, Any]) -> None:
        with open(self.index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False))
            f.write("\n")

    def _get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        # We keep index append-only; to get the latest record, scan and pick the last match.
        last: Optional[Dict[str, Any]] = None
        with open(self.index_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("session_id") == session_id:
                    last = rec
        if last is None:
            return None
        if last.get("deleted"):
            return None
        return SessionInfo(
            session_id=session_id,
            title=last.get("title", "") or "",
            created_at=last.get("created_at", "") or "",
            updated_at=last.get("updated_at", "") or last.get("created_at", "") or "",
        )
