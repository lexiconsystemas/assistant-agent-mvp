# app/db_store.py
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc
import uuid

from app.models import (
    get_session_factory,
    Session,
    Message,
    Task,
    Reminder,
    CheckIn,
    OutboundMessage,
    InboundMessage,
)


class DatabaseStore:
    """PostgreSQL-backed session store (replaces InMemorySessionStore)"""

    def __init__(self):
        self.SessionFactory = get_session_factory()

    def _get_db(self) -> DBSession:
        """Get database session (context manager pattern)"""
        return self.SessionFactory()

    def _ensure_session(self, session_id: str):
        """Ensure session exists in database"""
        with self._get_db() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                session = Session(id=session_id)
                db.add(session)
                db.commit()

    # -------- Chat History --------
    def get_history(self, session_id: str, limit: int = 12) -> List[dict]:
        """Get recent messages"""
        with self._get_db() as db:
            messages = (
                db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(desc(Message.ts))
                .limit(limit)
                .all()
            )
            # Return in chronological order
            return [
                {"role": m.role, "content": m.content, "ts": m.ts.isoformat()}
                for m in reversed(messages)
            ]

    def append(self, session_id: str, role: str, content: str) -> None:
        """Append message to history"""
        self._ensure_session(session_id)
        with self._get_db() as db:
            msg = Message(session_id=session_id, role=role, content=content)
            db.add(msg)
            db.commit()

            # Update session last activity
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.last_activity = datetime.now(timezone.utc)
                db.commit()

    def snapshot(self, session_id: str, limit: int = 50) -> List[dict]:
        """Get conversation snapshot"""
        return self.get_history(session_id, limit)

    # -------- Tasks --------
    def add_task(self, session_id: str, title: str) -> dict:
        """Add new task"""
        self._ensure_session(session_id)
        with self._get_db() as db:
            task = Task(
                id=str(uuid.uuid4()),
                session_id=session_id,
                title=title.strip(),
            )
            db.add(task)
            db.commit()
            return {
                "id": task.id,
                "title": task.title,
                "completed": task.completed,
                "ts": task.ts.isoformat(),
            }

    def list_tasks(self, session_id: str) -> List[dict]:
        """List all tasks"""
        with self._get_db() as db:
            tasks = db.query(Task).filter(Task.session_id == session_id).all()
            return [
                {
                    "id": t.id,
                    "title": t.title,
                    "completed": t.completed,
                    "ts": t.ts.isoformat(),
                }
                for t in tasks
            ]

    def complete_task(self, session_id: str, task_id: str) -> bool:
        """Mark task as completed"""
        with self._get_db() as db:
            task = (
                db.query(Task)
                .filter(Task.session_id == session_id, Task.id == task_id)
                .first()
            )
            if task:
                task.completed = True
                db.commit()
                return True
            return False

    # -------- Reminders --------
    def add_reminder(
        self, session_id: str, text: str, due_ts: Optional[str] = None
    ) -> dict:
        """Add new reminder"""
        self._ensure_session(session_id)
        with self._get_db() as db:
            if due_ts is None:
                due_dt = datetime.now(timezone.utc) + timedelta(minutes=60)
            else:
                due_dt = datetime.fromisoformat(due_ts)

            reminder = Reminder(
                id=str(uuid.uuid4()),
                session_id=session_id,
                text=text.strip(),
                due_ts=due_dt,
            )
            db.add(reminder)
            db.commit()
            return {
                "id": reminder.id,
                "text": reminder.text,
                "due_ts": reminder.due_ts.isoformat(),
                "completed": reminder.completed,
                "ts": reminder.ts.isoformat(),
            }

    def list_reminders(self, session_id: str) -> List[dict]:
        """List all reminders"""
        with self._get_db() as db:
            reminders = (
                db.query(Reminder).filter(Reminder.session_id == session_id).all()
            )
            return [
                {
                    "id": r.id,
                    "text": r.text,
                    "due_ts": r.due_ts.isoformat(),
                    "completed": r.completed,
                    "ts": r.ts.isoformat(),
                }
                for r in reminders
            ]

    def complete_reminder(self, session_id: str, reminder_id: str) -> bool:
        """Mark reminder as completed"""
        with self._get_db() as db:
            reminder = (
                db.query(Reminder)
                .filter(Reminder.session_id == session_id, Reminder.id == reminder_id)
                .first()
            )
            if reminder:
                reminder.completed = True
                db.commit()
                return True
            return False

    # -------- Check-ins --------
    def add_checkin(
        self, session_id: str, mood: str, energy: int, focus: int, note: str
    ) -> dict:
        """Add check-in"""
        self._ensure_session(session_id)
        with self._get_db() as db:
            checkin = CheckIn(
                id=str(uuid.uuid4()),
                session_id=session_id,
                mood=mood,
                energy=energy,
                focus=focus,
                note=note or "",
            )
            db.add(checkin)
            db.commit()
            return {
                "id": checkin.id,
                "mood": checkin.mood,
                "energy": checkin.energy,
                "focus": checkin.focus,
                "note": checkin.note,
                "ts": checkin.ts.isoformat(),
            }

    def list_checkins(self, session_id: str, limit: int = 7) -> List[dict]:
        """List recent check-ins"""
        with self._get_db() as db:
            checkins = (
                db.query(CheckIn)
                .filter(CheckIn.session_id == session_id)
                .order_by(desc(CheckIn.ts))
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": c.id,
                    "mood": c.mood,
                    "energy": c.energy,
                    "focus": c.focus,
                    "note": c.note,
                    "ts": c.ts.isoformat(),
                }
                for c in reversed(checkins)
            ]

    # -------- Outbox --------
    def add_outbox(self, session_id: str, text: str, reason: str) -> dict:
        """Add message to outbox"""
        self._ensure_session(session_id)
        with self._get_db() as db:
            msg = OutboundMessage(
                id=str(uuid.uuid4()),
                session_id=session_id,
                text=text,
                reason=reason,
            )
            db.add(msg)
            db.commit()
            return {
                "id": msg.id,
                "text": msg.text,
                "reason": msg.reason,
                "ts": msg.ts.isoformat(),
                "delivered": msg.delivered,
                "attempts": msg.attempts,
            }

    def list_outbox(self, session_id: str, limit: int = 20) -> List[dict]:
        """List outbox messages"""
        with self._get_db() as db:
            messages = (
                db.query(OutboundMessage)
                .filter(OutboundMessage.session_id == session_id)
                .order_by(desc(OutboundMessage.ts))
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": m.id,
                    "text": m.text,
                    "reason": m.reason,
                    "ts": m.ts.isoformat(),
                    "delivered": m.delivered,
                    "attempts": m.attempts,
                }
                for m in reversed(messages)
            ]

    def mark_delivered(self, session_id: str, message_id: str) -> bool:
        """Mark outbox message as delivered"""
        with self._get_db() as db:
            msg = (
                db.query(OutboundMessage)
                .filter(
                    OutboundMessage.session_id == session_id,
                    OutboundMessage.id == message_id,
                )
                .first()
            )
            if msg:
                msg.delivered = True
                db.commit()
                return True
            return False

    def mark_outbox_delivered(self, session_id: str, message_id: str, delivered: bool, delivered_at: Optional[str] = None) -> bool:
        """Mark outbox message as delivered with timestamp"""
        with self._get_db() as db:
            msg = (
                db.query(OutboundMessage)
                .filter(
                    OutboundMessage.session_id == session_id,
                    OutboundMessage.id == message_id,
                )
                .first()
            )
            if msg:
                msg.delivered = delivered
                if delivered_at:
                    from datetime import datetime
                    msg.delivered_at = datetime.fromisoformat(delivered_at.replace('Z', '+00:00'))
                db.commit()
                return True
            return False

    def increment_outbox_attempt(self, session_id: str, message_id: str) -> int:
        """Increment delivery attempt counter"""
        with self._get_db() as db:
            msg = (
                db.query(OutboundMessage)
                .filter(
                    OutboundMessage.session_id == session_id,
                    OutboundMessage.id == message_id,
                )
                .first()
            )
            if msg:
                msg.attempts += 1
                db.commit()
                return msg.attempts
            return -1

    # -------- Inbound Messages --------
    def add_inbound(
        self,
        session_id: str,
        author: str,
        text: str,
        source: str = "discord",
        channel_id: Optional[str] = None,
        inbound_id: Optional[str] = None,
        raw: Optional[dict] = None,
    ) -> dict:
        """Add inbound message"""
        self._ensure_session(session_id)
        with self._get_db() as db:
            msg = InboundMessage(
                id=inbound_id or str(uuid.uuid4()),
                session_id=session_id,
                source=source,
                author=author,
                text=text.strip(),
                raw=raw or {},
            )
            db.add(msg)

            # Update session last activity
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.last_activity = datetime.now(timezone.utc)

            db.commit()
            return {
                "id": msg.id,
                "source": msg.source,
                "author": msg.author,
                "text": msg.text,
                "ts": msg.ts.isoformat(),
                "raw": msg.raw,
            }

    def list_inbound(self, session_id: str, limit: int = 50) -> List[dict]:
        """List inbound messages"""
        with self._get_db() as db:
            messages = (
                db.query(InboundMessage)
                .filter(InboundMessage.session_id == session_id)
                .order_by(desc(InboundMessage.ts))
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": m.id,
                    "source": m.source,
                    "author": m.author,
                    "text": m.text,
                    "ts": m.ts.isoformat(),
                    "raw": m.raw,
                }
                for m in reversed(messages)
            ]

    def has_inbound_id(self, session_id: str, inbound_id: str) -> bool:
        """Check if inbound message exists (deduplication)"""
        with self._get_db() as db:
            exists = (
                db.query(InboundMessage)
                .filter(
                    InboundMessage.session_id == session_id,
                    InboundMessage.id == inbound_id,
                )
                .first()
            )
            return exists is not None

    # -------- Session Bindings --------
    def bind_discord_channel(self, session_id: str, channel_id: str) -> None:
        """Bind Discord channel to session"""
        with self._get_db() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if not session:
                session = Session(id=session_id, discord_channel_id=channel_id)
                db.add(session)
            else:
                session.discord_channel_id = channel_id
            db.commit()

    def get_discord_channel(self, session_id: str) -> Optional[str]:
        """Get Discord channel for session"""
        with self._get_db() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            return session.discord_channel_id if session else None

    def set_last_user_activity(self, session_id: str, ts_iso: str) -> None:
        """Update last user activity timestamp"""
        with self._get_db() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.last_activity = datetime.fromisoformat(ts_iso)
                db.commit()

    def get_last_user_activity(self, session_id: str) -> Optional[str]:
        """Get last user activity timestamp"""
        with self._get_db() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session and session.last_activity:
                return session.last_activity.isoformat()
            return None

    def clear(self, session_id: str) -> None:
        """Clear all session data"""
        with self._get_db() as db:
            db.query(Message).filter(Message.session_id == session_id).delete()
            db.query(Task).filter(Task.session_id == session_id).delete()
            db.query(Reminder).filter(Reminder.session_id == session_id).delete()
            db.query(CheckIn).filter(CheckIn.session_id == session_id).delete()
            db.query(OutboundMessage).filter(OutboundMessage.session_id == session_id).delete()
            db.query(InboundMessage).filter(InboundMessage.session_id == session_id).delete()
            db.query(Session).filter(Session.id == session_id).delete()
            db.commit()


# Singleton instance
store = DatabaseStore()
