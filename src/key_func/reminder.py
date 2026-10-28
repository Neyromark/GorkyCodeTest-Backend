from zoneinfo import ZoneInfo

from src.prompt_templates.template_reminder import get_reminder_time
from datetime import date as DateValue, time as TimeValue, datetime
import json

'''
Код, который считывает время напоминания из промпта и возвращает время в UTC
'''

def get_reminder_date(user_text : str, tz = ZoneInfo("Europe/Moscow")): # Получаем время по МСК
    dict_reminder_time = json.loads(get_reminder_time(user_text))
    if dict_reminder_time["time"] is None or dict_reminder_time["date"] is None:
        return None

    cur_date = DateValue.fromisoformat(dict_reminder_time["date"])
    cur_time = TimeValue.fromisoformat(dict_reminder_time["time"])

    actual_datetime = datetime.combine(cur_date, cur_time, tzinfo=tz)
    utc_datetime = actual_datetime.astimezone(ZoneInfo("UTC"))

    return utc_datetime # UTC нужен для того, чтобы беспрепятственно передать это в БД и нотифаеру