"""Планирование напоминаний в сервисе Notifications (POST /notifications)."""

import logging
from datetime import date as DateValue
from datetime import datetime, timezone
from datetime import time as TimeValue
from zoneinfo import ZoneInfo

from src.api_module import InternalClient
from src.config import notifications_url

logger = logging.getLogger(__name__)

notifications = InternalClient(base_url=notifications_url)

# Ограничение длины title в схеме Notifications
MAX_TITLE_LENGTH = 500


def event_moment(information: dict, date_notify: datetime, tz: ZoneInfo) -> datetime:
    """
    Момент события для Notifications. Он не может быть раньше date_notify,
    поэтому для задачи без времени (или с напоминанием после начала) берётся date_notify.
    Задача без даты — на сегодня, как в create_task.
    """
    if information.get("time"):
        day = (
            DateValue.fromisoformat(information["date"])
            if information.get("date")
            else datetime.now(tz).date()
        )
        moment = datetime.combine(day, TimeValue.fromisoformat(information["time"]), tzinfo=tz)
        return max(moment, date_notify)
    return date_notify


def schedule_notification(information: dict, user_id: int, date_notify: datetime, tz: ZoneInfo) -> str | None:
    """Ставит напоминание о задаче в Notifications и возвращает job_id."""
    created = notifications.post(
        "/notifications",
        {
            "type": information["type"],
            "date_notify": date_notify.astimezone(timezone.utc).isoformat(),
            "user_id": user_id,
            "title": information["title"][:MAX_TITLE_LENGTH],
            "date": event_moment(information, date_notify, tz).astimezone(timezone.utc).isoformat(),
        },
    )
    job_id = created.get("job_id") if created else None
    logger.info(f"Напоминание поставлено: job_id={job_id} user_id={user_id} время={date_notify.isoformat()}")
    return job_id
