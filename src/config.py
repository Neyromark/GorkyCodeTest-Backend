import os
from dotenv import load_dotenv

load_dotenv()

credential = os.getenv("CREDENTIAL")
# Адрес VK-бота в сети app-network (порт 80)
vk_bot_url = os.getenv("VK_BOT_URL", "http://vkbottle_bot")
# Адрес сервиса Notifications в сети app-network (порт 8080 внутри контейнера)
notifications_url = os.getenv("NOTIFICATIONS_URL", "http://notifications:8080")
