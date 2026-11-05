from uuid import UUID

from src.web.schemas.base import EntitySchema


class Artifact(EntitySchema):
    submission_id: UUID
    filename: str
    content_type: str
    size: int
    sha256: str
