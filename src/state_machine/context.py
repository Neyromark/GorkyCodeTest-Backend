from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from .machine import StateMachine


@dataclass(frozen=True)
class DialogContext:
    """Окружение одного сообщения пользователя. В состоянии не хранится: живёт только на время запроса."""

    user_id: int
    session: Session
    tz: ZoneInfo
    machine: StateMachine

    @property
    def utc_offset(self) -> timedelta:
        return datetime.now(self.tz).utcoffset()
