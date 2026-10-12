from enum import StrEnum


class AdminOrgsStateType0(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"

    def __str__(self) -> str:
        return str(self.value)
