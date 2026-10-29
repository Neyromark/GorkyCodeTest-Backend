from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from ..context import DialogContext


class State(ABC):
    """
    Состояние диалога. Наследники — dataclass'ы: поля без значения по умолчанию обязательные,
    со значением по умолчанию — необязательные. При переходе создаётся новый объект состояния,
    поэтому поля прошлого состояния сбрасываются, если их явно не передать в конструктор.
    """

    name: ClassVar[str]

    @abstractmethod
    def message(self) -> str:
        """Единственная строка, которая отправляется пользователю при переходе в это состояние."""

    @abstractmethod
    def handle(self, text: str, ctx: DialogContext) -> State:
        """Обрабатывает сообщение пользователя и переходит в новое состояние (через transition_to)."""

    def transition_to(self, ctx: DialogContext, new_state: State) -> State:
        """Последнее действие любого перехода: машина проверяет и регистрирует новое состояние."""
        return ctx.machine.transition(ctx.user_id, new_state)
