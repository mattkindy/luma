"""Logging configuration."""

import logging
import os
import sys

from pydantic import BaseModel


class LogConfig(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"


def setup_logging(config: LogConfig | None = None) -> None:
    """Set up logging configuration for the application."""
    if config is None:
        config = LogConfig()

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.level.upper()),
        format=config.format,
        datefmt=config.date_format,
        stream=sys.stdout,
        force=True,  # Override any existing configuration
    )

    # Set specific log levels for third-party libraries
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    log_level = level if level else os.getenv("LOG_LEVEL", "INFO")
    logger.setLevel(log_level.upper())

    return logger
