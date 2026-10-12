from enum import StrEnum


class JoinScreenRole(StrEnum):
    ORG_ADMIN = "org_admin"
    USER = "user"

    def __str__(self) -> str:
        return str(self.value)
