"""Structured logging system for Phonenv.

This module provides a centralized logging infrastructure to replace
scattered print() statements throughout the codebase. It supports
multiple log levels, structured output, and configurable verbosity.
"""

from __future__ import annotations

import logging
import sys
from enum import Enum
from pathlib import Path
from typing import Optional


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class PhonenvLogger:
    """Structured logger for Phonenv application.

    Provides consistent logging interface with support for:
    - Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - File and console output
    - Structured log messages with context
    - Progress reporting for batch operations
    """

    def __init__(
        self,
        name: str = "phonenv",
        level: LogLevel = LogLevel.INFO,
        log_file: Optional[str | Path] = None,
        console: bool = True,
    ):
        """Initialize logger.

        Args:
            name: Logger name (default: "phonenv")
            level: Minimum log level to display
            log_file: Optional file path for log output
            console: Whether to output to console (default: True)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level.value)
        self.logger.handlers.clear()  # Remove any existing handlers

        # Console handler
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(level.value)
            console_formatter = logging.Formatter(
                "%(levelname)s: %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        # File handler
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)  # Always log everything to file
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

    def debug(self, message: str, **context) -> None:
        """Log debug message with optional context."""
        if context:
            message = f"{message} | {self._format_context(context)}"
        self.logger.debug(message)

    def info(self, message: str, **context) -> None:
        """Log info message with optional context."""
        if context:
            message = f"{message} | {self._format_context(context)}"
        self.logger.info(message)

    def warning(self, message: str, **context) -> None:
        """Log warning message with optional context."""
        if context:
            message = f"{message} | {self._format_context(context)}"
        self.logger.warning(message)

    def error(self, message: str, **context) -> None:
        """Log error message with optional context."""
        if context:
            message = f"{message} | {self._format_context(context)}"
        self.logger.error(message)

    def critical(self, message: str, **context) -> None:
        """Log critical message with optional context."""
        if context:
            message = f"{message} | {self._format_context(context)}"
        self.logger.critical(message)

    def cache_hit(self, target: str, dataset: str) -> None:
        """Log cache hit."""
        self.debug(f"Cache hit", target=target, dataset=Path(dataset).name)

    def cache_miss(self, target: str, dataset: str) -> None:
        """Log cache miss."""
        self.debug(f"Cache miss", target=target, dataset=Path(dataset).name)

    def cache_error(self, operation: str, error: Exception, **context) -> None:
        """Log cache operation error."""
        self.error(
            f"Cache {operation} failed: {error}", error_type=type(error).__name__, **context
        )

    def validation_error(
        self, file_path: str, error_count: int, **context
    ) -> None:
        """Log validation error."""
        self.error(
            f"Validation failed for {file_path}",
            error_count=error_count,
            **context,
        )

    def batch_progress(
        self, current: int, total: int, target: str, cached: bool = False
    ) -> None:
        """Log batch processing progress."""
        status = "cached" if cached else "analyzed"
        self.info(
            f"[{current}/{total}] Analyzing '{target}' ({status})",
            progress=f"{current}/{total}",
        )

    def analysis_start(self, target: str, mode: str, **context) -> None:
        """Log analysis start."""
        self.info(
            f"Starting analysis for '{target}'", mode=mode, **context
        )

    def analysis_complete(
        self, target: str, occurrences: int, **context
    ) -> None:
        """Log analysis completion."""
        self.info(
            f"Analysis complete for '{target}'",
            occurrences=occurrences,
            **context,
        )

    def _format_context(self, context: dict) -> str:
        """Format context dictionary as key=value pairs."""
        return " | ".join(f"{k}={v}" for k, v in context.items())


# Global logger instance
_global_logger: Optional[PhonenvLogger] = None


def get_logger(
    name: str = "phonenv",
    level: LogLevel = LogLevel.INFO,
    log_file: Optional[str | Path] = None,
    console: bool = True,
) -> PhonenvLogger:
    """Get or create global logger instance.

    Args:
        name: Logger name (default: "phonenv")
        level: Minimum log level to display
        log_file: Optional file path for log output
        console: Whether to output to console (default: True)

    Returns:
        Global PhonenvLogger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = PhonenvLogger(
            name=name, level=level, log_file=log_file, console=console
        )
    return _global_logger


def set_log_level(level: LogLevel) -> None:
    """Set global log level.

    Args:
        level: New log level
    """
    logger = get_logger()
    logger.logger.setLevel(level.value)
    for handler in logger.logger.handlers:
        handler.setLevel(level.value)


__all__ = [
    "PhonenvLogger",
    "LogLevel",
    "get_logger",
    "set_log_level",
]
