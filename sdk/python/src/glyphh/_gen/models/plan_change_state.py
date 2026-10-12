from enum import StrEnum


class PlanChangeState(StrEnum):
    APPLYING = "applying"
    PAY = "pay"
    SCHEDULED = "scheduled"

    def __str__(self) -> str:
        return str(self.value)
