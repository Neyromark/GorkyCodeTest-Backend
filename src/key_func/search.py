from datetime import date as DateValue
from datetime import time as TimeValue

from src.database.models import EventType
from src.database.repositories import UserRepository, TaskRepository
from src.services.llm import get_search_answer_gigachat
from src.vectorization import vector

NOT_FOUND_ANSWER = "В календаре не нашлось подходящих записей."


def search_tasks(information, user_id, session):
    user_repository = UserRepository(session)
    user = user_repository.get(user_id)

    if user is None:
        raise ValueError(f"Пользователь {user_id} не найден")

    query = information["query"]
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
    
    candidates = task_repository.list_for_user(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        time_start=time_start,
        time_end=time_end,
        limit=1000,
    )

    if not candidates:
        return NOT_FOUND_ANSWER
    query_embedding = vector(query).reshape(-1).tolist()
    candidate_ids = [task.task_id for task in candidates]

    tasks = task_repository.search_similar_titles(
        user_id=user_id,
        embedding=query_embedding,
        task_ids=candidate_ids,
        limit=3,
    )

    if not tasks:
        return NOT_FOUND_ANSWER

    return get_search_answer_gigachat(query, format_tasks(tasks))


def format_tasks(tasks):
    """Записи для промпта: по одной строке, в порядке релевантности."""
    lines = []
    for number, task in enumerate(tasks, start=1):
        kind = "встреча" if task.type == EventType.MEETING else "задача"
        when = task.date.isoformat()
        if task.time is not None:
            when += f", {task.time.strftime('%H:%M')}"
        else:
            when += ", время не указано"
        lines.append(f"{number}. {task.title} — {kind}, {when}")
    return "\n".join(lines)