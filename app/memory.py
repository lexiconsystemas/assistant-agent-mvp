from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Literal
import threading
import uuid

Role = Literal["user", "assistant"]


@dataclass
class Message:
    role: Role
    content: str
    ts: str  # ISO timestamp


@dataclass
class Task:
    id: str
    title: str
    completed: bool
    ts: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InMemorySessionStore:
    """
    MVP memory:
    - per-session message history
    - per-session tasks
    - persists only while server runs
    - thread-safe for dev via a lock
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, List[Message]] = {}
        self._tasks: Dict[str, List[Task]] = {}

    # -------- chat history --------
    def get_history(self, session_id: str, limit: int = 12) -> List[Message]:
        with self._lock:
            msgs = self._sessions.get(session_id, [])
            return msgs[-limit:]

    def append(self, session_id: str, role: Role, content: str) -> None:
        with self._lock:
            self._sessions.setdefault(session_id, []).append(
                Message(role=role, content=content, ts=_now_iso())
            )

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
            self._tasks.pop(session_id, None)

    def snapshot(self, session_id: str, limit: int = 50) -> List[Message]:
        return self.get_history(session_id=session_id, limit=limit)

    # -------- tasks --------
    def add_task(self, session_id: str, title: str) -> Task:
        with self._lock:
            task = Task(
                id=str(uuid.uuid4()),
                title=title.strip(),
                completed=False,
                ts=_now_iso(),
            )
            self._tasks.setdefault(session_id, []).append(task)
            return task

    def list_tasks(self, session_id: str) -> List[Task]:
        with self._lock:
            return list(self._tasks.get(session_id, []))

    def complete_task(self, session_id: str, task_id: str) -> bool:
        with self._lock:
            for task in self._tasks.get(session_id, []):
                if task.id == task_id:
                    task.completed = True
                    return True
            return False


# Singleton store instance
store = InMemorySessionStore()
