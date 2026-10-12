from enum import StrEnum


class PlanPreviewKind(StrEnum):
    DOWNGRADE = "downgrade"
    SUBSCRIBE = "subscribe"
    UPGRADE = "upgrade"

    def __str__(self) -> str:
        return str(self.value)
