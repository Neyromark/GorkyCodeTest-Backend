from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date as DateValue
from datetime import datetime, timedelta, timezone
from datetime import time as TimeValue
from typing import TYPE_CHECKING, Any, ClassVar

from src.choose import division
from src.services.llm import get_reminder_answer_gigachat, parse_json_answer
from src.services.notifier import schedule_notification

from ..names import CLARIFY_DATE_NOTIFY
from . import idle
from .base import State

if TYPE_CHECKING:
    from ..context import DialogContext

logger = logging.getLogger(__name__)

# Notifications отклоняет date_notify в прошлом, поэтому оставляем запас на доставку запроса
MIN_LEAD = timedelta(seconds=10)

ASK_DATE_NOTIFY = "В какое время вам следует напомнить о задаче?"
DATE_NOTIFY_PARSE_ERROR = "Не удалось понять время напоминания."
DATE_NOTIFY_IN_PAST = "Это время уже прошло, поэтому задача сохранена без напоминания."
NOTIFIER_ERROR = "⚠️ Не удалось поставить напоминание: сервис уведомлений недоступен."


def parse_date_notify(reminder: dict[str, Any]) -> datetime | None:
    """Момент напоминания в UTC из ответа template_reminder; None — напоминание не нужно."""
    if not reminder.get("date") or not reminder.get("time"):
        return None
    return datetime.combine(
        DateValue.fromisoformat(reminder["date"]),
        TimeValue.fromisoformat(reminder["time"]),
        tzinfo=timezone.utc,
    )


@dataclass(frozen=True, kw_only=True)
class ClarifyDateNotifyState(State):
    """Задача распознана, бот спросил время напоминания."""

    name: ClassVar[str] = CLARIFY_DATE_NOTIFY

    # Обязательное: JSON из промпта template (intent, type, title, date, time, raw_text)
    information: dict[str, Any]
    # Необязательное: почему вопрос задаётся повторно
    retry_reason: str | None = None

    def message(self) -> str:
        return f"{self.retry_reason} {ASK_DATE_NOTIFY}" if self.retry_reason else ASK_DATE_NOTIFY

    def handle(self, text: str, ctx: DialogContext) -> State:
        """
        Определяет date_notify через template_reminder, сохраняет задачу в БД
        и, если напоминание нужно, ставит его в Notifications.
        """
        llm_answer = get_reminder_answer_gigachat(text, ctx.utc_offset)
        logger.info(f"Reminder LLM answer for user {ctx.user_id}: {llm_answer}")
        try:
            date_notify = parse_date_notify(parse_json_answer(llm_answer))
        except ValueError:
            logger.exception("Не удалось разобрать ответ LLM о напоминании")
            return self.transition_to(
                ctx,
                ClarifyDateNotifyState(information=self.information, retry_reason=DATE_NOTIFY_PARSE_ERROR),
            )

        notes = []
        if date_notify is not None and date_notify <= datetime.now(timezone.utc) + MIN_LEAD:
            date_notify = None
            notes.append(DATE_NOTIFY_IN_PAST)

        information = {**self.information, "date_notify": date_notify.isoformat() if date_notify else None}
        # Задача сохраняется в БД в любом случае; без напоминания, если date_notify = None
        try:
            answer = division(information, ctx.user_id, ctx.session)
        except Exception:
            # Иначе каждый следующий ответ снова упадёт на тех же данных и пользователь застрянет
            self.transition_to(ctx, idle.IdleState())
            raise

        if date_notify is not None:
            try:
                schedule_notification(information, ctx.user_id, date_notify, ctx.tz)
            except Exception:
                # Задача уже в БД (date_notify сохранён), поэтому ошибку сервиса уведомлений не пробрасываем
                logger.exception(f"Не удалось поставить напоминание для user {ctx.user_id}")
                notes.append(NOTIFIER_ERROR)

        return self.transition_to(ctx, idle.IdleState(answer="\n".join([answer, *notes])))
