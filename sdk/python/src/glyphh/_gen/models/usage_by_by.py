from enum import StrEnum


class UsageByBy(StrEnum):
    CONNECTIONS = "connections"
    CONNECTORS = "connectors"
    ERRORS = "errors"
    MACHINES = "machines"
    MODELS = "models"
    POWERS = "powers"
    SUPER_POWERS = "super_powers"
    TOOLS = "tools"
    USERS = "users"

    def __str__(self) -> str:
        return str(self.value)
