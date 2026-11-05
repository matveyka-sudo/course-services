from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query

from src.web.dependencies import CurrentUser, IdempotencyKey, ResourceId, Submissions
from src.web.schemas.base import Page
from src.web.schemas.submissions import Submission, SubmissionCreate, SubmissionQuery

router = APIRouter(prefix="/api/v1/submissions", tags=["Submissions"])


@router.post(
    "", response_model=Submission, status_code=201, operation_id="create_submission"
)
async def create_submission(
    data: SubmissionCreate,
    user: CurrentUser,
    key: IdempotencyKey,
    service: Submissions,
    background: BackgroundTasks,
) -> Submission:
    return await service.create(data, user, key, background)


@router.get("", response_model=Page[Submission], operation_id="list_submissions")
async def list_submissions(
    query: Annotated[SubmissionQuery, Query()], user: CurrentUser, service: Submissions
) -> Page[Submission]:
    return await service.list(query, user)


@router.get("/{id}", response_model=Submission, operation_id="get_submission")
async def get_submission(
    resource_id: ResourceId, user: CurrentUser, service: Submissions
) -> Submission:
    return await service.get(resource_id, user)
