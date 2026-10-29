import logging
from typing import Any
from zoneinfo import ZoneInfo

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


engine = make_engine()
server = ApiServer(session_factory=make_session_factory(engine), title="Backend API")
server.add_route("/api/v1/get-message", handle_message)
app = server.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
