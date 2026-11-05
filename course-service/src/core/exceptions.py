class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message
        super().__init__(message)


def not_found(entity: str, status: int = 404) -> ServiceError:
    messages = {
        "COURSE": "Курс не существует",
        "ASSIGNMENT": "Задание не найдено",
        "SUBMISSION": "Решение не существует",
        "REVIEW": "Ревью не существует",
    }
    return ServiceError(status, f"{entity}_NOT_FOUND", messages[entity])


def access_denied() -> ServiceError:
    return ServiceError(403, "ACCESS_DENIED", "Недостаточно прав доступа")
