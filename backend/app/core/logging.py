import json
import logging
from typing import Any


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit JSON logs. Callers must pass only non-secret operational fields."""
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))
