from enum import StrEnum


class SettingsChangeThemeType0(StrEnum):
    DARK = "dark"
    LIGHT = "light"
    SYSTEM = "system"

    def __str__(self) -> str:
        return str(self.value)
