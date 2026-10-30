"""Сужение скоупа: отбор записей по уточнению пользователя (template_clarify)."""

from collections.abc import Sequence
from datetime import timedelta

from src.database.models import Task
from src.key_func.formats import format_clarify_scope
from src.services.llm import get_clarify_answer_gigachat, parse_suitable_answer


def select_suitable_tasks(
    candidates: Sequence[Task],
    question: str,
    utc_offset: int | float | timedelta = 3,
) -> list[Task]:
    """
    Оставляет только те кандидаты, которые подходят под уточнение пользователя, —
    для расплывчатого описания удаляемой/изменяемой задачи, под которую подошло
    несколько записей. Кандидаты сокращаются до скоупа из template_clarify
    (не более 5 задач и 5 встреч), поэтому в результат попадают только записи,
    реально показанные пользователю.
    """
    scope_text, scope_tasks = format_clarify_scope(candidates)
    if not scope_tasks:
        return []

    llm_answer = get_clarify_answer_gigachat(scope_text, question, utc_offset)
    suitable = set(parse_suitable_answer(llm_answer, len(scope_tasks)))
    return [
        task
        for number, task in enumerate(scope_tasks, start=1)
        if number in suitable
    ]
