from sqlalchemy.orm import Session
from src.database.models import EventType
from src.database.repositories import UserRepository, TaskRepository
from src.vectorization import vector

def create_task(information: dict,user_id: int,session: Session, date_notify):
    """Создаёт задачу или встречу и сохраняет её в БД."""
    user_repository = UserRepository(session)
    user = user_repository.get(user_id)

    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")
    title = information["title"]
    raw_text = information["raw_text"]
    event_type = EventType(information["type"])
    date = information["date"]
    time = information["time"]
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

    return task
