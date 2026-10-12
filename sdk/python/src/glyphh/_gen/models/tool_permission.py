from enum import StrEnum


class ToolPermission(StrEnum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

    def __str__(self) -> str:
        return str(self.value)
