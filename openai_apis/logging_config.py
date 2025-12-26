#!/usr/bin/env python3
"""
Centralized Logging Configuration Module

Provides structured logging with audit trails for all API modules.
Supports console and file logging with rotation, structured formats,
and correlation IDs for request tracking.

Features:
- Structured JSON logging for production
- Human-readable console logging for development
- Log rotation with size and time-based policies
- Correlation ID tracking for request tracing
- Separate audit trail logging
- Performance metrics logging
- Configurable log levels per module

Example usage:
    from logging_config import get_logger, log_audit_event

    logger = get_logger(__name__)
    logger.info("Operation started", extra={"user_id": "123"})

    log_audit_event(
        event_type="transcription",
        user_id="user_123",
        action="audio_transcribed",
        details={"duration": 5.2, "language": "hu"}
    )
"""

import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from contextvars import ContextVar
import uuid


# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if present
        corr_id = correlation_id.get()
        if corr_id:
            log_data["correlation_id"] = corr_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data)


class AuditFormatter(logging.Formatter):
    """Special formatter for audit trail logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format audit log record."""
        audit_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": getattr(record, 'event_type', 'unknown'),
            "user_id": getattr(record, 'user_id', None),
            "session_id": getattr(record, 'session_id', None),
            "correlation_id": correlation_id.get(),
            "action": getattr(record, 'action', record.getMessage()),
            "details": getattr(record, 'details', {}),
            "status": getattr(record, 'status', 'success'),
        }
        return json.dumps(audit_data)


class ContextFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to record."""
        record.correlation_id = correlation_id.get() or "none"
        return True


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    enable_audit: bool = True,
    json_format: bool = False
) -> None:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files (default: ./logs).
        enable_console: Enable console logging.
        enable_file: Enable file logging.
        enable_audit: Enable separate audit trail logging.
        json_format: Use JSON format for console output.
    """
    # Create log directory
    if log_dir is None:
        log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    root_logger.handlers = []

    # Console handler
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)

        if json_format:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(console_formatter)

        console_handler.addFilter(ContextFilter())
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if enable_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(StructuredFormatter())
        file_handler.addFilter(ContextFilter())
        root_logger.addHandler(file_handler)

    # Audit trail handler
    if enable_audit:
        audit_handler = logging.handlers.RotatingFileHandler(
            log_dir / "audit.log",
            maxBytes=20 * 1024 * 1024,  # 20MB
            backupCount=10
        )
        audit_handler.setLevel(logging.INFO)
        audit_handler.setFormatter(AuditFormatter())

        # Audit logger
        audit_logger = logging.getLogger("audit")
        audit_logger.setLevel(logging.INFO)
        audit_logger.addHandler(audit_handler)
        audit_logger.propagate = False

    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    error_handler.addFilter(ContextFilter())
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


def set_correlation_id(corr_id: Optional[str] = None) -> str:
    """
    Set correlation ID for current context.

    Args:
        corr_id: Correlation ID (auto-generated if None).

    Returns:
        The correlation ID that was set.
    """
    if corr_id is None:
        corr_id = str(uuid.uuid4())
    correlation_id.set(corr_id)
    return corr_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from context."""
    correlation_id.set(None)


def log_audit_event(
    event_type: str,
    action: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    status: str = "success"
) -> None:
    """
    Log an audit trail event.

    Args:
        event_type: Type of event (e.g., "transcription", "synthesis", "session").
        action: Action performed (e.g., "audio_transcribed", "text_synthesized").
        user_id: User identifier.
        session_id: Session identifier.
        details: Additional details about the event.
        status: Event status (success, failure, error).
    """
    audit_logger = logging.getLogger("audit")

    # Create log record with extra attributes
    record = audit_logger.makeRecord(
        audit_logger.name,
        logging.INFO,
        "(audit)",
        0,
        action,
        (),
        None
    )

    record.event_type = event_type
    record.user_id = user_id
    record.session_id = session_id
    record.details = details or {}
    record.status = status

    audit_logger.handle(record)


def log_performance(
    operation: str,
    duration_ms: float,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log performance metrics.

    Args:
        operation: Operation name.
        duration_ms: Duration in milliseconds.
        details: Additional performance details.
    """
    logger = get_logger("performance")

    perf_data = {
        "operation": operation,
        "duration_ms": duration_ms,
        "correlation_id": get_correlation_id()
    }

    if details:
        perf_data.update(details)

    logger.info(f"Performance: {operation}", extra={"extra_data": perf_data})


def log_api_call(
    api_name: str,
    method: str,
    endpoint: str,
    status_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None
) -> None:
    """
    Log external API call.

    Args:
        api_name: API name (e.g., "OpenAI").
        method: HTTP method.
        endpoint: API endpoint.
        status_code: Response status code.
        duration_ms: Request duration in milliseconds.
        error: Error message if failed.
    """
    logger = get_logger(f"api.{api_name.lower()}")

    call_data = {
        "api": api_name,
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
        "duration_ms": duration_ms,
        "correlation_id": get_correlation_id()
    }

    if error:
        call_data["error"] = error
        logger.error(f"API call failed: {method} {endpoint}", extra={"extra_data": call_data})
    else:
        logger.info(f"API call: {method} {endpoint}", extra={"extra_data": call_data})


# Initialize logging on module import if not already configured
if not logging.getLogger().handlers:
    # Default configuration
    log_level = os.getenv("LOG_LEVEL", "INFO")
    json_format = os.getenv("LOG_FORMAT", "").lower() == "json"

    setup_logging(
        log_level=log_level,
        enable_console=True,
        enable_file=True,
        enable_audit=True,
        json_format=json_format
    )


if __name__ == "__main__":
    # Example usage
    setup_logging(log_level="DEBUG", json_format=False)

    logger = get_logger(__name__)

    # Set correlation ID for request tracking
    set_correlation_id("test-request-123")

    logger.debug("Debug message")
    logger.info("Info message with data", extra={"extra_data": {"key": "value"}})
    logger.warning("Warning message")
    logger.error("Error message")

    # Log audit event
    log_audit_event(
        event_type="transcription",
        action="audio_transcribed",
        user_id="user_123",
        session_id="session_456",
        details={"duration_seconds": 5.2, "language": "hu", "words": 42},
        status="success"
    )

    # Log performance
    log_performance(
        operation="transcribe_audio",
        duration_ms=523.5,
        details={"audio_length_seconds": 5.0, "model": "whisper-1"}
    )

    # Log API call
    log_api_call(
        api_name="OpenAI",
        method="POST",
        endpoint="/v1/audio/transcriptions",
        status_code=200,
        duration_ms=450.2
    )

    print("\nLog files created in ./logs/")
    print("- app.log (all logs)")
    print("- audit.log (audit trail)")
    print("- error.log (errors only)")
