from enum import StrEnum


class ExportUsageUsesStatusType0(StrEnum):
    ERROR = "error"
    OK = "ok"
    REFUSED = "refused"

    def __str__(self) -> str:
        return str(self.value)
