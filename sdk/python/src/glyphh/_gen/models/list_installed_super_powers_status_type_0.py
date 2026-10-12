from enum import StrEnum


class ListInstalledSuperPowersStatusType0(StrEnum):
    DONE = "done"
    IDLE = "idle"
    NEEDS_YOU = "needs_you"
    STUCK = "stuck"
    THINKING = "thinking"
    WORKING = "working"

    def __str__(self) -> str:
        return str(self.value)
