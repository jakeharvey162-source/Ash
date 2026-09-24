from __future__ import annotations
import json, sys, time
from typing import Any, TextIO

def emit(event_type: str, *, stream: TextIO | None = None, **fields: Any) -> dict[str, Any]:
    event = {"type": event_type, "ts": time.time(), **fields}
    print(json.dumps(event, ensure_ascii=False), file=stream or sys.stdout, flush=True)
    return event
