"""Форматирование ответов пользователю для функций из key_func."""

from collections.abc import Sequence
from datetime import date as DateValue
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

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

SCOPE_HEADERS = {
    EventType.TASK: "Задачи:",
    EventType.MEETING: "Встречи:",
}

WEEKDAYS_NOMINATIVE = (
    "понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье",
)

# template_clarify работает в урезанном скоупе: не больше 10 записей — по 5 в каждом типе
CLARIFY_LIMIT_PER_TYPE = 5


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


# Относительные названия дней: смещение от текущей даты в днях -> слово
RELATIVE_DAY_OFFSETS = {
    -2: "позавчера",
    -1: "вчера",
    0: "сегодня",
    1: "завтра",
    2: "послезавтра",
}


def format_day(value: DateValue, today: DateValue) -> str:
    relative = RELATIVE_DAY_OFFSETS.get((value - today).days)
    if relative is not None:
        return relative

    day = f"{value.day} {MONTHS_GENITIVE[value.month - 1]}"
    return day if value.year == today.year else f"{day} {value.year}"


def format_abs_date(value: DateValue) -> str:
    """Абсолютная дата с днём недели: «понедельник 2 ноября 2026»."""
    return (
        f"{WEEKDAYS_NOMINATIVE[value.weekday()]} {value.day} "
        f"{MONTHS_GENITIVE[value.month - 1]} {value.year}"
    )


def format_when(value: DateValue, today: DateValue) -> str:
    """
    Дата записи для сообщений бота: ближайшие дни — слово из format_day
    рядом с абсолютной датой («завтра, воскресенье 1 ноября 2026»),
    остальные — только абсолютная дата.
    """
    if (value - today).days in RELATIVE_DAY_OFFSETS:
        return f"{format_day(value, today)}, {format_abs_date(value)}"
    return format_abs_date(value)


def format_scope_line(number: int, task: Task, today: DateValue) -> str:
    """
    Строка кандидата для template_clarify: день недели и дата, а для ближайших
    дней ещё и относительное слово — чтобы ловить и «в пятницу», и «завтра»,
    и «6 ноября», и «2026-11-06».
    """
    when = format_when(task.date, today)
    if task.time is not None:
        when += f" {task.time.strftime('%H:%M')}"
    return f"{number}. {task.title}, {when}."


def format_clarify_scope(tasks: Sequence[Task], today: DateValue) -> tuple[str, list[Task]]:
    """
    Единственная строка кандидатов для промпта template_clarify:
    не больше 5 задач и 5 встреч, сквозная нумерация от задач к встречам.
    Возвращает строку и записи в её нумерации — состав и порядок совпадают,
    поэтому номер из ответа LLM указывает на ту же запись в списке.
    """
    limited = {
        event_type: [task for task in tasks if task.type == event_type][:CLARIFY_LIMIT_PER_TYPE]
        for event_type in (EventType.TASK, EventType.MEETING)
    }
    scope_tasks = [*limited[EventType.TASK], *limited[EventType.MEETING]]
    if not scope_tasks:
        return "", []

    sections = []
    number = 1
    for event_type in (EventType.TASK, EventType.MEETING):
        typed_tasks = limited[event_type]
        if not typed_tasks:
            continue
        lines = [SCOPE_HEADERS[event_type]]
        for task in typed_tasks:
            lines.append(format_scope_line(number, task, today))
            number += 1
        sections.append("\n".join(lines))

    return "\n\n".join(sections), scope_tasks


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


def format_task_brief(task: Task, today: DateValue) -> str:
    """Одна запись для сообщений бота: «название» — тип, завтра, воскресенье 1 ноября 2026, 18:00."""
    kind = "встреча" if task.type == EventType.MEETING else "задача"
    when = format_when(task.date, today)
    when += f", {task.time.strftime('%H:%M')}" if task.time is not None else ", время не указано"
    return f"«{task.title}» — {kind}, {when}"


def format_pending_changes(information: dict, today: DateValue) -> str:
    """Что именно будет изменено — по new_* полям из шаблона template."""
    parts = []
    if information.get("new_title"):
        parts.append(f"название: «{information['new_title']}»")
    if information.get("new_date"):
        parts.append(f"дата: {format_when(DateValue.fromisoformat(information['new_date']), today)}")
    if information.get("new_time"):
        parts.append(f"время: {information['new_time']}")
    return ", ".join(parts)


def format_deleted_task(task: Task, today: DateValue) -> str:
    return f"Запись удалена: {format_task_brief(task, today)}."


def format_changed_task(task: Task, today: DateValue) -> str:
    return f"Запись изменена: {format_task_brief(task, today)}."


def to_user_time(value: datetime, tz: ZoneInfo) -> datetime:
    """Переводит момент (из БД — в UTC) в часовой пояс пользователя; время без пояса считается UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(tz)


def format_new_task(information: dict, task: Task, tz: ZoneInfo) -> str:
    today = datetime.now(tz).date()
    day = format_day(task.date, today) if task.date is not None else None
    clock = task.time.strftime("%H:%M") if task.time is not None else None

    if EventType(information["type"]) == EventType.MEETING:
        parts = [f"💼  {task.title} запланирована"]
        if day:
            parts.append(day)
        if clock:
            parts.append(f"в {clock}")
        text = " ".join(parts) + "."
    else:
        text = f'✅  Задача "{task.title}" запланирована'
        when = ", ".join(part for part in (day, clock) if part)
        text = f"{text} на {when}." if when else f"{text}."

    if task.date_notify is not None:
        notify = to_user_time(task.date_notify, tz)
        text += f" Напоминание придёт {format_day(notify.date(), today)} в {notify:%H:%M}."
    return text
