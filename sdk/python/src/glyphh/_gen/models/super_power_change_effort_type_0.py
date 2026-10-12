from enum import StrEnum


class SuperPowerChangeEffortType0(StrEnum):
    HIGH = "high"
    LOW = "low"
    MAX = "max"
    MEDIUM = "medium"
    XHIGH = "xhigh"

    def __str__(self) -> str:
        return str(self.value)
