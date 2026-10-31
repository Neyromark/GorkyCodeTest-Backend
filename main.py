import logging
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import uvicorn
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api_module import ApiServer, InternalClient
from src.config import vk_bot_url
from src.database.connection import make_engine, make_session_factory
from src.database.repositories import UserRepository
from src.state_machine import DialogContext, StateMachine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Клиент для отправки ответа пользователю через VK-бота (POST /api/v1/send-message)
vk_bot = InternalClient(base_url=vk_bot_url)
machine = StateMachine()


def handle_message(payload: dict[str, Any], session: Session | None) -> dict[str, Any]:
    """Принимает сообщение пользователя от VK-бота и передаёт его текущему состоянию диалога."""
    user_id = payload.get("user_id")
    text = payload.get("message")
    if not isinstance(user_id, int) or not text:
        raise HTTPException(status_code=422, detail="Нужны поля user_id (int) и message")

    user = UserRepository(session).get_or_create(user_id)
    ctx = DialogContext(user_id=user_id, session=session, tz=ZoneInfo(user.timezone), machine=machine)
    state = machine.get(user_id).handle(text, ctx)

    try:
        vk_bot.post("/api/v1/send-message", {"type": "message", "user_id": user_id, "message": state.message()})
    except Exception:
        # Задача и состояние уже сохранены: ошибка доставки ответа не должна их откатывать
        logger.exception(f"Не удалось отправить ответ user {user_id}")
    return {"state": state.name, "answer": state.message()}


def registration(payload: dict[str, Any], session: Session | None) -> dict[str, Any]:
    """Регистрация пользователя: создаёт запись или обновляет имя и часовой пояс."""
    if payload.get("type") != "registration":
        raise HTTPException(status_code=422, detail="Ожидался type='registration'")

    user_id = payload.get("user_id")
    user_name = payload.get("user_name")
    user_timezone = payload.get("user_timezone")
    if isinstance(user_id, bool) or not isinstance(user_id, int):
        raise HTTPException(status_code=422, detail="Нужен user_id (int)")
    if not isinstance(user_name, str) or not user_name.strip():
        raise HTTPException(status_code=422, detail="Нужен user_name (непустая строка)")
    if not isinstance(user_timezone, str) or not user_timezone:
        raise HTTPException(status_code=422, detail="Нужен user_timezone (IANA, например Asia/Novosibirsk)")
    try:
        ZoneInfo(user_timezone)
    except (ValueError, ZoneInfoNotFoundError, KeyError):
        raise HTTPException(status_code=422, detail=f"Неизвестный часовой пояс: {user_timezone}")

    if session is None:
        raise HTTPException(status_code=503, detail="Регистрация недоступна: нет подключения к БД")

    users = UserRepository(session)
    user = users.get(user_id)
    created = user is None
    if created:
        user = users.create(user_id=user_id, username=user_name, timezone=user_timezone)
    else:
        user.username = user_name
        user.timezone = user_timezone
        session.flush()

    return {
        "user_id": user.user_id,
        "username": user.username,
        "timezone": user.timezone,
        "created": created,
    }


engine = make_engine()
server = ApiServer(session_factory=make_session_factory(engine), title="Backend API")
server.add_route("/api/v1/get-message", handle_message)
server.add_route("/api/v1/registration", registration)
app = server.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
