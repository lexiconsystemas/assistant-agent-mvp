from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Literal, Any, Optional
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


@dataclass
class InboundMessage:
    id: str
    source: str
    author: str
    text: str
    ts: str  # ISO timestamp
    raw: Dict[str, Any]


@dataclass
class SessionBindings:
    discord_channel_id: Optional[str] = None


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
        self._inbox: Dict[str, List[InboundMessage]] = {}
        # session bindings (e.g., discord channel id)
        self._bindings: Dict[str, SessionBindings] = {}
        # last user activity timestamps per session (ISO)
        self._last_user_activity: Dict[str, str] = {}

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
            self._inbox.pop(session_id, None)
            self._bindings.pop(session_id, None)
            self._last_user_activity.pop(session_id, None)

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
                    # Mark delivered without changing attempts count.
                    # attempts should only be incremented on failed delivery attempts.
                    m.delivered = True
                    return True
            return False

    def increment_outbox_attempt(self, session_id: str, message_id: str) -> int:
        """Increment attempt counter for an outbox message and return new attempts count.

        Returns -1 if message not found.
        """
        with self._lock:
            for m in self._outbox.get(session_id, []):
                if m.id == message_id:
                    # attempts increment only on failed delivery attempts
                    m.attempts += 1
                    return m.attempts
            return -1

    # -------- inbox (inbound messages) --------
    def add_inbound(self, session_id: str, author: str, text: str, source: str = "discord", 
                    channel_id: str | None = None, inbound_id: str | None = None, raw: Dict[str, Any] | None = None) -> InboundMessage:
        """Add an inbound message to the inbox.

        Args:
            session_id: Session ID
            author: Author name/ID
            text: Message text
            source: Source platform (default: "discord")
            channel_id: Optional channel ID
            inbound_id: Optional external message ID (for deduplication)

        Returns: InboundMessage
        """
        with self._lock:
            msg = InboundMessage(
                id=inbound_id or str(uuid.uuid4()),
                source=source,
                author=author,
                text=text.strip(),
                ts=_now_iso(),
                raw=raw or {},
            )
            self._inbox.setdefault(session_id, []).append(msg)
            # update last user activity on inbound
            self._last_user_activity[session_id] = msg.ts
            return msg

    def list_inbound(self, session_id: str, limit: int = 50) -> List[InboundMessage]:
        """Get inbound messages for a session."""
        with self._lock:
            lst = list(self._inbox.get(session_id, []))
            return lst[-limit:]

    def has_inbound_id(self, session_id: str, inbound_id: str) -> bool:
        """Check if an inbound message ID already exists (for deduplication)."""
        with self._lock:
            for msg in self._inbox.get(session_id, []):
                if msg.id == inbound_id:
                    return True
            return False

    # -------- bindings & last-activity --------
    def bind_discord_channel(self, session_id: str, channel_id: str) -> None:
        """Bind a discord channel id to a session."""
        with self._lock:
            b = self._bindings.setdefault(session_id, SessionBindings())
            b.discord_channel_id = channel_id

    def get_discord_channel(self, session_id: str) -> Optional[str]:
        with self._lock:
            b = self._bindings.get(session_id)
            return b.discord_channel_id if b else None

    def append_inbound(self, session_id: str, msg: InboundMessage) -> InboundMessage:
        """Append an InboundMessage instance to the inbox and update last activity."""
        with self._lock:
            self._inbox.setdefault(session_id, []).append(msg)
            self._last_user_activity[session_id] = msg.ts
            return msg

    def set_last_user_activity(self, session_id: str, ts_iso: str) -> None:
        with self._lock:
            self._last_user_activity[session_id] = ts_iso

    def get_last_user_activity(self, session_id: str) -> Optional[str]:
        with self._lock:
            return self._last_user_activity.get(session_id)


# Singleton store instance
store = InMemorySessionStore()