"""Создание Engine, фабрики сессий и таблиц PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from . import models as _models  # noqa: F401 — регистрирует модели в Base.metadata
from .base import Base


def make_engine(
    database_url: str | URL | None = None,
    **engine_options: Any,
) -> Engine:
    """Создать синхронный SQLAlchemy Engine.

    Если ``database_url`` не передан, используется переменная окружения
    ``DATABASE_URL``. Для драйвера из README подойдет URL вида
    ``postgresql+psycopg://user:password@host:5432/database``.
    """

    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Не задан DATABASE_URL. Передайте database_url или установите "
            "переменную окружения DATABASE_URL."
        )

    options = {"pool_pre_ping": True, **engine_options}
    return create_engine(url, **options)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Создать фабрику сессий, привязанную к Engine."""

    return sessionmaker(bind=engine, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Открыть сессию в транзакции: commit при успехе, rollback при ошибке."""

    with session_factory.begin() as session:
        yield session


def create_schema(engine: Engine) -> None:
    """Создать расширение pgvector, ENUM и таблицы из ORM metadata.

    Это bootstrap для новой базы, а не замена миграциям. Требует PostgreSQL,
    установленного на сервере расширения pgvector и прав на CREATE EXTENSION.
    """

    if engine.dialect.name != "postgresql":
        raise ValueError("Схема поддерживает только PostgreSQL.")

    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
