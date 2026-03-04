"""Dual-format logging system (JSON + plain text) using structlog."""

import logging
import sys
from datetime import datetime

import structlog

from skus2ontology.config import settings


def setup_logging() -> structlog.stdlib.BoundLogger:
    """
    Configure dual-format logging: JSON + plain text.
    Creates log files in both formats based on settings.
    """
    # Ensure log directories exist
    json_log_dir = settings.log_dir / "json"
    text_log_dir = settings.log_dir / "text"
    json_log_dir.mkdir(parents=True, exist_ok=True)
    text_log_dir.mkdir(parents=True, exist_ok=True)

    # Timestamp for log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    # Configure structlog processors
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler (always plain text with colors)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=shared_processors,
        )
    )
    root_logger.addHandler(console_handler)

    # JSON file handler
    if settings.log_format in ("json", "both"):
        json_file = json_log_dir / f"skus2ontology_{timestamp}.json"
        json_handler = logging.FileHandler(json_file, encoding="utf-8")
        json_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.processors.JSONRenderer(),
                foreign_pre_chain=shared_processors,
            )
        )
        root_logger.addHandler(json_handler)

    # Plain text file handler
    if settings.log_format in ("text", "both"):
        text_file = text_log_dir / f"skus2ontology_{timestamp}.log"
        text_handler = logging.FileHandler(text_file, encoding="utf-8")
        text_handler.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=structlog.dev.ConsoleRenderer(colors=False),
                foreign_pre_chain=shared_processors,
            )
        )
        root_logger.addHandler(text_handler)

    return structlog.get_logger()


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a bound logger for a module."""
    return structlog.get_logger(name)
