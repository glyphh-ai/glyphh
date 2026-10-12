from enum import StrEnum


class OpenInPanel(StrEnum):
    MACHINE = "machine"
    NEEDS_YOU = "needs_you"
    THREAD = "thread"

    def __str__(self) -> str:
        return str(self.value)
