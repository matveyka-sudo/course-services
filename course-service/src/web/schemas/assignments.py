from typing import Literal
from uuid import UUID

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from src.web.schemas.base import (
    BaseSchemaModel,
    Description,
    EntitySchema,
    PatchSchema,
    Title,
)


class AssignmentFields(BaseSchemaModel):
    title: Title
    description: Description = ""


class AssignmentCreate(AssignmentFields):
    course_id: UUID


class Assignment(AssignmentCreate, EntitySchema):
    pass


class AssignmentUpdate(PatchSchema):
    title: Title | SkipJsonSchema[None] = None
    description: Description | SkipJsonSchema[None] = None


class AssignmentQuery(BaseSchemaModel):
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=10, le=10)
    sort: Literal["created_at:asc"] = "created_at:asc"
