from enum import StrEnum


class ToolRisk(StrEnum):
    DELETE = "delete"
    OTHER = "other"
    READ = "read"
    WRITE = "write"

    def __str__(self) -> str:
        return str(self.value)
