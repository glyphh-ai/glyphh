from enum import StrEnum


class GetLimitsKind(StrEnum):
    CONNECTIONS = "connections"
    MODELS = "models"

    def __str__(self) -> str:
        return str(self.value)
