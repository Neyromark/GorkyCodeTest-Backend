"""Вопрос о времени напоминания после подтверждённого изменения записи."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, ClassVar

from src.database.models import Task
from src.database.repositories import TaskRepository
from src.key_func.formats import format_changed_task
from src.services.llm import get_reminder_answer_gigachat, parse_json_answer
from src.services.notifier import schedule_notification

from ..names import CLARIFY_CHANGE_NOTIFY
from . import clarify_date_notify, idle
from .base import State

if TYPE_CHECKING:
    from ..context import DialogContext

logger = logging.getLogger(__name__)

ASK_NOTIFY = "Во сколько напомнить об изменённой записи?"
DATE_NOTIFY_PARSE_ERROR = "Не удалось понять время напоминания."


@dataclass(frozen=True, kw_only=True)
class ClarifyChangeNotifyState(State):
    """Изменение уже применено, бот спросил новое время напоминания."""

    name: ClassVar[str] = CLARIFY_CHANGE_NOTIFY

    # Обязательные: изменённая запись и JSON, по которому она менялась
    task: Task
    information: dict[str, Any]
    # Необязательное: почему вопрос задаётся повторно
    retry_reason: str | None = None

    def message(self) -> str:
        return f"{self.retry_reason} {ASK_NOTIFY}" if self.retry_reason else ASK_NOTIFY

    def handle(self, text: str, ctx: DialogContext) -> State:
        """
        Определяет date_notify через template_reminder, сохраняет его в записи
        и ставит напоминание в Notifications, если оно нужно.
        """
        llm_answer = get_reminder_answer_gigachat(text, ctx.utc_offset)
        logger.info(f"Reminder LLM answer for user {ctx.user_id}: {llm_answer}")
        try:
            date_notify = clarify_date_notify.parse_date_notify(parse_json_answer(llm_answer))
        except ValueError:
            logger.exception("Не удалось разобрать ответ LLM о напоминании")
            return self.transition_to(
                ctx,
                ClarifyChangeNotifyState(
                    task=self.task,
                    information=self.information,
                    retry_reason=DATE_NOTIFY_PARSE_ERROR,
                ),
            )

        notes = []
        if date_notify is not None and date_notify <= datetime.now(timezone.utc) + clarify_date_notify.MIN_LEAD:
            date_notify = None
            notes.append(clarify_date_notify.DATE_NOTIFY_IN_PAST)

        task = TaskRepository(ctx.session).update(
            self.task,
            date_notify=date_notify,
            is_notified=False,
        )

        if date_notify is not None:
            try:
                schedule_notification(notification_information(task), ctx.user_id, date_notify, ctx.tz)
            except Exception:
                # Запись уже изменена в БД (date_notify сохранён), ошибку сервиса не пробрасываем
                logger.exception(f"Не удалось поставить напоминание для user {ctx.user_id}")
                notes.append(clarify_date_notify.NOTIFIER_ERROR)

        answer = "\n".join([format_changed_task(task, datetime.now(ctx.tz).date()), *notes])
        return self.transition_to(ctx, idle.IdleState(answer=answer))


def notification_information(task: Task) -> dict:
    """Данные записи для Notifications: после изменения они отличаются от исходного JSON."""
    return {
        "type": task.type.value,
        "title": task.title,
        "date": task.date.isoformat(),
        "time": task.time.strftime("%H:%M") if task.time is not None else None,
    }
