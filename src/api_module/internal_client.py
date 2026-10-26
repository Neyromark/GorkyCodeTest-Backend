import httpx
import uuid
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception, RetryError

logger = logging.getLogger(__name__)


# 1. Кастомное исключение для 5xx ошибок, чтобы отделить их от 4xx
class TransientHTTPError(Exception):
    pass


def is_retryable_error(exception: Exception) -> bool:
    """
    Определяет, стоит ли повторять запрос.
    """
    # Сетевые ошибки (таймауты, обрывы соединения, DNS)
    if isinstance(exception, httpx.RequestError):
        return True

    # Ошибки сервера (5xx). Мы перехватываем их вручную и заворачиваем в TransientHTTPError
    if isinstance(exception, TransientHTTPError):
        return True

    # На 4xx (Bad Request, Unauthorized, Not Found) и ошибки JSON парсинга ретраить НЕ НУЖНО
    return False


class InternalClient:
    def __init__(self, base_url: str):
        # Пул соединений
        self.client = httpx.AsyncClient(base_url=base_url, timeout=10.0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=2),  # Паузы: 1с, 2с. max=2 здесь для наглядности
        retry=retry_if_exception(is_retryable_error),
        reraise=True  # Если все 3 попытки провалились, пробрасываем последнее исключение
    )
    async def _post_with_retry(self, endpoint: str, payload: dict, request_id: str):
        # request_id передается снаружи, чтобы он был одинаковым для всех ретраев
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": request_id
        }

        response = await self.client.post(endpoint, json=payload, headers=headers)

        # Обработка 5xx: выбрасываем ошибку, которая разрешена для ретрая
        if response.status_code >= 500:
            raise TransientHTTPError(f"Server error {response.status_code}")

        # Обработка 4xx: выбрасываем HTTPStatusError, который НЕ будет ретраиться
        response.raise_for_status()

        # Защита от пустого ответа (204 No Content)
        if response.status_code == 204 or not response.content:
            return None

        return response.json()

    async def post(self, endpoint: str, payload: dict):
        # Генерируем ID ОДИН РАЗ до вызова ретрая
        request_id = str(uuid.uuid4())

        # Добавляем ID в payload или в лог для идемпотентности на сервере
        logger.info(f"Starting request {request_id} to {endpoint}")

        try:
            return await self._post_with_retry(endpoint, payload, request_id)
        except Exception as e:
            logger.error(f"Request {request_id} failed completely: {e}")
            raise