from src.application.ports import UnitOfWorkPort
from src.core.exceptions import ServiceError, access_denied, not_found
from src.web.schemas.submissions import Submission, SubmissionCreate
from src.web.schemas.users import Role, User


class CreateSubmissionUseCase:
    def __init__(self, uow: UnitOfWorkPort):
        self.uow = uow

    async def execute(self, data: SubmissionCreate, user: User) -> Submission:
        if user.role != Role.STUDENT:
            raise access_denied()
        assignment = await self.uow.assignments.get(data.assignment_id, lock=True)
        if assignment is None:
            raise not_found("ASSIGNMENT", 422)
        course = await self.uow.courses.get(assignment["course_id"])
        if course is None:
            raise not_found("COURSE")
        if user.id not in course["student_ids"]:
            raise access_denied()
        attempts = await self.uow.submissions.count_attempts(data.assignment_id, user.id)
        if attempts >= 10:
            raise ServiceError(422, "SUBMISSION_LIMIT_REACHED", "Допускается не более 10 попыток на задание")

        values = {**data.model_dump(), "student_id": user.id, "attempt": attempts + 1}
        result = await self.uow.submissions.create(values)
        submission = Submission.model_validate(result)
        await self.uow.outbox.add(submission.id, submission.model_dump(mode="json"))
        return submission
