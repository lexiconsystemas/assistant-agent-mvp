from dotenv import load_dotenv
import os
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# CRITICAL: Load .env BEFORE accessing os.getenv()
load_dotenv()

# Modern SQLAlchemy 2.0 syntax
class Base(DeclarativeBase):
    pass


class Session(Base):
    """Represents a chat session"""
    __tablename__ = "sessions"
    
    id = Column(String(255), primary_key=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    discord_channel_id = Column(String(255), nullable=True, index=True)


class Message(Base):
    """Chat message history"""
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=False)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Task(Base):
    """User tasks"""
    __tablename__ = "tasks"
    
    id = Column(String(255), primary_key=True)
    session_id = Column(String(255), index=True, nullable=False)
    title = Column(String(500), nullable=False)
    completed = Column(Boolean, default=False)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Reminder(Base):
    """User reminders"""
    __tablename__ = "reminders"
    
    id = Column(String(255), primary_key=True)
    session_id = Column(String(255), index=True, nullable=False)
    text = Column(String(500), nullable=False)
    due_ts = Column(DateTime, nullable=False)
    completed = Column(Boolean, default=False)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CheckIn(Base):
    """User check-ins"""
    __tablename__ = "checkins"
    
    id = Column(String(255), primary_key=True)
    session_id = Column(String(255), index=True, nullable=False)
    mood = Column(String(100), nullable=False)
    energy = Column(Integer, nullable=False)
    focus = Column(Integer, nullable=False)
    note = Column(Text, default="")
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OutboundMessage(Base):
    """Outbox queue for message delivery"""
    __tablename__ = "outbound_messages"
    
    id = Column(String(255), primary_key=True)
    session_id = Column(String(255), index=True, nullable=False)
    text = Column(Text, nullable=False)
    reason = Column(String(100), nullable=False)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    delivered = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)


class InboundMessage(Base):
    """Inbound messages from external platforms"""
    __tablename__ = "inbound_messages"
    
    id = Column(String(255), primary_key=True)
    session_id = Column(String(255), index=True, nullable=False)
    source = Column(String(50), nullable=False)
    author = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    ts = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    raw = Column(JSON, default={})


def get_engine():
    """Get database engine from environment"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set in environment")
    return create_engine(database_url, echo=False)  # Set to False for production


def get_session_factory():
    """Get SQLAlchemy session factory"""
    engine = get_engine()
    return sessionmaker(bind=engine)


def init_db():
    """Initialize database tables"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✅ Database tables created successfully")


if __name__ == "__main__":
    init_db()
