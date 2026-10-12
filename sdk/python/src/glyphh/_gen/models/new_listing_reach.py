from enum import StrEnum


class NewListingReach(StrEnum):
    MARKETPLACE = "marketplace"
    ORG = "org"

    def __str__(self) -> str:
        return str(self.value)
