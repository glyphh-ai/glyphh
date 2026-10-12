from enum import StrEnum


class RemoveLimitEntriesKind(StrEnum):
    CONNECTIONS = "connections"
    MODELS = "models"

    def __str__(self) -> str:
        return str(self.value)
