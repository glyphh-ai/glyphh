from enum import StrEnum


class SearchedBy(StrEnum):
    GOAL = "goal"
    SAID = "said"

    def __str__(self) -> str:
        return str(self.value)
