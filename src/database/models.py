"""ORM-модели, соответствующие PostgreSQL-схеме приложения."""

from __future__ import annotations

from datetime import date as DateValue
from datetime import datetime, time as TimeValue
from enum import Enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Time,
    Text,
    text,
)
from sqlalchemy import (
    Enum as SqlEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

EMBEDDING_DIMENSION = 1536


class EventType(str, Enum):
    """Допустимые типы события."""

    TASK = "task"
    MEETING = "meeting"


# values_callable сохраняет в PostgreSQL значения 'task'/'meeting',
# а не имена членов Python Enum ('TASK'/'MEETING').
EVENT_TYPE_ENUM = SqlEnum(
    EventType,
    name="event_type",
    native_enum=True,
    validate_strings=True,
    values_callable=lambda enum_cls: [member.value for member in enum_cls],
)


class User(Base):
    """Пользователь ВКонтакте."""

    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="Europe/Moscow",
        server_default=text("'Europe/Moscow'"),
    )

    tasks: Mapped[list[Task]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Task(Base):
    """Задача или встреча пользователя."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_user_date", "user_id", "date"),
        Index(
            "idx_tasks_date_notify",
            "date_notify",
            postgresql_where=text("date_notify IS NOT NULL"),
        ),
        Index(
            "idx_tasks_title_vector_hnsw",
            "title_vector",
            postgresql_using="hnsw",
            postgresql_ops={"title_vector": "vector_cosine_ops"},
        ),
    )

    task_id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[EventType] = mapped_column(EVENT_TYPE_ENUM, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_vector: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=True,
    )
    date: Mapped[DateValue] = mapped_column(Date, nullable=False)
    date_notify: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    time: Mapped[TimeValue | None] = mapped_column(Time, nullable=True)
    is_notified: Mapped[bool | None] = mapped_column(nullable=True)

    user: Mapped[User] = relationship(back_populates="tasks")
