from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Literal
import threading

Role = Literal["user", "assistant"]

@dataclass
class Message:
    role: Role
    content: str
    ts: str  # ISO timestamp


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemorySessionStore:
    """
    MVP memory:
    - per-session message history
    - persists only while server runs
    - thread-safe for dev via a lock
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, List[Message]] = {}

    def get_history(self, session_id: str, limit: int = 12) -> List[Message]:
        with self._lock:
            msgs = self._sessions.get(session_id, [])
            return msgs[-limit:]

    def append(self, session_id: str, role: Role, content: str) -> None:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = []
            self._sessions[session_id].append(
                Message(role=role, content=content, ts=_now_iso())
            )

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def snapshot(self, session_id: str, limit: int = 50) -> List[Message]:
        return self.get_history(session_id=session_id, limit=limit)


# Singleton store instance
store = InMemorySessionStore()
