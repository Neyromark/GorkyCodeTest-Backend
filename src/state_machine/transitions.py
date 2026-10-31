"""Допустимые переходы между состояниями диалога: из состояния-ключа в любое из множеств."""

from .names import CLARIFY_CHANGE_NOTIFY, CLARIFY_DATE_NOTIFY, CLARIFY_SCOPE, CONFIRM_ACTION, IDLE

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    IDLE: {
        # Команда не распознана или это не известный intent → снова ждём команду
        IDLE,
        # Распознана новая задача → спрашиваем время напоминания
        CLARIFY_DATE_NOTIFY,
        # Под delete_task/change_task подошло несколько записей → показываем скоуп
        CLARIFY_SCOPE,
        # Под delete_task/change_task подошла ровно одна запись → ждём подтверждения
        CONFIRM_ACTION,
    },
    CLARIFY_SCOPE: {
        # Уточнение выделило одну запись → ждём подтверждения
        CONFIRM_ACTION,
        # Уточнение не помогло → показываем тот же скоуп ещё раз
        CLARIFY_SCOPE,
    },
    CONFIRM_ACTION: {
        # Удаление выполнено или пользователь отказался → ждём новую команду
        IDLE,
        # Изменение подтверждено → спрашиваем время напоминания
        CLARIFY_CHANGE_NOTIFY,
        # Ответ не удалось разобрать → спрашиваем подтверждение ещё раз
        CONFIRM_ACTION,
    },
    CLARIFY_DATE_NOTIFY: {
        # Задача сохранена (с напоминанием или без) → ждём новую команду
        IDLE,
        # Ответ не удалось разобрать → спрашиваем ещё раз, сохраняя данные задачи
        CLARIFY_DATE_NOTIFY,
    },
    CLARIFY_CHANGE_NOTIFY: {
        # Изменение сохранено (с напоминанием или без) → ждём новую команду
        IDLE,
        # Ответ не удалось разобрать → спрашиваем ещё раз, сохраняя запись
        CLARIFY_CHANGE_NOTIFY,
    },
}


def can_transition(source: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(source, set())
