from datetime import date as DateValue
from datetime import time as TimeValue

from src.database.repositories import UserRepository, TaskRepository
from src.database.models import EventType


def show_all_tasks(information, user_id, session):
    user_repository = UserRepository(session)
    user = user_repository.get(user_id)

    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")

    event_type = (
        EventType(information["type"])
        if information.get("type")
        else None
    )

    date_from = (
        DateValue.fromisoformat(information["date_from"])
        if information.get("date_from")
        else None
    )

    date_to = (
        DateValue.fromisoformat(information["date_to"])
        if information.get("date_to")
        else None
    )

    time_start = (
        TimeValue.fromisoformat(information["time_start"])
        if information.get("time_start")
        else None
    )

    time_end = (
        TimeValue.fromisoformat(information["time_end"])
        if information.get("time_end")
        else None
    )

    task_repository = TaskRepository(session)

    tasks = task_repository.list_for_user(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        time_start=time_start,
        time_end=time_end,
        event_type=event_type,
    )
    return tasks
