from enum import StrEnum


class HostTemplateHost(StrEnum):
    AWS = "aws"
    AZURE = "azure"

    def __str__(self) -> str:
        return str(self.value)
