from fastapi import APIRouter

from src.web.dependencies import CurrentUser, IdempotencyKey, ResourceId, Reviews
from src.web.schemas.reviews import Review, ReviewCreate, ReviewUpdate

router = APIRouter(prefix="/api/v1/submissions/{id}/review", tags=["Reviews"])


@router.post("", response_model=Review, status_code=201, operation_id="create_review")
async def create_review(
    resource_id: ResourceId,
    data: ReviewCreate,
    user: CurrentUser,
    key: IdempotencyKey,
    service: Reviews,
) -> Review:
    return await service.create(resource_id, data, user, key)


@router.get("", response_model=Review, operation_id="get_review")
async def get_review(
    resource_id: ResourceId, user: CurrentUser, service: Reviews
) -> Review:
    return await service.get(resource_id, user)


@router.patch("", response_model=Review, operation_id="update_review")
async def update_review(
    resource_id: ResourceId, data: ReviewUpdate, user: CurrentUser, service: Reviews
) -> Review:
    return await service.update(resource_id, data, user)
