from enum import StrEnum


class ConnectionViewState(StrEnum):
    CONNECTED = "connected"
    NEEDS_RECONNECT = "needs_reconnect"
    NOT_CONNECTED = "not_connected"
    OFF = "off"

    def __str__(self) -> str:
        return str(self.value)
