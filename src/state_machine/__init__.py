"""Автомат состояний диалога с пользователем."""

from .context import DialogContext
from .machine import StateMachine, TransitionError
from .names import CLARIFY_DATE_NOTIFY, IDLE
from .possible_state import ClarifyDateNotifyState, IdleState, State

__all__ = [
    "CLARIFY_DATE_NOTIFY",
    "IDLE",
    "ClarifyDateNotifyState",
    "DialogContext",
    "IdleState",
    "State",
    "StateMachine",
    "TransitionError",
]
