"""Автомат состояний диалога с пользователем."""

from .context import DialogContext
from .machine import StateMachine, TransitionError
from .names import (
    CLARIFY_CHANGE_NOTIFY,
    CLARIFY_DATE_NOTIFY,
    CLARIFY_SCOPE,
    CONFIRM_ACTION,
    IDLE,
)
from .possible_state import (
    ClarifyChangeNotifyState,
    ClarifyDateNotifyState,
    ClarifyScopeState,
    ConfirmActionState,
    IdleState,
    State,
)

__all__ = [
    "CLARIFY_CHANGE_NOTIFY",
    "CLARIFY_DATE_NOTIFY",
    "CLARIFY_SCOPE",
    "CONFIRM_ACTION",
    "IDLE",
    "ClarifyChangeNotifyState",
    "ClarifyDateNotifyState",
    "ClarifyScopeState",
    "ConfirmActionState",
    "DialogContext",
    "IdleState",
    "State",
    "StateMachine",
    "TransitionError",
]
