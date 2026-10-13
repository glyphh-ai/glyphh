from enum import StrEnum


class HostedViewState(StrEnum):
    EXPIRED = "expired"
    READY = "ready"
    REGISTERED = "registered"
    STARTING = "starting"
    STOPPED = "stopped"
    WAITING = "waiting"

    def __str__(self) -> str:
        return str(self.value)
