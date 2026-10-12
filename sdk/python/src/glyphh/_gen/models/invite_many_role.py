from enum import StrEnum


class InviteManyRole(StrEnum):
    ORG_ADMIN = "org_admin"
    USER = "user"

    def __str__(self) -> str:
        return str(self.value)
