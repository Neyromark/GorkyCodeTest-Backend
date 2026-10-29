import json
import logging
from typing import Any

import uvicorn
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.api_module import ApiServer, InternalClient
from src.choose import division
from src.config import vk_bot_url
from src.database.connection import make_engine, make_session_factory
from src.database.repositories import UserRepository
from src.services.llm import get_answer_gigachat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Клиент для отправки ответа пользователю через VK-бота (POST /api/v1/send-message)
vk_bot = InternalClient(base_url=vk_bot_url)

# Намерения, которые сэмпл уже передаёт в division; остальные проверяем по кусочкам позже
SUPPORTED_INTENTS = {"create_task"}

PARSE_ERROR_ANSWER = "Не удалось понять сообщение. Попробуйте сформулировать иначе."


def parse_intent(llm_answer: str) -> dict[str, Any]:
    """JSON из ответа LLM; обрамление ```json ... ``` срезается, если модель его всё же добавила."""
    text = llm_answer.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    return json.loads(text)


def ensure_user(user_id: int, session: Session) -> None:
    """Для тестов: заводит пользователя VK при первом сообщении, иначе create_task его не найдёт."""
    users = UserRepository(session)
    if users.get(user_id) is None:
        users.create(user_id=user_id, username=f"id{user_id}")
        logger.info(f"User {user_id} created")


def handle_message(payload: dict[str, Any], session: Session | None) -> dict[str, Any]:
    """
    Принимает сообщение пользователя от VK-бота, определяет намерение через LLM
    и для create_task передаёт его в division. Ответ отправляется пользователю через бота.
    """
    user_id = payload.get("user_id")
    message = payload.get("message")
    if not isinstance(user_id, int) or not message:
        raise HTTPException(status_code=422, detail="Нужны поля user_id (int) и message")

    llm_answer = get_answer_gigachat(message)
    logger.info(f"LLM answer for user {user_id}: {llm_answer}")

    try:
        information = parse_intent(llm_answer)
        intent = information["intent"]
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.exception("Не удалось разобрать ответ LLM")
        intent, answer = None, PARSE_ERROR_ANSWER
    else:
        if intent in SUPPORTED_INTENTS:
            ensure_user(user_id, session)
            answer = division(information, user_id, session)
        else:
            answer = f"Намерение «{intent}» в сэмпле пока не обрабатывается."

    print(f'Пользователь {user_id} сказал "{message}" → intent={intent}\n{answer}')

    vk_bot.post(
        "/api/v1/send-message",
        {"type": "message", "user_id": user_id, "message": answer},
    )
    return {"intent": intent, "answer": answer}


engine = make_engine()
server = ApiServer(session_factory=make_session_factory(engine), title="Backend API")
server.add_route("/api/v1/get-message", handle_message)
app = server.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
