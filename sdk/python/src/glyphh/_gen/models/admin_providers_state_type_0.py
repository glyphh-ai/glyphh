from enum import StrEnum


class AdminProvidersStateType0(StrEnum):
    OFF = "off"
    ON = "on"
    REMOVED = "removed"

    def __str__(self) -> str:
        return str(self.value)
