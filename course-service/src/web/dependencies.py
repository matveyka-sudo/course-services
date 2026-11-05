from typing import Annotated, cast
from uuid import UUID

import jwt
from fastapi import Depends, Header, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError

from src.core.database import Database
from src.core.exceptions import ServiceError
from src.web.schemas.users import User
from src.web.services.artifacts import ArtifactService
from src.web.services.assignments import AssignmentService
from src.web.services.courses import CourseService
from src.web.services.reviews import ReviewService
from src.web.services.submissions import SubmissionService

bearer = HTTPBearer(auto_error=False, scheme_name="bearerAuth")


async def get_database(request: Request) -> Database:
    return cast(Database, request.app.state.database)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        if request.headers.get("Authorization"):
            raise ServiceError(401, "TOKEN_INVALID", "Токен недействителен")
        raise ServiceError(401, "TOKEN_MISSING", "Токен отсутствует")
    settings = request.app.state.settings.auth
    secret = settings.secret.get_secret_value()
    if not secret:
        raise ServiceError(401, "TOKEN_INVALID", "Не настроена проверка токенов")
    try:
        payload = jwt.decode(
            credentials.credentials,
            secret,
            algorithms=["HS256"],
            issuer=settings.issuer,
            audience=settings.audience,
            options={
                "require": ["sub", "role", "exp"],
                "verify_aud": settings.audience is not None,
            },
        )
        if not isinstance(payload["sub"], str) or not payload["sub"].isdigit():
            raise ValueError("Invalid subject")
        return User(id=int(payload["sub"]), role=payload["role"])
    except jwt.ExpiredSignatureError as exc:
        raise ServiceError(401, "TOKEN_EXPIRED", "Токен истёк") from exc
    except (jwt.InvalidTokenError, ValidationError, ValueError, TypeError) as exc:
        raise ServiceError(401, "TOKEN_INVALID", "Токен недействителен") from exc


async def get_idempotency_key(
    value: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if value is None:
        raise ServiceError(
            422, "IDEMPOTENCY_KEY_MISSING", "Заголовок Idempotency-Key обязателен"
        )
    if not value.strip():
        raise ServiceError(
            422, "VALIDATION_ERROR", "Idempotency-Key не может быть пустым"
        )
    return value


ResourceId = Annotated[UUID, Path(alias="id")]

DatabaseDependency = Annotated[Database, Depends(get_database)]
CurrentUser = Annotated[User, Depends(get_current_user)]
IdempotencyKey = Annotated[str, Depends(get_idempotency_key)]


async def get_course_service(database: DatabaseDependency) -> CourseService:
    return CourseService(database)


async def get_assignment_service(database: DatabaseDependency) -> AssignmentService:
    return AssignmentService(database)


async def get_submission_service(
    request: Request, database: DatabaseDependency
) -> SubmissionService:
    return SubmissionService(database, request.app.state.checker)


async def get_review_service(database: DatabaseDependency) -> ReviewService:
    return ReviewService(database)


async def get_artifact_service(
    request: Request, database: DatabaseDependency
) -> ArtifactService:
    return ArtifactService(database, request.app.state.settings.max_upload_bytes)


Courses = Annotated[CourseService, Depends(get_course_service)]
Assignments = Annotated[AssignmentService, Depends(get_assignment_service)]
Submissions = Annotated[SubmissionService, Depends(get_submission_service)]
Reviews = Annotated[ReviewService, Depends(get_review_service)]
Artifacts = Annotated[ArtifactService, Depends(get_artifact_service)]
