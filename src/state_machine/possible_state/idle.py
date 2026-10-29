from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from src.services.llm import get_answer_gigachat, parse_json_answer

from ..names import IDLE
from . import clarify_date_notify
from .base import State

if TYPE_CHECKING:
    from ..context import DialogContext

logger = logging.getLogger(__name__)

GREETING = "Напишите, что запланировать. Например: «Завтра в 15:00 встреча с Ольгой»."
ONLY_CREATE_TASK = "Пока я умею только создавать задачи и встречи. Например: «Завтра в 15:00 встреча с Ольгой»."
PARSE_ERROR = "Не удалось понять сообщение. Попробуйте сформулировать иначе."


@dataclass(frozen=True, kw_only=True)
class IdleState(State):
    """Ожидание новой команды пользователя."""

    name: ClassVar[str] = IDLE

    # Необязательное: ответ на прошлое сообщение (подтверждение задачи, ошибка)
    answer: str | None = None

    def message(self) -> str:
        return self.answer or GREETING

    def handle(self, text: str, ctx: DialogContext) -> State:
        """Распознаёт команду через промпт template; для create_task спрашивает время напоминания."""
        llm_answer = get_answer_gigachat(text, ctx.utc_offset)
        logger.info(f"LLM answer for user {ctx.user_id}: {llm_answer}")
        try:
            information = parse_json_answer(llm_answer)
        except ValueError:
            logger.exception("Не удалось разобрать ответ LLM")
            return self.transition_to(ctx, IdleState(answer=PARSE_ERROR))

        if information.get("intent") != "create_task":
            return self.transition_to(ctx, IdleState(answer=ONLY_CREATE_TASK))

        return self.transition_to(ctx, clarify_date_notify.ClarifyDateNotifyState(information=information))
