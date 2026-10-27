from src.database.repositories import UserRepository,TaskRepository
from src.database.models import EventType


def show_all_tasks(information,user_id,session):
    user_repository = UserRepository(session)
    user = user_repository.get(user_id)

    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")
    
    type = EventType(information["event_type"])
    date_from = information["date_from"]
    date_to = information["date_to"]
    time_start = information["time_start"]
    time_end = information["time_end"]
    task_repository = TaskRepository(session)
    
    tasks = task_repository.list_for_user(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        tieme_start=time_start,
        time_end=time_end,
        event_type=type,
    )
    return tasks