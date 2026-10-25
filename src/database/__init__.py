"""SQLAlchemy package для схемы пользователей, задач и встреч."""

from .base import Base
from .connection import (
    create_schema,
    make_engine,
    make_session_factory,
    session_scope,
)
from .models import EMBEDDING_DIMENSION, DoneTask, EventType, Task, User
from .repositories import DoneTaskRepository, TaskRepository, UserRepository

__all__ = [
    "EMBEDDING_DIMENSION",
    "Base",
    "DoneTask",
    "DoneTaskRepository",
    "EventType",
    "Task",
    "TaskRepository",
    "User",
    "UserRepository",
    "create_schema",
    "make_engine",
    "make_session_factory",
    "session_scope",
]
