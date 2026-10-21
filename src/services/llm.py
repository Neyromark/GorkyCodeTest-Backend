from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from src.config import credential
from src.template import get_prompt


def get_answer_gigachat(user_text: str):
    client = GigaChat(
        base_url="https://api.giga.chat/v1",
        credentials=credential,
        scope="GIGACHAT_API_PERS",
        verify_ssl_certs=False,
    )

    prompt = get_prompt(user_text)

    chat = Chat(
        model="GigaChat-3-Ultra",
        messages=[
            Messages(
                role=MessagesRole.USER,
                content=prompt,
            )
        ],
        temperature=0.1,
        max_tokens=1000,
    )

    response = client.chat(chat)

    return response.choices[0].message.content
