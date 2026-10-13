from enum import StrEnum


class ThreadStartEngine(StrEnum):
    CLAUDE_CODE = "claude_code"
    CODEX = "codex"
    GLYPHH = "glyphh"

    def __str__(self) -> str:
        return str(self.value)
