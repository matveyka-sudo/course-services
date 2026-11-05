from enum import StrEnum

from src.web.schemas.base import BaseSchemaModel, UserId


class Role(StrEnum):
    ADMIN = "admin"
    PROFESSOR = "professor"
    STUDENT = "student"


class User(BaseSchemaModel):
    id: UserId
    role: Role
