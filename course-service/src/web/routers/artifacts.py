from fastapi import APIRouter, UploadFile

from src.web.dependencies import Artifacts, CurrentUser, IdempotencyKey, ResourceId
from src.web.schemas.artifacts import Artifact

router = APIRouter(prefix="/api/v1/submissions/{id}/artifacts", tags=["Artifacts"])


@router.post(
    "", response_model=Artifact, status_code=201, operation_id="upload_artifact"
)
async def upload_artifact(
    resource_id: ResourceId,
    file: UploadFile,
    user: CurrentUser,
    key: IdempotencyKey,
    service: Artifacts,
) -> Artifact:
    return await service.upload(resource_id, file, user, key)


@router.get("", response_model=list[Artifact], operation_id="get_artifacts")
async def get_artifacts(
    resource_id: ResourceId, user: CurrentUser, service: Artifacts
) -> list[Artifact]:
    return await service.list(resource_id, user)
