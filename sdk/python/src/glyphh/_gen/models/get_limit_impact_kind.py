from enum import StrEnum


class GetLimitImpactKind(StrEnum):
    CONNECTIONS = "connections"
    MODELS = "models"

    def __str__(self) -> str:
        return str(self.value)
