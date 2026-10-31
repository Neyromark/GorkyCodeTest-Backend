"""Уточнение скоупа: под delete_task/change_task подошло несколько записей."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as DateValue
from typing import TYPE_CHECKING, Any, ClassVar

from src.database.models import Task
from src.key_func.clarify import select_suitable_tasks
from src.key_func.formats import format_clarify_scope

from ..names import CLARIFY_SCOPE
from . import confirm_action
from .base import State

if TYPE_CHECKING:
    from ..context import DialogContext

logger = logging.getLogger(__name__)

NOTHING_MATCHED = "По этому уточнению не нашлось подходящих записей."
SEVERAL_MATCHED = "Подходит больше одной записи — уточните точнее."
PARSE_ERROR = "Не удалось понять уточнение. Попробуйте ещё раз."

ASK = "Какую из них вы имеете в виду? Напишите, например: «та, что в понедельник»."


@dataclass(frozen=True, kw_only=True)
class ClarifyScopeState(State):
    """Описание записи расплывчато: пользователю показан скоуп кандидатов."""

    name: ClassVar[str] = CLARIFY_SCOPE

    # Обязательные: JSON из шаблона template, кандидаты до урезания скоупом
    # и текущая дата пользователя — по ней скоуп показывает «завтра» и т. п.
    information: dict[str, Any]
    candidates: list[Task]
    today: DateValue
    # Необязательное: почему уточнение не подошло
    retry_reason: str | None = None

    def question(self) -> str:
        scope_text, _ = format_clarify_scope(self.candidates, self.today)
        return (
            "Под ваше описание подходит несколько записей:\n"
            f"{scope_text}\n\n{ASK}"
        )

    def message(self) -> str:
        question = self.question()
        return f"{self.retry_reason}\n\n{question}" if self.retry_reason else question

    def handle(self, text: str, ctx: DialogContext) -> State:
        """
        Оставляет через template_clarify только записи, подходящие под уточнение:
        одна — ждём подтверждения, больше или меньше одной — спрашиваем ещё раз.
        """
        try:
            selected = select_suitable_tasks(self.candidates, text, self.today, ctx.utc_offset)
        except ValueError:
            logger.exception(f"Не удалось разобрать уточнение скоупа у user {ctx.user_id}")
            return self.transition_to(
                ctx,
                ClarifyScopeState(
                    information=self.information,
                    candidates=self.candidates,
                    today=self.today,
                    retry_reason=PARSE_ERROR,
                ),
            )

        logger.info(
            f"Уточнение скоупа user {ctx.user_id}: {len(selected)} из {len(self.candidates)}"
        )
        if len(selected) == 1:
            return self.transition_to(
                ctx,
                confirm_action.ConfirmActionState(
                    information=self.information,
                    task=selected[0],
                    today=self.today,
                ),
            )

        return self.transition_to(
            ctx,
            ClarifyScopeState(
                information=self.information,
                candidates=self.candidates,
                today=self.today,
                retry_reason=NOTHING_MATCHED if not selected else SEVERAL_MATCHED,
            ),
        )
