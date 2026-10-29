from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from src.config import credential
from src.prompt_templates.template import get_prompt
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

def get_answer_gigachat(user_text: str):
    return ask_gigachat(get_prompt(user_text))

def get_search_answer_gigachat(question: str, tasks_text: str) -> str:
    """Сформулировать ответ на вопрос пользователя по найденным записям календаря."""
    return ask_gigachat(get_search_answer_prompt(question, tasks_text), max_tokens=300)