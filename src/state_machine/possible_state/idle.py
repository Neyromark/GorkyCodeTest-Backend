from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from src.key_func.all_tasks import show_all_tasks
from src.key_func.change_delete import find_candidates
from src.key_func.search import search_tasks
from src.services.llm import get_answer_gigachat, parse_json_answer

from ..names import IDLE
from . import clarify_date_notify, clarify_scope, confirm_action
from .base import State

if TYPE_CHECKING:
    from ..context import DialogContext

logger = logging.getLogger(__name__)

GREETING = "Напишите, что запланировать. Например: «Завтра в 15:00 встреча с Ольгой»."
UNKNOWN_INTENT = "Я умею создавать задачи и встречи, показывать их список и искать по ним. Попробуйте переформулировать."
PARSE_ERROR = "Не удалось понять сообщение. Попробуйте сформулировать иначе."
NOT_FOUND = "В календаре не нашлось подходящих записей."


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
        create_task — спрашивает время напоминания, list_events и search_history — отвечают сразу,
        delete_task и change_task — ищут запись и просят подтвердить действие.
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
        elif intent in ("delete_task", "change_task"):
            candidates = find_candidates(information, ctx.user_id, ctx.session)
            logger.info(f"Кандидатов под описание у user {ctx.user_id}: {len(candidates)}")
            if not candidates:
                return self.transition_to(ctx, IdleState(answer=NOT_FOUND))
            # Текущая дата пользователя — состояния показывают записи словами («завтра»)
            today = datetime.now(ctx.tz).date()
            # Подходящих несколько — показываем скоуп и ждём уточнения;
            # ровно одна — сразу просим подтвердить действие
            if len(candidates) == 1:
                return self.transition_to(
                    ctx,
                    confirm_action.ConfirmActionState(
                        information=information,
                        task=candidates[0],
                        today=today,
                    ),
                )
            return self.transition_to(
                ctx,
                clarify_scope.ClarifyScopeState(
                    information=information,
                    candidates=candidates,
                    today=today,
                ),
            )
        else:
            return self.transition_to(ctx, IdleState(answer=UNKNOWN_INTENT))
