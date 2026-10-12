from enum import StrEnum


class ReviewDecisionDecision(StrEnum):
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    REJECTED = "rejected"

    def __str__(self) -> str:
        return str(self.value)
