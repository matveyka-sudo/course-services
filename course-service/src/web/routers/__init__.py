from src.web.routers.artifacts import router as artifacts_router
from src.web.routers.assignments import router as assignments_router
from src.web.routers.courses import router as courses_router
from src.web.routers.reviews import router as reviews_router
from src.web.routers.service import service_router
from src.web.routers.submissions import router as submissions_router

routers = (
    service_router,
    courses_router,
    assignments_router,
    submissions_router,
    reviews_router,
    artifacts_router,
)

__all__ = ["routers", "service_router"]
