from enum import StrEnum


class PersonKind(StrEnum):
    INVITE = "invite"
    MEMBER = "member"

    def __str__(self) -> str:
        return str(self.value)
