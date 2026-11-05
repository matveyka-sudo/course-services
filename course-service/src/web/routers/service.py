from fastapi import APIRouter

from src.web.schemas.base import ServiceInfo

service_router = APIRouter(prefix="/service", tags=["service"])


@service_router.get("", response_model=ServiceInfo)
async def info() -> ServiceInfo:
    return ServiceInfo()
