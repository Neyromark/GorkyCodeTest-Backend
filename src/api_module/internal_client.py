import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
import uuid

class InternalClient:
    def __init__(self, base_url: str):
        # Создаем один клиент на все запросы (пул соединений)
        # ПРИМЕР: InternalClient(base_url="http://agent-backend:8080")
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    @retry(
        stop=stop_after_attempt(3), # 3 попытки
        wait=wait_exponential(multiplier=1, min=1, max=5), # Ждем 1с, 2с, 4с...
        reraise=True
    )
    async def post(self, endpoint: str, payload: dict):
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": str(uuid.uuid4()) # Трассировка
        }
        try:
            response = await self.client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status() # Выкинет исключение, если статус 4xx/5xx
            return response.json()
        except httpx.RequestError as exc:
            print(f"Сетевая ошибка при запросе к {exc.request.url}: {exc}")
            raise # Пробрасываем выше, чтобы tenacity сделал ретрай