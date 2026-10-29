# GorkyCodeTest-Backend

Сервис-«мозг» умного календаря: принимает сообщение пользователя от VK-бота,
определяет намерение через GigaChat, ведёт диалог с помощью автомата состояний,
сохраняет задачи и встречи в PostgreSQL и заказывает напоминания в сервисе
`Notifications`.

HTTP-приложение — FastAPI, запускается через `uvicorn` на порту `8000`.

## Что умеет

* **`create_task`** — создать задачу или встречу. Бот сначала уточняет время
  напоминания, затем сохраняет запись.
* **`list_events`** — показать задачи и встречи за период (фильтры по типу,
  датам и времени, «сегодня»/«завтра» считаются по часовому поясу пользователя).
* **`search_history`** — семантический поиск по истории: вектор заголовка
  сравнивается с вектором запроса (pgvector, косинусное расстояние), затем LLM
  формулирует ответ по найденным записям.
* Голосовые сообщения не отличаются от текстовых: распознавание делает VK-бот,
  в бэкенд приходит уже текст.

## Запуск

```bash
python -m venv .venv && . .venv/bin/activate     # Python 3.12
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python main.py                                   # http://0.0.0.0:8000
```

Или в составе всего проекта из корня репозитория (сеть `app-network` объявлена
как external и создаётся один раз):

```bash
docker network create app-network 2>/dev/null || true
docker compose up -d --build backend
```

## Переменные окружения

Читаются из `.env` в каталоге модуля (`load_dotenv()` в `src/config.py`) или из
окружения контейнера. Шаблон — [.env.example](.env.example).

| Переменная | Обязательна | По умолчанию | Назначение |
| --- | --- | --- | --- |
| `CREDENTIAL` | да | — | Authorization key GigaChat (scope `GIGACHAT_API_PERS`) |
| `DATABASE_URL` | да | — | `postgresql+psycopg://user:password@host:5432/tasks_db` |
| `VK_BOT_URL` | нет | `http://vkbottle_bot` | База для `POST /api/v1/send-message` |
| `NOTIFICATIONS_URL` | нет | `http://notifications:8080` | База для `POST /notifications` |
| `EMBEDDING_MODEL` | нет | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` | Модель эмбеддингов |
| `HF_HOME`, `HF_HUB_OFFLINE` | нет | заданы в `Dockerfile` | Кэш модели и офлайн-режим в контейнере |

Образ собирается с уже скачанной моделью эмбеддингов (слой до `COPY . .`),
поэтому правки кода не вызывают повторную загрузку, а в рантайме обращения к
Hugging Face Hub нет. Для локального запуска модель скачается при первом
импорте `src/vectorization.py`.

## API

### `POST /api/v1/get-message`

Принимает сообщение пользователя от VK-бота.

```http
POST /api/v1/get-message
Content-Type: application/json
X-Request-ID: 6f1c1f9a-6a58-4a3e-9a8e-9d3e0b0f7c11   # обязателен, UUID4

{"user_id": 123456, "message": "Завтра в 15:00 встреча с Ольгой"}
```

```json
{
  "query_id": "6f1c1f9a-6a58-4a3e-9a8e-9d3e0b0f7c11",
  "status": "done",
  "result": {"state": "CLARIFY_DATE_NOTIFY", "answer": "В какое время вам следует напомнить о задаче?"}
}
```

* `400` — нет заголовка `X-Request-ID` или это не UUID4.
* `422` — в теле нет `user_id` (int) или `message` (непустая строка).
* `status: "already_done"` — запрос с этим `X-Request-ID` уже выполнялся;
  `result` при этом `null`.

Ответ пользователю бэкенд **отправляет сам** — `POST /api/v1/send-message` в
VK-бот. Ошибка доставки логируется, но не откатывает уже сохранённую задачу и
не меняет ответ API.

Идемпотентность: отметка в `done_tasks` и работа обработчика выполняются в одной
транзакции. Если обработчик упал — откатывается и отметка, запрос можно
повторить; параллельный дубль ждёт на первичном ключе и не выполняется дважды.
Если БД недоступна (`session_factory is None`), API работает без дедупликации и
предупреждает об этом в логе.

## Устройство

```
main.py                       сборка приложения, обработчик handle_message
src/
├── api_module/               ApiServer (роутинг, X-Request-ID, done_tasks)
│   └── internal_client.py    HTTP-клиент к другим сервисам с ретраями
├── state_machine/            автомат диалога
│   ├── names.py              IDLE, CLARIFY_DATE_NOTIFY
│   ├── transitions.py        таблица разрешённых переходов
│   ├── machine.py            хранение состояний пользователей
│   ├── context.py            DialogContext: пользователь, сессия БД, часовой пояс
│   └── possible_state/       IdleState, ClarifyDateNotifyState
├── key_func/                 create_task / show_all_tasks / search_tasks и форматирование
├── services/                 GigaChat (llm.py) и постановка напоминаний (notifier.py)
├── prompt_templates/         промпты: разбор сообщения, время напоминания, ответ по поиску
├── database/                 модели SQLAlchemy, репозитории, engine и сессии
└── vectorization.py          эмбеддинги заголовков (768 измерений)
```

### Автомат диалога

```
IDLE ──create_task──▶ CLARIFY_DATE_NOTIFY ──сохранено / отказ──▶ IDLE
  ▲                            │
  └──────list_events, search_history, неизвестное намерение─────┘
                               └──не удалось разобрать ответ───▶ CLARIFY_DATE_NOTIFY (retry)
