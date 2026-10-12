from enum import StrEnum


class CancelCliSignInCli(StrEnum):
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"

    def __str__(self) -> str:
        return str(self.value)
