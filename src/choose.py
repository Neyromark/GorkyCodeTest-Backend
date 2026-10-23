import json
from src.key_func.new_task import create_task
from src.key_func.search import search_tasks
from src.key_func.all_tasks import show_all_tasks

def division(information, user_id,session, date_notify):
    """Функция, которая на оcнове ответа llm выбирает функцию для выполнения задачи,которую выбрал пользователь"""
    if isinstance(information, str):
        information = json.loads(information)
    if information["intent"] == "create_task":
        return create_task(information,user_id,session,date_notify)
    elif information["intent"] == "list_events":
        return show_all_tasks(information,user_id,session)
    else:
        return search_tasks(information,user_id,session)
    