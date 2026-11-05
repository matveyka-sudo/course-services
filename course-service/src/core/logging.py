import logging
import logging.config
from contextvars import ContextVar

import yaml

from src.core.config import ROOT

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    configuration = yaml.safe_load((ROOT / "log-config.yaml").read_text())
    configuration["root"]["level"] = level
    logging.config.dictConfig(configuration)
