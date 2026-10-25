import uuid
import logging
from collections.abc import Callable
from typing import Any

from fastapi import Body, FastAPI, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, sessionmaker

from src.database.connection import session_scope
from src.database.repositories import DoneTaskRepository

logger = logging.getLogger(__name__)

# Обработчик (worker) получает JSON-тело запроса и открытую сессию БД
# (или None, если у API нет доступа к БД).
# Возвращаемое значение должно сериализоваться в JSON (dict, list, str, ...).
Worker = Callable[[dict[str, Any], Session | None], Any]


def parse_request_id(request_id: str | None) -> uuid.UUID:
    """
    Проверяет заголовок X-Request-ID: он обязателен и должен быть UUID версии 4.
    """
    if request_id is None:
        raise HTTPException(status_code=400, detail="Не передан заголовок X-Request-ID")

    try:
        query_id = uuid.UUID(request_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Request-ID не является UUID")

    if query_id.version != 4:
        raise HTTPException(status_code=400, detail="X-Request-ID должен быть UUID4")

    return query_id


class ApiServer:
    def __init__(self, session_factory: sessionmaker[Session] | None = None, title: str = "Backend API"):
        # Нет фабрики или она не привязана к engine — значит, у API нет доступа к БД:
        # запросы выполняются без отметки в done_tasks, а обработчик получает session=None.
        if session_factory is not None and session_factory.kw.get("bind") is None:
            session_factory = None
        if session_factory is None:
            logger.warning("ApiServer works without database: requests will not be marked as done")
        self.session_factory = session_factory
        # Само ASGI-приложение, которое запускается через uvicorn
        self.app = FastAPI(title=title)

    def add_route(self, path: str, worker: Worker) -> None:
        """
        Регистрирует POST-адрес path и закрепляет за ним обработчик worker.
        """

        # Обычная (не async) функция: FastAPI выполнит её в пуле потоков,
        # поэтому синхронная работа с БД не блокирует event loop.
        def endpoint(
            payload: dict[str, Any] = Body(...),
            x_request_id: str | None = Header(default=None),
        ) -> dict[str, Any]:
            query_id = parse_request_id(x_request_id)
            return self._execute_once(query_id, path, payload, worker)

        self.app.add_api_route(path, endpoint, methods=["POST"], name=path)

    def _execute_once(
        self,
        query_id: uuid.UUID,
        path: str,
        payload: dict[str, Any],
        worker: Worker,
    ) -> dict[str, Any]:
        # Без БД повторы не отсекаются: каждый запрос просто выполняется
        if self.session_factory is None:
            logger.info(f"Executing request {query_id} to {path} without database")
            result = jsonable_encoder(worker(payload, None))
            return {"query_id": str(query_id), "status": "done", "result": result}

        # Отметка о выполнении и работа обработчика идут в ОДНОЙ транзакции:
        # - если обработчик упал, откатится и отметка, и запрос можно повторить;
        # - параллельный запрос с тем же query_id ждёт на первичном ключе,
        #   пока первая транзакция не завершится, и не выполнится дважды.
        with session_scope(self.session_factory) as session:
            if not DoneTaskRepository(session).mark_done(query_id):
                logger.info(f"Request {query_id} to {path} was already done, skipping")
                return {"query_id": str(query_id), "status": "already_done", "result": None}

            logger.info(f"Executing request {query_id} to {path}")
            # Сериализуем результат внутри сессии, пока ORM-объекты к ней привязаны
            result = jsonable_encoder(worker(payload, session))

        return {"query_id": str(query_id), "status": "done", "result": result}
