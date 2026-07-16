"""
Structured JSON Logger with Correlation ID support.

Usage:
    from src.utils.logger import get_logger, set_correlation_id
    import uuid

    set_correlation_id(str(uuid.uuid4()))
    logger = get_logger("devops-agent.pipeline")
    logger.info("Stage started", stage="Docker", model="Gemini")
"""

import json
import logging
import time
import uuid
from contextvars import ContextVar

# ─── Correlation ID (unique per pipeline run) ───────────────────
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


def set_correlation_id(cid: str | None = None) -> str:
    """Set the correlation ID for the current pipeline run. Returns the ID."""
    if cid is None:
        cid = str(uuid.uuid4())[:8]
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return _correlation_id.get()


# ─── JSON Formatter ─────────────────────────────────────────────

class StructuredFormatter(logging.Formatter):
    """Outputs each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }

        # Inject correlation ID if set
        cid = _correlation_id.get()
        if cid:
            log_entry["correlation_id"] = cid

        # Merge any extra fields passed via `extra={"stage": ..., "model": ...}`
        for key in ("stage", "model", "latency", "tokens", "decision", "error_type", "attempt"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry)


# ─── Console Formatter (human-friendly during local dev) ────────

class DevFormatter(logging.Formatter):
    """Pretty console output for local development."""

    ICONS = {
        "DEBUG": "🔍",
        "INFO": "ℹ️ ",
        "WARNING": "⚠️ ",
        "ERROR": "❌",
        "CRITICAL": "🔥",
    }

    def format(self, record: logging.LogRecord) -> str:
        icon = self.ICONS.get(record.levelname, "")
        cid = _correlation_id.get()
        prefix = f"[{cid}] " if cid else ""

        extras = []
        for key in ("stage", "model", "latency", "decision"):
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")

        extra_str = f" ({', '.join(extras)})" if extras else ""
        return f"{icon} {prefix}{record.getMessage()}{extra_str}"


# ─── Logger Factory ─────────────────────────────────────────────

_configured = False


def configure_logging(json_mode: bool = False, level: int = logging.INFO):
    """
    Configure the root devops-agent logger.

    Args:
        json_mode: If True, output structured JSON (production).
                   If False, output human-friendly (development).
        level: Logging level.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root_logger = logging.getLogger("devops-agent")
    root_logger.setLevel(level)

    handler = logging.StreamHandler()
    if json_mode:
        handler.setFormatter(StructuredFormatter())
    else:
        handler.setFormatter(DevFormatter())

    root_logger.addHandler(handler)

    # Prevent propagation to root logger (avoids duplicate output)
    root_logger.propagate = False


def get_logger(name: str = "devops-agent") -> logging.Logger:
    """Get a named logger under the devops-agent namespace."""
    configure_logging()
    return logging.getLogger(name)
