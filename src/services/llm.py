import datetime
import json
from typing import Any

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from src.config import credential
from src.prompt_templates.template import get_prompt
from src.prompt_templates.template_clarify import get_clarify_prompt
from src.prompt_templates.template_reminder import get_reminder_time
from src.prompt_templates.template_search import get_search_answer_prompt


# Небольшое изменение - много лучше, если client будет на уровне модуля.
client = GigaChat(
        base_url="https://api.giga.chat/v1",
        credentials=credential,
        scope="GIGACHAT_API_PERS",
        verify_ssl_certs=False,
    )

def ask_gigachat(prompt: str, temperature: float = 0.1, max_tokens: int = 1000) -> str:
    chat = Chat(
        model="GigaChat-3-Ultra",
        messages=[
            Messages(
                role=MessagesRole.USER,
                content=prompt,
            )
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )

    response = client.chat(chat)

    return response.choices[0].message.content

def get_answer_gigachat(user_text: str, utc_offset: datetime.timedelta | int | float = 3):
    return ask_gigachat(get_prompt(user_text, utc_offset))


def get_reminder_answer_gigachat(user_text: str, utc_offset: datetime.timedelta | int | float = 3) -> str:
    """JSON {"time", "date"} момента напоминания в UTC по ответу пользователя."""
    return ask_gigachat(get_reminder_time(user_text, utc_offset), max_tokens=100)

def get_search_answer_gigachat(question: str, tasks_text: str) -> str:
    """Сформулировать ответ на вопрос пользователя по найденным записям календаря."""
    return ask_gigachat(get_search_answer_prompt(question, tasks_text), max_tokens=300)


def get_clarify_answer_gigachat(
    scope_text: str,
    question: str,
    utc_offset: datetime.timedelta | int | float = 3,
) -> str:
    """JSON {"suitable": [...]} с номерами записей скоупа, подходящих под уточнение пользователя."""
    return ask_gigachat(get_clarify_prompt(scope_text, question, utc_offset), max_tokens=100)


def parse_json_answer(llm_answer: str) -> dict[str, Any]:
    """JSON-объект из ответа LLM; обрамление ```json ... ``` срезается, если модель его всё же добавила."""
    text = llm_answer.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"Ожидался JSON-объект, получено: {llm_answer!r}")
    return result


def parse_suitable_answer(llm_answer: str, scope_size: int) -> list[int]:
    """Номера подходящих записей из ответа template_clarify; чужие и повторные номера — ошибка."""
    suitable = parse_json_answer(llm_answer).get("suitable")
    if not isinstance(suitable, list):
        raise ValueError(f"Ожидался массив suitable, получено: {llm_answer!r}")

    numbers: list[int] = []
    for value in suitable:
        # bool — подкласс int, а «true» в suitable не номер
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Ожидался номер записи (целое число), получено: {value!r}")
        if not 1 <= value <= scope_size:
            raise ValueError(f"Номер {value} вне скоупа из {scope_size} записей")
        if value not in numbers:
            numbers.append(value)
    return sorted(numbers)
