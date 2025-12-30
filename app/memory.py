from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
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


@dataclass
class Reminder:
    id: str
    text: str
    due_ts: str  # ISO timestamp
    completed: bool
    ts: str


@dataclass
class CheckIn:
    id: str
    mood: str
    energy: int
    focus: int
    note: str
    ts: str


@dataclass
class OutboundMessage:
    id: str
    text: str
    reason: str
    ts: str
    delivered: bool
    attempts: int


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
        self._reminders: Dict[str, List[Reminder]] = {}
        self._checkins: Dict[str, List[CheckIn]] = {}
        self._outbox: Dict[str, List[OutboundMessage]] = {}

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
            self._reminders.pop(session_id, None)
            self._checkins.pop(session_id, None)
            self._outbox.pop(session_id, None)

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

    # -------- reminders --------
    def add_reminder(self, session_id: str, text: str, due_ts: str | None = None) -> Reminder:
        with self._lock:
            if due_ts is None:
                due_ts = (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat()
            reminder = Reminder(
                id=str(uuid.uuid4()),
                text=text.strip(),
                due_ts=due_ts,
                completed=False,
                ts=_now_iso(),
            )
            self._reminders.setdefault(session_id, []).append(reminder)
            return reminder

    def list_reminders(self, session_id: str) -> List[Reminder]:
        with self._lock:
            return list(self._reminders.get(session_id, []))

    def complete_reminder(self, session_id: str, reminder_id: str) -> bool:
        with self._lock:
            for r in self._reminders.get(session_id, []):
                if r.id == reminder_id:
                    r.completed = True
                    return True
            return False

    # -------- checkins --------
    def add_checkin(self, session_id: str, mood: str, energy: int, focus: int, note: str) -> CheckIn:
        with self._lock:
            chk = CheckIn(
                id=str(uuid.uuid4()),
                mood=mood,
                energy=int(energy),
                focus=int(focus),
                note=note or "",
                ts=_now_iso(),
            )
            self._checkins.setdefault(session_id, []).append(chk)
            return chk

    def list_checkins(self, session_id: str, limit: int = 7) -> List[CheckIn]:
        with self._lock:
            lst = list(self._checkins.get(session_id, []))
            return lst[-limit:]

    # -------- outbox --------
    def add_outbox(self, session_id: str, text: str, reason: str) -> OutboundMessage:
        with self._lock:
            msg = OutboundMessage(
                id=str(uuid.uuid4()),
                text=text,
                reason=reason,
                ts=_now_iso(),
                delivered=False,
                attempts=0,
            )
            self._outbox.setdefault(session_id, []).append(msg)
            return msg

    def list_outbox(self, session_id: str, limit: int = 20) -> List[OutboundMessage]:
        with self._lock:
            lst = list(self._outbox.get(session_id, []))
            return lst[-limit:]

    def mark_delivered(self, session_id: str, message_id: str) -> bool:
        with self._lock:
            for m in self._outbox.get(session_id, []):
                if m.id == message_id:
                    m.delivered = True
                    m.attempts += 1
                    return True
            return False

    def increment_outbox_attempt(self, session_id: str, message_id: str) -> int:
        """Increment attempt counter for an outbox message and return new attempts count.

        Returns -1 if message not found.
        """
        with self._lock:
            for m in self._outbox.get(session_id, []):
                if m.id == message_id:
                    m.attempts += 1
                    return m.attempts
            return -1


# Singleton store instance
store = InMemorySessionStore()
