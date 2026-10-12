from enum import StrEnum


class AdminOrgsKindType0(StrEnum):
    PERSONAL = "personal"
    TEAM = "team"

    def __str__(self) -> str:
        return str(self.value)
