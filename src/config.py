import os
from dotenv import load_dotenv

load_dotenv()

credential = os.getenv("CREDENTIAL")
# Адрес VK-бота в сети app-network (порт 80)
vk_bot_url = os.getenv("VK_BOT_URL", "http://vkbottle_bot")
