from enum import StrEnum


class AdminNextPlanVersionFamily(StrEnum):
    BASIC = "Basic"
    ENTERPRISE = "Enterprise"
    FREE = "Free"
    PRO = "Pro"
    SOLO = "Solo"

    def __str__(self) -> str:
        return str(self.value)
