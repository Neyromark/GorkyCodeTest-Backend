"""Небольшой слой операций с пользователями и событиями."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date as DateValue
from datetime import datetime, time as TimeValue

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EventType, Task, User


class UserRepository:
    """Операции чтения и добавления пользователей."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def create(
        self,
        *,
        user_id: int,
        username: str,
        timezone: str = "Europe/Moscow",
    ) -> User:
        user = User(user_id=user_id, username=username, timezone=timezone)
        self._session.add(user)
        self._session.flush()
        return user


class TaskRepository:
    """Операции с событиями, включая поиск похожих заголовков по вектору."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        user_id: int,
        event_type: EventType,
        title: str,
        date: DateValue,
        raw_text: str,
        date_notify: datetime | None = None,
        title_vector: Sequence[float] | None = None,
        time: TimeValue | None = None,
        is_notified: bool | None = None,
    ) -> Task:
        task = Task(
            user_id=user_id,
            type=event_type,
            title=title,
            date=date,
            date_notify=date_notify,
            raw_text=raw_text,
            title_vector=list(title_vector) if title_vector is not None else None,
            time=time,
            is_notified=is_notified,
        )
        self._session.add(task)
        self._session.flush()
        return task

    def list_for_user(
        self,
        user_id: int,
        *,
        date_from: DateValue | None = None,
        date_to: DateValue | None = None,
        event_type: EventType | None = None,
        limit: int = 100,
    ) -> list[Task]:
        if limit < 1:
            raise ValueError("limit должен быть положительным числом")

        statement = select(Task).where(Task.user_id == user_id)
        if date_from is not None:
            statement = statement.where(Task.date >= date_from)
        if date_to is not None:
            statement = statement.where(Task.date < date_to)
        if event_type is not None:
            statement = statement.where(Task.type == event_type)

        statement = statement.order_by(Task.date.asc()).limit(limit)
        return list(self._session.scalars(statement).all())

    def search_similar_titles(
        self,
        user_id: int,
        embedding: Sequence[float],
        *,
        limit: int = 5,
    ) -> list[Task]:
        """Вернуть ближайшие заголовки пользователя по cosine distance.

        Размер ``embedding`` должен совпадать с EMBEDDING_DIMENSION (1536).
        Фильтр по пользователю применяется до ранжирования, чтобы не смешивать
        результаты разных пользователей.
        """

        if limit < 1:
            raise ValueError("limit должен быть положительным числом")

        distance = Task.title_vector.cosine_distance(list(embedding))
        statement = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.title_vector.is_not(None),
            )
            .order_by(distance)
            .limit(limit)
        )
        return list(self._session.scalars(statement).all())
