from uuid import UUID

from src.core.database import Connection
from src.core.exceptions import ServiceError, not_found
from src.web.repository.reviews import ReviewRepository
from src.web.schemas.reviews import Review, ReviewCreate, ReviewUpdate
from src.web.schemas.users import Role, User
from src.web.services.base import BaseService


class ReviewService(BaseService):
    async def create(
        self, submission_id: UUID, data: ReviewCreate, user: User, key: str
    ) -> Review:
        self.require_role(user, Role.PROFESSOR)

        async def save(connection: Connection) -> Review:
            await self.submission(connection, user, submission_id, lock=True)
            if await ReviewRepository.for_submission(connection, submission_id):
                raise ServiceError(
                    409,
                    "REVIEW_ALREADY_EXISTS",
                    "Ревью уже существует; используйте PATCH для обновления",
                )
            values = {
                **data.model_dump(),
                "submission_id": submission_id,
                "professor_id": user.id,
            }
            return Review.model_validate(
                await ReviewRepository.create(connection, values)
            )

        payload = {**data.model_dump(mode="json"), "submission_id": str(submission_id)}
        result, _ = await self.create_once(
            user, "create_review", key, payload, Review, action=save
        )
        return result

    async def get(self, submission_id: UUID, user: User) -> Review:
        async with self.database.transaction(readonly=True) as connection:
            await self.submission(connection, user, submission_id, missing="REVIEW")
            review = await ReviewRepository.for_submission(connection, submission_id)
            if review is None:
                raise not_found("REVIEW")
            return Review.model_validate(review)

    async def update(
        self, submission_id: UUID, data: ReviewUpdate, user: User
    ) -> Review:
        self.require_role(user, Role.PROFESSOR)
        async with self.database.transaction() as connection:
            await self.submission(
                connection, user, submission_id, lock=True, missing="REVIEW"
            )
            review = await ReviewRepository.for_submission(connection, submission_id)
            if review is None:
                raise not_found("REVIEW")
            updated = await ReviewRepository.update(
                connection, review["id"], data.model_dump(exclude_unset=True)
            )
            return Review.model_validate(updated)
