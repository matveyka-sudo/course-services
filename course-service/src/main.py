from src.core.config import get_settings
from src.core.logging import configure_logging
from src.web.app import create_app

settings = get_settings()
configure_logging(settings.log_level)
app = create_app(settings)
