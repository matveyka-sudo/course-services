from typing import Annotated

from fastapi import APIRouter, Query, Response

from src.web.dependencies import Assignments, CurrentUser, IdempotencyKey, ResourceId
from src.web.schemas.assignments import (
    Assignment,
    AssignmentCreate,
    AssignmentQuery,
    AssignmentUpdate,
)
from src.web.schemas.base import Page

router = APIRouter(prefix="/api/v1/assignments", tags=["Assignments"])


@router.post(
    "", response_model=Assignment, status_code=201, operation_id="create_assignment"
)
async def create_assignment(
    data: AssignmentCreate, user: CurrentUser, key: IdempotencyKey, service: Assignments
) -> Assignment:
    return await service.create(data, user, key)


@router.get("", response_model=Page[Assignment], operation_id="list_assignments")
async def list_assignments(
    query: Annotated[AssignmentQuery, Query()], user: CurrentUser, service: Assignments
) -> Page[Assignment]:
    return await service.list(query, user)


@router.get("/{id}", response_model=Assignment, operation_id="get_assignment")
async def get_assignment(
    resource_id: ResourceId, user: CurrentUser, service: Assignments
) -> Assignment:
    return await service.get(resource_id, user)


@router.patch("/{id}", response_model=Assignment, operation_id="update_assignment")
async def update_assignment(
    resource_id: ResourceId,
    data: AssignmentUpdate,
    user: CurrentUser,
    service: Assignments,
) -> Assignment:
    return await service.update(resource_id, data, user)


@router.delete("/{id}", status_code=204, operation_id="delete_assignment")
async def delete_assignment(
    resource_id: ResourceId, user: CurrentUser, service: Assignments
) -> Response:
    await service.delete(resource_id, user)
    return Response(status_code=204)
