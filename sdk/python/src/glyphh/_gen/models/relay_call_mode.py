from enum import StrEnum


class RelayCallMode(StrEnum):
    AUTONOMOUS = "autonomous"
    DRIVEN = "driven"

    def __str__(self) -> str:
        return str(self.value)
