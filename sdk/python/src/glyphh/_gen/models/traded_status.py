from enum import StrEnum


class TradedStatus(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    PENDING = "pending"
    SLOW_DOWN = "slow_down"

    def __str__(self) -> str:
        return str(self.value)
