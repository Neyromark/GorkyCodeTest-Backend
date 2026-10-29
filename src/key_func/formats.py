"""Форматирование ответов пользователю для функций из key_func."""

from collections.abc import Sequence
from datetime import date as DateValue
from datetime import timedelta

from src.database.models import EventType, Task
from src.services.llm import get_search_answer_gigachat

MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)

HEADERS = {
    None: "Ваши задачи и встречи:",
    EventType.TASK: "Ваши задачи:",
    EventType.MEETING: "Ваши встречи:",
}

EMPTY_SECTIONS = {
    EventType.TASK: "Нет запланированных задач",
    EventType.MEETING: "Нет запланированных встреч",
}

SECTION_TITLES = {
    EventType.TASK: "Задачи ✅:",
    EventType.MEETING: "Встречи 💼:",
}


def format_search_answer(query: str, tasks: Sequence[Task]) -> str:
    """
    Промпт-инжиниринг для поиска: собирает найденные записи в нумерованный список
    (по одной строке, в порядке релевантности), подставляет его в промпт
    и возвращает ответ LLM на вопрос пользователя.
    """
    lines = []
    for number, task in enumerate(tasks, start=1):
        kind = "встреча" if task.type == EventType.MEETING else "задача"
        when = task.date.isoformat()
        if task.time is not None:
            when += f", {task.time.strftime('%H:%M')}"
        else:
            when += ", время не указано"
        lines.append(f"{number}. {task.title} — {kind}, {when}")

    return get_search_answer_gigachat(query, "\n".join(lines))


def format_day(value: DateValue, today: DateValue) -> str:
    relative = {
        today - timedelta(days=1): "вчера",
        today: "сегодня",
        today + timedelta(days=1): "завтра",
        today - timedelta(days=2): "позавчера",
        today + timedelta(days=2): "послезавтра",
    }
    if value in relative:
        return relative[value]

    day = f"{value.day} {MONTHS_GENITIVE[value.month - 1]}"
    return day if value.year == today.year else f"{day} {value.year}"


def format_task_line(number: int, task: Task, today: DateValue) -> str:
    when = format_day(task.date, today)
    if task.time is not None:
        when += f" {task.time.strftime('%H:%M')}"
    return f"{number}. {task.title}, {when}."


def format_all_tasks(information: dict, tasks: Sequence[Task], today: DateValue) -> str:
    event_type = EventType(information["type"]) if information.get("type") else None
    shown_types = [event_type] if event_type else [EventType.TASK, EventType.MEETING]

    sections = []
    for shown_type in shown_types:
        typed_tasks = [task for task in tasks if task.type == shown_type]
        lines = [SECTION_TITLES[shown_type]]
        if typed_tasks:
            lines += [
                format_task_line(number, task, today)
                for number, task in enumerate(typed_tasks, start=1)
            ]
        else:
            lines.append(EMPTY_SECTIONS[shown_type])
        sections.append("\n".join(lines))

    return "\n\n".join([HEADERS[event_type], *sections])
