from enum import StrEnum


class SetLimitKind(StrEnum):
    CONNECTIONS = "connections"
    MODELS = "models"

    def __str__(self) -> str:
        return str(self.value)
