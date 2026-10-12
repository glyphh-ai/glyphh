from enum import StrEnum


class AdminAuditLogTypeType0(StrEnum):
    BILLING = "billing"
    FEATURED = "featured"
    GIFTS = "gifts"
    GLYPHH = "glyphh"
    KEYS = "keys"
    LIMITS = "limits"
    MARKETPLACE = "marketplace"
    MEMBERS = "members"
    MODELS = "models"
    ORGS = "orgs"
    PLANS = "plans"
    REVIEW = "review"
    TEAMS = "teams"

    def __str__(self) -> str:
        return str(self.value)
