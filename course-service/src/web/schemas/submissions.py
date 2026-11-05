from enum import StrEnum
from uuid import UUID

from pydantic import Field

from src.web.schemas.base import BaseSchemaModel, EntitySchema


class SubmissionStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SubmissionCreate(BaseSchemaModel):
    assignment_id: UUID
    solution: str = Field(min_length=1, max_length=1_000_000)


class Submission(SubmissionCreate, EntitySchema):
    student_id: int
    attempt: int = Field(ge=1, le=10)
    status: SubmissionStatus


class SubmissionQuery(BaseSchemaModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=10, le=10)
