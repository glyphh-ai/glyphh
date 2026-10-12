from enum import StrEnum


class ListingChangeReachType0(StrEnum):
    MARKETPLACE = "marketplace"
    ORG = "org"

    def __str__(self) -> str:
        return str(self.value)
