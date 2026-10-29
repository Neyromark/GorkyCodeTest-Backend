from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from src.key_func.all_tasks import show_all_tasks
from src.key_func.search import search_tasks
from src.services.llm import get_answer_gigachat, parse_json_answer

from ..names import IDLE
from . import clarify_date_notify
from .base import State

if TYPE_CHECKING:
    from ..context import DialogContext

logger = logging.getLogger(__name__)

GREETING = "Напишите, что запланировать. Например: «Завтра в 15:00 встреча с Ольгой»."
UNKNOWN_INTENT = "Я умею создавать задачи и встречи, показывать их список и искать по ним. Попробуйте переформулировать."
PARSE_ERROR = "Не удалось понять сообщение. Попробуйте сформулировать иначе."


@dataclass(frozen=True, kw_only=True)
class IdleState(State):
    """Ожидание новой команды пользователя."""

    name: ClassVar[str] = IDLE

    # Необязательное: ответ на прошлое сообщение (подтверждение задачи, список, результат поиска, ошибка)
    answer: str | None = None

    def message(self) -> str:
        return self.answer or GREETING

    def handle(self, text: str, ctx: DialogContext) -> State:
        """
        Распознаёт команду через промпт template:
        create_task — спрашивает время напоминания, list_events и search_history — отвечают сразу.
        """
        llm_answer = get_answer_gigachat(text, ctx.utc_offset)
        logger.info(f"LLM answer for user {ctx.user_id}: {llm_answer}")
        try:
            information = parse_json_answer(llm_answer)
        except ValueError:
            logger.exception("Не удалось разобрать ответ LLM")
            return self.transition_to(ctx, IdleState(answer=PARSE_ERROR))

        intent = information.get("intent")
        if intent == "create_task":
            return self.transition_to(ctx, clarify_date_notify.ClarifyDateNotifyState(information=information))
        elif intent == "list_events":
            return self.transition_to(ctx, IdleState(answer=show_all_tasks(information, ctx.user_id, ctx.session)))
        elif intent == "search_history":
            return self.transition_to(ctx, IdleState(answer=search_tasks(information, ctx.user_id, ctx.session)))
        else:
            return self.transition_to(ctx, IdleState(answer=UNKNOWN_INTENT))
