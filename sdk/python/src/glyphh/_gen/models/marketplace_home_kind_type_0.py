from enum import StrEnum


class MarketplaceHomeKindType0(StrEnum):
    CUSTOM = "custom"
    SUPER_POWER = "super_power"

    def __str__(self) -> str:
        return str(self.value)
