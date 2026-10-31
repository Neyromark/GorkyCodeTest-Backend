"""Подтверждение удаления или изменения найденной записи."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as DateValue
from typing import TYPE_CHECKING, Any, ClassVar

from src.database.models import Task
from src.key_func.change_delete import apply_changes, delete_found_task
from src.key_func.formats import format_deleted_task, format_pending_changes, format_task_brief
from src.services.llm import get_confirm_answer_gigachat, parse_confirm_answer

from ..names import CONFIRM_ACTION
from . import clarify_change_notify, idle
from .base import State

if TYPE_CHECKING:
    from ..context import DialogContext

logger = logging.getLogger(__name__)

CONFIRM_PARSE_ERROR = "Не удалось разобрать ответ. Ответьте «да» или «нет»."
CANCELLED = "Хорошо, отменено."

ASK = "Ответьте «да» или «нет»."


@dataclass(frozen=True, kw_only=True)
class ConfirmActionState(State):
    """Запись найдена, бот показал её и просит подтвердить удаление или изменение."""

    name: ClassVar[str] = CONFIRM_ACTION

    # Обязательные: JSON из шаблона template, выбранная запись
    # и текущая дата пользователя — по ней запись показывается словами
    information: dict[str, Any]
    task: Task
    today: DateValue
    # Необязательное: почему вопрос задаётся повторно
    retry_reason: str | None = None

    @property
    def is_change(self) -> bool:
        return self.information.get("intent") == "change_task"

    def question(self) -> str:
        lines = [f"Вы имеете в виду запись:\n{format_task_brief(self.task, self.today)}."]
        if self.is_change:
            lines.append(f"Что изменить: {format_pending_changes(self.information, self.today)}.")
            action = "Изменить её?"
        else:
            action = "Удалить её?"
        lines.append(f"{action} {ASK}")
        return "\n".join(lines)

    def message(self) -> str:
        question = self.question()
        return f"{self.retry_reason}\n{question}" if self.retry_reason else question

    def handle(self, text: str, ctx: DialogContext) -> State:
        """
        Удаляет запись или применяет изменения и переходит к вопросу о напоминании.
        Отказ (confirm = false) и неопределённый ответ возвращают в IDLE.
        """
        try:
            confirmed = parse_confirm_answer(
                get_confirm_answer_gigachat(self.question(), text)
            )
        except ValueError:
            logger.exception(f"Не удалось разобрать подтверждение у user {ctx.user_id}")
            return self.transition_to(
                ctx,
                ConfirmActionState(
                    information=self.information,
                    task=self.task,
                    today=self.today,
                    retry_reason=CONFIRM_PARSE_ERROR,
                ),
            )

        logger.info(f"Подтверждение user {ctx.user_id}: {confirmed}")
        if not confirmed:
            return self.transition_to(ctx, idle.IdleState(answer=CANCELLED))

        if self.is_change:
            task = apply_changes(self.task, self.information, ctx.session)
            return self.transition_to(
                ctx,
                clarify_change_notify.ClarifyChangeNotifyState(
                    task=task,
                    information=self.information,
                ),
            )

        # Ответ собираем до удаления: после flush объект уже изъят из сессии
        answer = format_deleted_task(self.task, self.today)
        delete_found_task(self.task, ctx.session)
        return self.transition_to(ctx, idle.IdleState(answer=answer))
