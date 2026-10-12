from enum import StrEnum


class ExportUsageUsesScope(StrEnum):
    ME = "me"
    ORG = "org"

    def __str__(self) -> str:
        return str(self.value)
