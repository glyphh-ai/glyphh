from enum import StrEnum


class ListSuperPowersStatus(StrEnum):
    ALL = "all"
    IDLE = "idle"
    NEEDS_YOU = "needs_you"
    WORKING = "working"

    def __str__(self) -> str:
        return str(self.value)
