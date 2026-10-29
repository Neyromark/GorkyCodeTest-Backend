import datetime
import json
from typing import Any

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from src.config import credential
from src.prompt_templates.template import get_prompt
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


def parse_json_answer(llm_answer: str) -> dict[str, Any]:
    """JSON-объект из ответа LLM; обрамление ```json ... ``` срезается, если модель его всё же добавила."""
    text = llm_answer.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError(f"Ожидался JSON-объект, получено: {llm_answer!r}")
    return result
