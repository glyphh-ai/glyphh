from enum import StrEnum


class StepStep(StrEnum):
    ENTER_CODE = "enter_code"
    OPEN_LINK = "open_link"

    def __str__(self) -> str:
        return str(self.value)
