from enum import IntEnum


class SettingsChangePageSizesType0AdditionalProperty(IntEnum):
    VALUE_10 = 10
    VALUE_25 = 25
    VALUE_50 = 50
    VALUE_100 = 100

    def __str__(self) -> str:
        return str(self.value)
