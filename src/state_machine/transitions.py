"""Допустимые переходы между состояниями диалога: из состояния-ключа в любое из множества."""

from .names import CLARIFY_DATE_NOTIFY, IDLE

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    IDLE: {
        # Команда не распознана или это не create_task → снова ждём команду
        IDLE,
        # Распознана новая задача → спрашиваем время напоминания
        CLARIFY_DATE_NOTIFY,
    },
    CLARIFY_DATE_NOTIFY: {
        # Задача сохранена (с напоминанием или без) → ждём новую команду
        IDLE,
        # Ответ не удалось разобрать → спрашиваем ещё раз, сохраняя данные задачи
        CLARIFY_DATE_NOTIFY,
    },
}


def can_transition(source: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(source, set())
