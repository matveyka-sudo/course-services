from typing import Annotated

from fastapi import APIRouter, Query, Response

from src.web.dependencies import Courses, CurrentUser, IdempotencyKey, ResourceId
from src.web.schemas.base import Page
from src.web.schemas.courses import Course, CourseCreate, CourseQuery, CourseUpdate

router = APIRouter(prefix="/api/v1/courses", tags=["Courses"])


@router.post("", response_model=Course, status_code=201, operation_id="create_course")
async def create_course(
    data: CourseCreate, user: CurrentUser, key: IdempotencyKey, service: Courses
) -> Course:
    return await service.create(data, user, key)


@router.get("", response_model=Page[Course], operation_id="list_courses")
async def list_courses(
    query: Annotated[CourseQuery, Query()], _user: CurrentUser, service: Courses
) -> Page[Course]:
    return await service.list(query)


@router.get("/{id}", response_model=Course, operation_id="get_course")
async def get_course(
    resource_id: ResourceId, _user: CurrentUser, service: Courses
) -> Course:
    return await service.get(resource_id)


@router.patch("/{id}", response_model=Course, operation_id="update_course")
async def update_course(
    resource_id: ResourceId, data: CourseUpdate, user: CurrentUser, service: Courses
) -> Course:
    return await service.update(resource_id, data, user)


@router.delete("/{id}", status_code=204, operation_id="delete_course")
async def delete_course(
    resource_id: ResourceId, user: CurrentUser, service: Courses
) -> Response:
    await service.delete(resource_id, user)
    return Response(status_code=204)
