from src.web.schemas import ServiceInfo


def get_service_info() -> ServiceInfo:
    """Вернуть состояние сервиса."""

    return ServiceInfo()
