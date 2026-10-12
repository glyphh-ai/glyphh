from enum import StrEnum


class ListCustomPowersKindType0(StrEnum):
    APP = "app"
    PLUGIN = "plugin"
    SKILL = "skill"
    TASK = "task"

    def __str__(self) -> str:
        return str(self.value)
