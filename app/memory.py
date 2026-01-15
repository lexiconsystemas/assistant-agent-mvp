"""
Memory module - now backed by PostgreSQL

Import compatibility layer: code using `from app.memory import store` 
continues to work without changes.
"""

from app.db_store import store

__all__ = ["store"]