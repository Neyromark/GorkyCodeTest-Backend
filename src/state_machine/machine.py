import logging
import threading

from .possible_state import IdleState, State
from .transitions import can_transition

logger = logging.getLogger(__name__)


class TransitionError(Exception):
    """Переход между состояниями не описан в ALLOWED_TRANSITIONS."""


class StateMachine:
    """
    Хранит состояние диалога каждого пользователя. Пользователь без записи находится в IDLE.
    Состояния переходят друг в друга сами (State.handle), а машина проверяет и регистрирует переход.
    """

    def __init__(self) -> None:
        # TODO: хранить состояние в БД, а не в памяти процесса — сейчас оно теряется
        #  при перезапуске бэкенда и не делится между несколькими его экземплярами.
        #  Добавить в модель User (src/database/models.py) и в таблицу "user" (Database/init.sql):
        #    state: Mapped[str] = mapped_column(Text, nullable=False, default=IDLE, server_default=text("'IDLE'"))
        #      -- SQL: state TEXT NOT NULL DEFAULT 'IDLE'
        #    state_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
        #      -- SQL: state_data JSONB (поля состояния, например information для CLARIFY_DATE_NOTIFY)
        self._states: dict[int, State] = {}
        # Обработчики ApiServer выполняются в пуле потоков
        self._lock = threading.Lock()

    def get(self, user_id: int) -> State:
        with self._lock:
            return self._states.get(user_id, IdleState())

    def transition(self, user_id: int, new_state: State) -> State:
        """
        Проверяет переход из текущего состояния в new_state и регистрирует его.
        Состояние вызывает этот метод последним действием перехода.
        """
        with self._lock:
            current = self._states.get(user_id, IdleState())
            if not can_transition(current.name, new_state.name):
                raise TransitionError(f"Переход {current.name} → {new_state.name} не разрешён")
            self._states[user_id] = new_state

        logger.info(f"User {user_id}: {current.name} → {new_state.name}")
        return new_state
