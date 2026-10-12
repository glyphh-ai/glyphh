from enum import StrEnum


class KeyViewStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    OFF = "off"
    REVOKED = "revoked"

    def __str__(self) -> str:
        return str(self.value)
