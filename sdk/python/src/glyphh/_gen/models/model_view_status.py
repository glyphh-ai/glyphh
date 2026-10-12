from enum import StrEnum


class ModelViewStatus(StrEnum):
    KEY_REFUSED = "key_refused"
    OFF = "off"
    READY = "ready"
    UNCHECKED = "unchecked"

    def __str__(self) -> str:
        return str(self.value)
