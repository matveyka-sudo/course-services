import asyncio
import logging
from uuid import UUID

import httpx

from src.core.config import get_settings
from src.core.database import Database
from src.infrastructure.outbox_repository import OutboxRepository
from src.web.repository.submissions import SubmissionRepository
from src.web.schemas.submissions import Submission, SubmissionStatus
from src.web.services.checker import CheckerService

logger = logging.getLogger(__name__)


class OutboxWorker:
    def __init__(self, database: Database, checker: CheckerService, retry_delay: float = 5):
        self.database = database
        self.checker = checker
        self.retry_delay = retry_delay

    async def process_once(self, submission_id: UUID | None = None) -> bool:
        if not self.checker.settings.url:
            return False
        async with self.database.transaction() as connection:
            outbox = OutboxRepository(connection)
            event = await outbox.claim(submission_id)
            if event is None:
                return False
            current = await SubmissionRepository.get(connection, event["submission_id"])
            if current is None:
                return False
            success = current["status"] == SubmissionStatus.COMPLETED
            if not success:
                submission = Submission.model_validate(event["payload"])
                success = await self.checker.check(submission, connection=connection)
            await outbox.finish(event["submission_id"], success, self.retry_delay)
        return True

    async def run(self) -> None:
        while True:
            try:
                if await self.process_once():
                    continue
            except Exception:
                logger.exception("Outbox processing failed; will retry")
            await asyncio.sleep(1)


async def main() -> None:
    settings = get_settings()
    if not settings.checker.url:
        raise SystemExit("Set CHECKER__URL before starting the outbox worker")
    database = Database(settings.database)
    await database.connect()
    try:
        async with httpx.AsyncClient(timeout=settings.checker.timeout) as client:
            checker = CheckerService(database, client, settings.checker)
            await OutboxWorker(database, checker).run()
    finally:
        await database.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
