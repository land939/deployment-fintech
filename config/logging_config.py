"""Logging configuration."""

import logging
import logging.handlers
from pathlib import Path

from config.settings import Settings


def setup_logging(settings: Settings) -> None:
    """Configure logging for the application."""
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level))
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (general logs)
    if settings.log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            settings.log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setLevel(getattr(logging, settings.log_level))
        file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Security audit logger
    audit_logger = logging.getLogger("audit")
    if settings.audit_log_file:
        audit_handler = logging.handlers.RotatingFileHandler(
            settings.audit_log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        audit_handler.setLevel(logging.INFO)
        audit_formatter = logging.Formatter("%(asctime)s | %(name)s | %(message)s")
        audit_handler.setFormatter(audit_formatter)
        audit_logger.addHandler(audit_handler)
        audit_logger.setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "✅ Logging configured: level=%s, file=%s",
        settings.log_level,
        settings.log_file or "console only",
    )
