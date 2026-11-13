"""Structured single-line logger (container logs are the only sink)."""
import json
import logging
import sys
from datetime import datetime, timezone

LOGGER = logging.getLogger("partfit")
if not LOGGER.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
    LOGGER.setLevel(logging.INFO)


def log_event(event: str, **fields) -> None:
    payload = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
    LOGGER.info(json.dumps(payload, ensure_ascii=False, default=str))
