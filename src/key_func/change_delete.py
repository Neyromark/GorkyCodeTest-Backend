"""Поиск кандидатов на удаление/изменение и операции над найденными записями."""

from datetime import date as DateValue
from datetime import time as TimeValue

from sqlalchemy.orm import Session

from src.database.models import EventType, Task
from src.database.repositories import TaskRepository
from src.vectorization import vector

# Кандидатов берём с запасом: format_clarify_scope режет список по типам
# (до 5 задач и до 5 встреч), поэтому из двадцати набираются оба блока
CANDIDATES_LIMIT = 20


def find_candidates(information: dict, user_id: int, session: Session) -> list[Task]:
    """
    Записи пользователя, подходящие под описание из delete_task/change_task:
    фильтр по типу и дате из запроса, затем ближайшие по смыслу заголовки.

    Время в запросе не фильтрует — пользователь может неточно вспомнить
    час встречи, а скоуп всё равно уточняется отдельным вопросом.
    """
    event_type = (
        EventType(information["type"])
        if information.get("type")
        else None
    )
    date = (
        DateValue.fromisoformat(information["date"])
        if information.get("date")
        else None
    )

    task_repository = TaskRepository(session)
    candidates = task_repository.list_for_user(
        user_id=user_id,
        date_from=date,
        date_to=date,
        event_type=event_type,
        limit=1000,
    )
    if not candidates:
        return []

    query = " ".join(
        part for part in (information.get("title"), information.get("raw_text")) if part
    )
    query_embedding = vector(query).reshape(-1).tolist()

    return task_repository.search_similar_titles(
        user_id=user_id,
        embedding=query_embedding,
        task_ids=[task.task_id for task in candidates],
        limit=CANDIDATES_LIMIT,
    )


def delete_found_task(task: Task, session: Session) -> None:
    """Удалить запись, выбранную пользователем на подтверждении."""
    TaskRepository(session).delete(task)


def apply_changes(task: Task, information: dict, session: Session) -> Task:
    """
    Применить new_* поля change_task к найденной записи.

    Напоминание здесь не трогаем: его спросит CLARIFY_CHANGE_NOTIFY,
    но is_notified сбрасываем — старое напоминание больше не актуально.
    """
    changes: dict = {"is_notified": False}

    new_title = information.get("new_title")
    if new_title:
        changes["title"] = new_title
        # Заголовок участвует в поиске похожих записей — пересчитываем вектор
        changes["title_vector"] = vector(new_title).reshape(-1).tolist()
    if information.get("new_date"):
        changes["date"] = DateValue.fromisoformat(information["new_date"])
    if information.get("new_time"):
        changes["time"] = TimeValue.fromisoformat(information["new_time"])

    return TaskRepository(session).update(task, **changes)
