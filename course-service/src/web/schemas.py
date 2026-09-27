from pydantic import BaseModel, ConfigDict


class BaseSchemaModel(BaseModel):
    """Общие настройки для моделей ответов"""

    model_config = ConfigDict(
        from_attributes=True,
        validate_assignment=True,
        populate_by_name=True,
    )


class ServiceInfo(BaseSchemaModel):
    """Ответ о состоянии сервиса"""

    healthy: bool = True
