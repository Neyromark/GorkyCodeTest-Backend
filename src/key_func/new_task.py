from datetime import date as DateValue
from datetime import datetime, timedelta
from datetime import time as TimeValue
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session
from src.database.models import EventType
from src.database.repositories import UserRepository, TaskRepository
from src.key_func.formats import format_new_task
from src.vectorization import vector

# Правило по умолчанию: за 15 минут до события, а для дел без времени — в 9:00 дня события
DEFAULT_NOTIFY_BEFORE = timedelta(minutes=15)
DEFAULT_NOTIFY_TIME = TimeValue(9, 0)


def default_date_notify(
    date: DateValue | None,
    time: TimeValue | None,
    tz: ZoneInfo,
) -> datetime | None:
    """Момент напоминания по умолчанию или None, если его не на что опереть или он уже прошёл."""
    if date is None:
        return None

    if time is not None:
        date_notify = datetime.combine(date, time, tzinfo=tz) - DEFAULT_NOTIFY_BEFORE
    else:
        date_notify = datetime.combine(date, DEFAULT_NOTIFY_TIME, tzinfo=tz)

    if date_notify <= datetime.now(tz):
        return None
    return date_notify


def create_task(information: dict, user_id: int, session: Session):
    """Создаёт задачу или встречу и сохраняет её в БД."""
    user_repository = UserRepository(session)
    user = user_repository.get(user_id)

    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")
    tz = ZoneInfo(user.timezone)

    title = information["title"]
    raw_text = information["raw_text"]
    event_type = EventType(information["type"])

    # Дата не названа — задача на сегодня по часовому поясу пользователя (в tasks.date NOT NULL)
    date = (
        DateValue.fromisoformat(information["date"])
        if information.get("date")
        else datetime.now(tz).date()
    )

    time = (
        TimeValue.fromisoformat(information["time"])
        if information.get("time")
        else None
    )

    # Явный срок важнее правила по умолчанию. Явный null — пользователь отказался от напоминания.
    # Время без часового пояса считается местным временем пользователя
    if "date_notify" in information:
        date_notify = (
            datetime.fromisoformat(information["date_notify"])
            if information["date_notify"]
            else None
        )
        if date_notify is not None and date_notify.tzinfo is None:
            date_notify = date_notify.replace(tzinfo=tz)
    else:
        date_notify = default_date_notify(date, time, tz)

    vector_raw_text = list(vector(raw_text))

    task_repository = TaskRepository(session)

    task = task_repository.create(
        user_id=user_id,
        event_type=event_type,
        title=title,
        date=date,
        raw_text=raw_text,
        date_notify=date_notify,
        title_vector=vector_raw_text,
        time=time,
        is_notified=False
    )
    # По часовому поясу юзера
    return format_new_task(information, task, tz)
