from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Title = Annotated[str, Field(min_length=1, max_length=256)]
Description = Annotated[str, Field(max_length=2048)]
UserId = Annotated[int, Field(ge=0, le=2**63 - 1)]


class BaseSchemaModel(BaseModel):
    model_config = ConfigDict(
        from_attributes=True, extra="forbid", validate_assignment=True
    )


class EntitySchema(BaseSchemaModel):
    id: UUID
    created_at: datetime
    updated_at: datetime


class PatchSchema(BaseSchemaModel):
    @model_validator(mode="after")
    def reject_null_fields(self) -> Self:
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Переданные поля не могут быть null")
        return self


class Pagination(BaseSchemaModel):
    offset: int = Field(ge=0)
    limit: Literal[10, 12]
    total: int = Field(ge=0)


class Page[T](BaseSchemaModel):
    data: list[T]
    pagination: Pagination


class ServiceInfo(BaseSchemaModel):
    healthy: bool = True


class ErrorDetail(BaseSchemaModel):
    code: str
    message: str
    status: int = Field(ge=400, le=599)
    path: str
    request_id: UUID


class ErrorResponse(BaseSchemaModel):
    error: ErrorDetail
