"""Structured logging for CodeLupe Python services."""

import logging
import os
import sys
from typing import Any, Dict, Optional

import structlog


def configure_logging(
    service: str,
    level: str = "INFO",
    json_output: bool = False,
    log_file: Optional[str] = None,
) -> structlog.BoundLogger:
    """
    Configure structured logging for the application.

    Args:
        service: Name of the service
        level: Log level (DEBUG, INFO, WARN, ERROR)
        json_output: If True, output JSON format. If False, use console format.
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    # Parse log level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add service and version to all logs
    structlog.contextvars.bind_contextvars(
        service=service,
        version=os.getenv("APP_VERSION", "dev"),
    )

    if json_output:
        # JSON output for production
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Console output for development
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        logging.root.addHandler(file_handler)

    return structlog.get_logger()


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a logger instance.

    Args:
        name: Optional logger name

    Returns:
        Logger instance
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class."""

    @property
    def logger(self) -> structlog.BoundLogger:
        """Get logger instance for this class."""
        if not hasattr(self, "_logger"):
            self._logger = structlog.get_logger(self.__class__.__name__)
        return self._logger


def setup_default_logging(service: str) -> structlog.BoundLogger:
    """
    Setup logging with defaults from environment variables.

    Environment variables:
        LOG_LEVEL: Log level (default: INFO)
        LOG_JSON: Use JSON output (default: false)
        LOG_FILE: Optional log file path

    Args:
        service: Name of the service

    Returns:
        Configured logger instance
    """
    return configure_logging(
        service=service,
        level=os.getenv("LOG_LEVEL", "INFO"),
        json_output=os.getenv("LOG_JSON", "false").lower() == "true",
        log_file=os.getenv("LOG_FILE"),
    )


# Example usage:
#
# from src.python.utils.logger import setup_default_logging, get_logger
#
# # Setup logging once at application startup
# setup_default_logging("trainer")
#
# # Get logger in your modules
# logger = get_logger(__name__)
#
# # Use the logger
# logger.info("training_started", model="qwen-14b", batch_size=4)
# logger.error("training_failed", error=str(e), epoch=epoch)
#
# # Add context
# logger = logger.bind(request_id="123", user_id="abc")
# logger.info("processing_request")
