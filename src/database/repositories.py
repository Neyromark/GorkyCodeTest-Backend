"""Небольшой слой операций с пользователями и событиями."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date as DateValue
from datetime import datetime, time as TimeValue
from uuid import UUID

from sqlalchemy import func, or_, select, tuple_
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from .models import DoneTask, EventType, Task, User


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
        is_notified: bool | None = False,
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
        time_start: TimeValue | None = None,
        time_end: TimeValue | None = None,
        event_type: EventType | None = None,
        limit: int = 100,
    ) -> list[Task]:
        if limit < 1:
            raise ValueError("limit должен быть положительным числом")

        statement = select(Task).where(Task.user_id == user_id)
        has_dates = date_from is not None or date_to is not None
        has_times = time_start is not None or time_end is not None

        if not has_times:
            # Только даты: события без времени попадают в выборку
            if date_from is not None:
                statement = statement.where(Task.date >= date_from)
            if date_to is not None:
                statement = statement.where(Task.date <= date_to)
        elif not has_dates:
            # Только время: окно по времени внутри каждого дня, события без времени исключаются
            lower_time = time_start if time_start is not None else TimeValue.min
            upper_time = time_end if time_end is not None else TimeValue.max
            if lower_time <= upper_time:
                statement = statement.where(Task.time.between(lower_time, upper_time))
            else:
                # Окно через полночь, например 22:00–02:00
                statement = statement.where(
                    or_(Task.time >= lower_time, Task.time <= upper_time)
                )
        else:
            # Даты и время: непрерывный диапазон (date, time), события без времени исключаются
            lower_date = date_from if date_from is not None else DateValue.min
            lower_time = time_start if time_start is not None else TimeValue.min
            upper_date = date_to if date_to is not None else DateValue.max
            upper_time = time_end if time_end is not None else TimeValue.max
            statement = statement.where(
                Task.time.is_not(None),
                tuple_(Task.date, Task.time) >= (lower_date, lower_time),
                tuple_(Task.date, Task.time) <= (upper_date, upper_time),
            )

        if event_type is not None:
            statement = statement.where(Task.type == event_type)

        # Последние ``limit`` событий, от новых к старым
        statement = statement.order_by(
            Task.date.desc(),
            Task.time.desc().nulls_last(),
            Task.task_id.desc(),
        ).limit(limit)

        return list(self._session.execute(statement).scalars().all())

    def search_similar_titles(
        self,
        user_id: int,
        embedding: Sequence[float],
        task_ids: Sequence[int],
        *,
        limit: int = 5,
    ) -> list[Task]:
        """Вернуть ближайшие заголовки пользователя по cosine distance.
        """

        if limit < 1:
            raise ValueError("limit должен быть положительным числом")
        if not task_ids:
            return []
        # Нулевой вектор (пустой запрос): cosine distance не определена (NaN)
        if not any(embedding):
            return []

        distance = Task.title_vector.cosine_distance(list(embedding))
        statement = (
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.task_id.in_(task_ids),
                Task.title_vector.is_not(None),
                # Сохраненные нулевые векторы дают NaN, исключаем их
                func.vector_norm(Task.title_vector) > 0,
            )
            # ``+ 0`` не дает планировщику выбрать HNSW-индекс: он фильтрует уже после
            # поиска ближайших по всей таблице и может вернуть меньше ``limit`` строк.
            # Кандидатов не больше ``task_ids``, поэтому точная сортировка дешевая.
            .order_by(distance + 0)
            .limit(limit)
        )
        return list(self._session.scalars(statement).all())


class DoneTaskRepository:
    """Учет уже обработанных запросов по их query_id."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, query_id: UUID) -> DoneTask | None:
        return self._session.get(DoneTask, query_id)

    def is_done(self, query_id: UUID) -> bool:
        statement = select(DoneTask.query_id).where(DoneTask.query_id == query_id)
        return self._session.scalar(statement) is not None

    def mark_done(self, query_id: UUID) -> bool:
        """Отметить запрос обработанным.

        Возвращает ``True``, если отметка добавлена, и ``False``, если запрос
        уже был отмечен ранее. Использует ``ON CONFLICT DO NOTHING``, поэтому
        безопасен при конкурентных вызовах с одним и тем же query_id.
        """

        dialect = self._session.get_bind().dialect.name
        insert = sqlite.insert if dialect == "sqlite" else postgresql.insert
        statement = (
            insert(DoneTask)
            .values(query_id=query_id)
            .on_conflict_do_nothing(index_elements=[DoneTask.query_id])
            .returning(DoneTask.query_id)
        )
        return self._session.execute(statement).scalar() is not None