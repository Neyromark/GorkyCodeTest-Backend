import logging
from typing import Any

import uvicorn
from anyio.from_thread import run as run_in_event_loop
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api_module import ApiServer, InternalClient
from src.config import vk_bot_url

logging.basicConfig(level=logging.INFO)

# Клиент для отправки сообщений пользователю через VK-бота (POST /api/v1/send-message)
vk_bot = InternalClient(base_url=vk_bot_url)


def echo_message(payload: dict[str, Any], session: Session | None) -> dict[str, Any]:
    """
    Принимает сообщение пользователя от VK-бота (текст или расшифровку голосового)
    и отправляет его обратно тем же текстом.
    """
    user_id = payload.get("user_id")
    message = payload.get("message")
    if not isinstance(user_id, int) or not message:
        raise HTTPException(status_code=422, detail="Нужны поля user_id (int) и message")

    print(f'Пользователь {user_id} сказал "{message}"')

    # Обработчик выполняется в пуле потоков, а InternalClient асинхронный:
    # отправляем запрос через event loop, в котором работает uvicorn
    reply = run_in_event_loop(
        vk_bot.post,
        "/api/v1/send-message",
        {"type": "message", "user_id": user_id, "message": message},
    )
    return {"replied": reply is not None and reply.get("status") in ("done", "already_done")}


# Сэмпл работает без БД: ApiServer не отмечает запросы в done_tasks
server = ApiServer(title="Backend API")
server.add_route("/api/v1/get-message", echo_message)
app = server.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
