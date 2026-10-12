from enum import StrEnum


class NewKeyExpires(StrEnum):
    NEVER = "never"
    VALUE_0 = "30d"
    VALUE_1 = "90d"
    VALUE_2 = "1y"

    def __str__(self) -> str:
        return str(self.value)
