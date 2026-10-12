from enum import StrEnum


class ReviewQueueStep(StrEnum):
    GLYPHH = "glyphh"
    ORG = "org"

    def __str__(self) -> str:
        return str(self.value)