```

* Пользователь без записи считается находящимся в `IDLE`.
* Переход выполняет само состояние (`State.transition_to` → `StateMachine.transition`),
  машина проверяет его по `ALLOWED_TRANSITIONS` и логирует.
* Состояния — `frozen` dataclass'ы: `IdleState.answer` хранит ответ на последнее
  сообщение, `ClarifyDateNotifyState.information` — разобранные поля задачи.
* Состояния живут в памяти процесса (`dict[int, State]` под `threading.Lock`):
  перезапуск бэкенда их сбрасывает, несколько реплик их не разделяют.
* Обработчики `ApiServer` синхронные, поэтому FastAPI выполняет их в пуле
  потоков и работа с БД не блокирует event loop.

### Создание задачи и напоминание

1. `IdleState` отправляет текст в GigaChat с промптом `template.get_prompt`
   (в промпт подставляются текущие дата, время и смещение UTC пользователя) и
   получает JSON: `intent`, `type`, `title`, `date`, `time`, `raw_text`.
2. При `create_task` управление переходит в `ClarifyDateNotifyState`, который
   спрашивает время напоминания.
3. Ответ разбирает промпт `template_reminder` (JSON `{"date", "time"}` в UTC).
4. `create_task` сохраняет запись в `tasks` вместе с эмбеддингом `raw_text`.
   Если дата не названа — берётся сегодняшняя по часовому поясу пользователя.
   Напоминание по умолчанию: за 15 минут до события, а для дел без времени —
   в 09:00 дня события; прошедшее время отбрасывается.
5. Если напоминание нужно, `schedule_notification` вызывает
   `POST /notifications`; текст ответа дополняется временем напоминания.
   Недоступность сервиса уведомлений не отменяет сохранение задачи — в ответ
   добавляется предупреждение.

Внутренние HTTP-вызовы идут через `InternalClient`: один `httpx.Client` на
процесс, таймаут 10 секунд, до 3 попыток с экспоненциальной паузой. Повторяются
сетевые ошибки и `5xx`, ошибки `4xx` — нет. `X-Request-ID` генерируется один раз
до первой попытки, поэтому все ретраи идемпотентны на принимающей стороне.

### Работа с БД

* `make_engine()` читает `DATABASE_URL` (драйвер `psycopg`), `pool_pre_ping` включён.
* `session_scope()` — сессия в транзакции: `commit` при успехе, `rollback` при ошибке.
* `UserRepository.get_or_create()` заводит пользователя при первом сообщении
  (`username = "id<user_id>"`, часовой пояс `Europe/Moscow`).
* `TaskRepository.search_similar_titles()` сортирует по косинусному расстоянию
  среди кандидатов, отфильтрованных по пользователю и периоду; нулевые векторы
  исключаются (`vector_norm > 0`).
* `DoneTaskRepository.mark_done()` — `INSERT ... ON CONFLICT DO NOTHING RETURNING`.

Схему таблиц создаёт [Database/init.sql](../Database/init.sql);
`database.create_schema()` — вспомогательный bootstrap для пустой базы, а не
замена миграциям.

## Замечания

* `src/choose.py` — устаревшая точка входа, логика переехала в
  `state_machine/possible_state/idle.py`.
* Имя пользователя из VK API не запрашивается (TODO в `UserRepository`).
* Тестов в модуле нет; проверка — реальный диалог с ботом и `docker compose logs backend`.
