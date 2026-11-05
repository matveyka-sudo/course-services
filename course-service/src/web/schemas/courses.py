from enum import StrEnum
from typing import Literal

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from src.web.schemas.base import (
    BaseSchemaModel,
    Description,
    EntitySchema,
    PatchSchema,
    Title,
    UserId,
)


class CourseStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class CourseFields(BaseSchemaModel):
    title: Title
    description: Description = ""
    status: CourseStatus = CourseStatus.DRAFT


class CourseCreate(CourseFields):
    professor_id: UserId
    student_ids: list[UserId] = Field(default_factory=list)


class Course(CourseCreate, EntitySchema):
    pass


class CourseUpdate(PatchSchema):
    title: Title | SkipJsonSchema[None] = None
    description: Description | SkipJsonSchema[None] = None
    status: CourseStatus | SkipJsonSchema[None] = None


class CourseQuery(BaseSchemaModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=12, ge=12, le=12)
    sort: Literal["created_at:desc"] = "created_at:desc"
