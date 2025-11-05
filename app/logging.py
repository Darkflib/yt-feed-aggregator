"""Logging configuration for YouTube Feed Aggregator."""

import json
import logging
import sys

from app.config import get_settings


class JsonFormatter(logging.Formatter):
    """JSON formatter for production logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        base = {
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base)


def setup_logging() -> None:
    """Configure logging based on environment."""
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)

    if settings.env == "prod":
        handler.setFormatter(JsonFormatter())
    else:
        # Pretty format for development
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
