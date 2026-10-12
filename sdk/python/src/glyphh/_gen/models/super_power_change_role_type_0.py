from enum import StrEnum


class SuperPowerChangeRoleType0(StrEnum):
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"

    def __str__(self) -> str:
        return str(self.value)
