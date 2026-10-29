import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import uvicorn
from anyio.from_thread import run as run_in_event_loop
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.database.connection import make_engine, make_session_factory
from src.api_module import ApiServer, InternalClient
from src.config import notifications_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Клиент сервиса Notifications: POST /notifications планирует напоминание
notifications = InternalClient(base_url=notifications_url)

# Notifications отклоняет date_notify в прошлом, поэтому оставляем запас на доставку запроса
MIN_LEAD = timedelta(seconds=10)
# Ограничение длины title в схеме Notifications
MAX_TITLE_LENGTH = 500


def next_minute(now: datetime) -> datetime:
    """Начало следующей минуты; если до неё меньше MIN_LEAD — начало минуты после неё."""
    target = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if target - now < MIN_LEAD:
        target += timedelta(minutes=1)
    return target


def schedule_reminder(payload: dict[str, Any], session: Session | None) -> dict[str, Any]:
    """
    Принимает сообщение пользователя от VK-бота (текст или расшифровку голосового)
    и планирует в Notifications напоминание с тем же текстом на следующую минуту.
    """
    user_id = payload.get("user_id")
    message = payload.get("message")
    if not isinstance(user_id, int) or not message:
        raise HTTPException(status_code=422, detail="Нужны поля user_id (int) и message")

    notify_at = next_minute(datetime.now(timezone.utc))
    print(f'Пользователь {user_id} сказал "{message}", напомним в {notify_at:%H:%M} UTC')

    # Обработчик выполняется в пуле потоков, а InternalClient асинхронный:
    # отправляем запрос через event loop, в котором работает uvicorn
    created = run_in_event_loop(
        notifications.post,
        "/notifications",
        {
            "type": "task",
            "date_notify": notify_at.isoformat(),
            "user_id": user_id,
            "title": message[:MAX_TITLE_LENGTH],
            "date": notify_at.isoformat(),
        },
    )
    job_id = created.get("job_id") if created else None
    logger.info(f"Notification scheduled: job_id={job_id} user_id={user_id} at={notify_at.isoformat()}")
    return {"job_id": job_id, "notify_at": notify_at.isoformat()}


engine = make_engine()
server = ApiServer(session_factory=make_session_factory(engine), title="Backend API")
server.add_route("/api/v1/get-message", schedule_reminder)
app = server.app


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
