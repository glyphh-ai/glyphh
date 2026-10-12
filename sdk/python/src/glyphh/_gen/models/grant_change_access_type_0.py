from enum import StrEnum


class GrantChangeAccessType0(StrEnum):
    READ = "read"
    WRITE = "write"

    def __str__(self) -> str:
        return str(self.value)
