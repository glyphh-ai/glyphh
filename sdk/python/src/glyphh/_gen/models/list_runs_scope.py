from enum import StrEnum


class ListRunsScope(StrEnum):
    ME = "me"
    ORG = "org"

    def __str__(self) -> str:
        return str(self.value)
