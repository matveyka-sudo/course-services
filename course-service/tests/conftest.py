import pytest
from fastapi.testclient import TestClient

from src.core.config import get_settings
from src.web.app import create_app
from src.web.lifespans import lifespan_app
from src.web.routers import service_router


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def app(settings):
    return create_app(settings, (service_router,), lifespan=lifespan_app)


@pytest.fixture
def app_client(app):
    with TestClient(app) as client:
        yield client
