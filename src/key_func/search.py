from datetime import date as DateValue
from datetime import time as TimeValue

from src.database.repositories import UserRepository, TaskRepository
from src.key_func.formats import format_search_answer
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

    return format_search_answer(query, tasks)
