from enum import StrEnum


class LinkLabelType0(StrEnum):
    NO = "no"
    YES = "yes"

    def __str__(self) -> str:
        return str(self.value)
