from enum import StrEnum


class AdminOrgsFamilyType0(StrEnum):
    BASIC = "Basic"
    ENTERPRISE = "Enterprise"
    FREE = "Free"
    PRO = "Pro"
    SOLO = "Solo"

    def __str__(self) -> str:
        return str(self.value)
