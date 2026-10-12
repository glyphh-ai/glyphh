from enum import StrEnum


class ModelChangeTypeType0(StrEnum):
    AUDIO = "audio"
    CHAT = "chat"
    EMBEDDING = "embedding"
    IMAGE = "image"
    VIDEO = "video"

    def __str__(self) -> str:
        return str(self.value)
