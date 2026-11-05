import hashlib
from pathlib import PurePosixPath
from uuid import UUID

from fastapi import UploadFile

from src.core.database import Connection, Database
from src.core.exceptions import ServiceError
from src.web.repository.artifacts import ArtifactRepository
from src.web.schemas.artifacts import Artifact
from src.web.schemas.users import Role, User
from src.web.services.base import BaseService


class ArtifactService(BaseService):
    def __init__(self, database: Database, max_upload_bytes: int) -> None:
        super().__init__(database)
        self.max_upload_bytes = max_upload_bytes

    async def upload(
        self, submission_id: UUID, file: UploadFile, user: User, key: str
    ) -> Artifact:
        self.require_role(user, Role.PROFESSOR)
        content = await file.read(self.max_upload_bytes + 1)
        if len(content) > self.max_upload_bytes:
            raise ServiceError(
                422, "VALIDATION_ERROR", "Превышен допустимый размер файла"
            )
        filename = PurePosixPath((file.filename or "file").replace("\\", "/")).name
        values = {
            "submission_id": submission_id,
            "filename": filename,
            "content_type": file.content_type or "application/octet-stream",
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }

        async def save(connection: Connection) -> Artifact:
            await self.submission(connection, user, submission_id, lock=True)
            row = await ArtifactRepository.create(
                connection, {**values, "content": content}
            )
            row.pop("content")
            return Artifact.model_validate(row)

        payload = {**values, "submission_id": str(submission_id)}
        result, _ = await self.create_once(
            user, "upload_artifact", key, payload, Artifact, action=save
        )
        return result

    async def list(self, submission_id: UUID, user: User) -> list[Artifact]:
        async with self.database.transaction(readonly=True) as connection:
            await self.submission(connection, user, submission_id)
            rows = await ArtifactRepository.for_submission(connection, submission_id)
            return [Artifact.model_validate(row) for row in rows]
