from enum import StrEnum


class AdminListingsStateType0(StrEnum):
    FEATURED = "featured"
    GLYPHH_REVIEW = "glyphh_review"
    PUBLISHED = "published"
    UNPUBLISHED = "unpublished"

    def __str__(self) -> str:
        return str(self.value)
