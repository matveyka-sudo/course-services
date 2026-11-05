import asyncio
import logging
from uuid import UUID

import httpx

from src.core.config import CheckerSettings
from src.core.database import Database
from src.core.logging import request_id_context
from src.web.repository.submissions import SubmissionRepository
from src.web.schemas.submissions import Submission, SubmissionStatus

logger = logging.getLogger(__name__)


class CheckerService:
    def __init__(
        self, database: Database, client: httpx.AsyncClient, settings: CheckerSettings
    ) -> None:
        self.database = database
        self.client = client
        self.settings = settings
        self.semaphore = asyncio.Semaphore(settings.concurrency)

    async def set_status(self, resource_id: UUID, status: SubmissionStatus) -> None:
        async with self.database.transaction() as connection:
            await SubmissionRepository.update(
                connection, resource_id, {"status": status}
            )

    async def check(self, submission: Submission) -> None:
        if not self.settings.url:
            return
        try:
            await self.set_status(submission.id, SubmissionStatus.PENDING)
            async with asyncio.timeout(self.settings.timeout):
                async with self.semaphore:
                    await self.set_status(submission.id, SubmissionStatus.PROCESSING)
                    response = await self.client.post(
                        self.settings.url,
                        json=submission.model_dump(mode="json"),
                        headers={
                            "Idempotency-Key": str(submission.id),
                            "X-Request-ID": request_id_context.get(),
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    if (
                        not isinstance(body, dict)
                        or body.get("status") != SubmissionStatus.COMPLETED
                    ):
                        raise ValueError("Checker did not return COMPLETED")
            await self.set_status(submission.id, SubmissionStatus.COMPLETED)
            logger.info("Submission check completed submission_id=%s", submission.id)
        except asyncio.CancelledError:
            await self.set_status(submission.id, SubmissionStatus.FAILED)
            raise
        except httpx.HTTPError, TimeoutError, ValueError:
            await self.set_status(submission.id, SubmissionStatus.FAILED)
            logger.warning("Submission check failed submission_id=%s", submission.id)
