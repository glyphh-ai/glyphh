from enum import StrEnum


class HealthStatus(StrEnum):
    DEGRADED = "degraded"
    OK = "ok"

    def __str__(self) -> str:
        return str(self.value)
