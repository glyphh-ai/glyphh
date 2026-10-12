from enum import StrEnum


class ThreadStartMode(StrEnum):
    AUTONOMOUS = "autonomous"
    DRIVEN = "driven"

    def __str__(self) -> str:
        return str(self.value)
