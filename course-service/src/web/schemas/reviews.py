from typing import Annotated
from uuid import UUID

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from src.web.schemas.base import BaseSchemaModel, EntitySchema, PatchSchema

Grade = Annotated[int, Field(ge=0, le=100)]
Comment = Annotated[str, Field(max_length=8192)]


class ReviewCreate(BaseSchemaModel):
    grade: Grade
    comment: Comment = ""


class Review(ReviewCreate, EntitySchema):
    submission_id: UUID
    professor_id: int


class ReviewUpdate(PatchSchema):
    grade: Grade | SkipJsonSchema[None] = None
    comment: Comment | SkipJsonSchema[None] = None
