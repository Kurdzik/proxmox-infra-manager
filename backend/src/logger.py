import logging
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from contextvars import ContextVar
from typing import Any

import structlog
from sqlmodel import Session
from src.models import Logs

_log_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


class DatabaseHandler(logging.Handler):
    """Custom logging handler that writes logs to the database."""

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        db_level_name = os.getenv("LOG_DB_LEVEL", "WARNING").upper()
        self.db_level = getattr(logging, db_level_name, logging.WARNING)
        self.setLevel(logging.INFO)

    def _should_persist(self, record, formatted_message: str) -> bool:
        if record.levelno >= self.db_level:
            return True
        try:
            return bool(json.loads(formatted_message).get("persist_db"))
        except (json.JSONDecodeError, TypeError):
            return False

    def emit(self, record):
        try:
            context = _log_context.get()
            tenant_id = context.get("tenant_id")
            if not tenant_id:
                return

            service_name = context.get("service_name", "unknown")
            formatted_message = self.format(record)
            if not self._should_persist(record, formatted_message):
                return

            log_entry = Logs(
                tenant_id=tenant_id,
                service_name=service_name,
                log=formatted_message,
                timestamp=datetime.now(),
            )
            with Session(self.engine) as session:
                session.add(log_entry)
                session.commit()
        except Exception:
            self.handleError(record)


def configure_logger(engine, service_name: str = "default"):
    """Configure structlog once at application startup."""

    def add_context(logger, method_name, event_dict):
        context = _log_context.get()
        if context:
            event_dict.update({k: v for k, v in context.items() if v is not None})
        event_dict.setdefault("service_name", service_name)
        return event_dict

    structlog.configure(
        processors=[
            add_context,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    )

    logger = logging.getLogger()
    if any(isinstance(h, DatabaseHandler) for h in logger.handlers):
        return

    db_handler = DatabaseHandler(engine)
    logger.addHandler(db_handler)


def get_logger(name: str = __name__):
    return structlog.get_logger(name)


@contextmanager
def log_context(**context: Any):
    """Temporarily attach structured context fields to log events."""
    current = _log_context.get().copy()
    current.update({k: v for k, v in context.items() if v is not None})
    token = _log_context.set(current)
    try:
        yield
    finally:
        _log_context.reset(token)


@contextmanager
def tenant_context(tenant_id: str, service_name: str = "default"):
    with log_context(tenant_id=tenant_id, service_name=service_name):
        yield
