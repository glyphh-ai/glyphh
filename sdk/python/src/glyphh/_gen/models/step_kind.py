from enum import StrEnum


class StepKind(StrEnum):
    AGENT = "agent"
    CHECKPOINT = "checkpoint"
    CONNECTION = "connection"
    DECIDE = "decide"
    MEMORY = "memory"
    MODEL = "model"
    OUTPUT = "output"
    SKILL = "skill"
    TRIGGER = "trigger"

    def __str__(self) -> str:
        return str(self.value)
