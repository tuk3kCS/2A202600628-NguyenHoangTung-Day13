from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import structlog
from structlog.contextvars import merge_contextvars

from .pii import scrub_text

LOG_PATH = Path(os.getenv("LOG_PATH", "data/logs.jsonl"))


class JsonlFileProcessor:
    def __call__(self, logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        rendered = structlog.processors.JSONRenderer()(logger, method_name, event_dict)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(rendered + "\n")
        return event_dict



def scrub_event(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    def scrub_val(v: Any) -> Any:
        if isinstance(v, str):
            return scrub_text(v)
        elif isinstance(v, dict):
            return {k: scrub_val(val) for k, val in v.items()}
        elif isinstance(v, list):
            return [scrub_val(item) for item in v]
        return v

    protected_keys = {"ts", "level", "service", "correlation_id", "env"}
    for k, v in event_dict.items():
        if k not in protected_keys:
            event_dict[k] = scrub_val(v)
    return event_dict



def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")))
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
            # Register your PII scrubbing processor here
            scrub_event,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            JsonlFileProcessor(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )



def get_logger() -> structlog.typing.FilteringBoundLogger:
    return structlog.get_logger()


AUDIT_LOG_PATH = Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))


def log_audit(event: str, user: str, correlation_id: str | None = None, payload: dict | None = None) -> None:
    import json
    from datetime import datetime, timezone
    
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    clean_event = scrub_text(event)
    clean_payload = None
    if payload:
        def scrub_val(v: Any) -> Any:
            if isinstance(v, str):
                return scrub_text(v)
            elif isinstance(v, dict):
                return {k: scrub_val(val) for k, val in v.items()}
            elif isinstance(v, list):
                return [scrub_val(item) for item in v]
            return v
        clean_payload = scrub_val(payload)
        
    record = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": "info",
        "service": "audit",
        "event": clean_event,
        "user": user,
        "correlation_id": correlation_id or "N/A",
        "payload": clean_payload,
    }
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
