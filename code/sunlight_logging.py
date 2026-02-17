"""
SUNLIGHT Structured Logging
============================

Every detection decision must be traceable. This module provides:
- JSON-structured log output for machine parsing
- Human-readable console output for development
- Per-contract decision logging for audit compliance
- Run-level summary logging

Usage:
    from sunlight_logging import get_logger
    logger = get_logger(__name__)
    logger.info("message", extra={"contract_id": "X", "tier": "RED"})
"""

import logging
import json
import sys
import os
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON-structured log formatter for production use.

    Every log line is a valid JSON object with:
    - timestamp (ISO 8601 UTC)
    - level
    - logger name
    - message
    - Any extra fields (contract_id, run_id, tier, etc.)
    """

    RESERVED_ATTRS = {
        'name', 'msg', 'args', 'created', 'relativeCreated', 'exc_info',
        'exc_text', 'stack_info', 'lineno', 'funcName', 'filename',
        'module', 'pathname', 'thread', 'threadName', 'processName',
        'process', 'message', 'levelname', 'levelno', 'msecs', 'taskName',
    }

    def format(self, record):
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include any extra fields passed via `extra={}`
        for key, value in record.__dict__.items():
            if key not in self.RESERVED_ATTRS and not key.startswith('_'):
                try:
                    json.dumps(value)  # Ensure serializable
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        if record.exc_info and record.exc_info[0]:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter for development."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime('%H:%M:%S')

        # Build extra context string
        extras = []
        for key, value in record.__dict__.items():
            if key not in StructuredFormatter.RESERVED_ATTRS and not key.startswith('_'):
                extras.append(f"{key}={value}")
        extra_str = f" [{', '.join(extras)}]" if extras else ""

        return f"{color}{ts} {record.levelname:8s}{self.RESET} {record.name}: {record.getMessage()}{extra_str}"


def get_logger(name: str, level: str = None) -> logging.Logger:
    """Get a configured SUNLIGHT logger.

    Args:
        name: Logger name (typically __name__)
        level: Override log level (DEBUG/INFO/WARNING/ERROR)

    Environment variables:
        SUNLIGHT_LOG_LEVEL: Default log level (default: INFO)
        SUNLIGHT_LOG_FORMAT: "json" for structured, "console" for human-readable (default: console)
        SUNLIGHT_LOG_FILE: Path to log file (optional, in addition to stderr)
    """
    logger = logging.getLogger(f"sunlight.{name}")

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    log_level = level or os.environ.get("SUNLIGHT_LOG_LEVEL", "INFO")
    log_format = os.environ.get("SUNLIGHT_LOG_FORMAT", "console")
    log_file = os.environ.get("SUNLIGHT_LOG_FILE")

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.propagate = False

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    if log_format == "json":
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    # File handler (always JSON for machine parsing)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        logger.addHandler(file_handler)

    return logger
