from enum import StrEnum


class FlowStepKind(StrEnum):
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
