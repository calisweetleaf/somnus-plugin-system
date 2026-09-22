"""Agent actions declared by the somnus_reference manifest.

The loader does not dispatch these names. The plugin records them so a host
can read the catalog from lifecycle state after activation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


def catalog() -> List[str]:
    return ["describe_contract", "record_observation"]


def record_observation(note: str) -> Dict[str, Any]:
    text = note.strip()
    if not text:
        raise ValueError("observation note is empty")
    return {
        "action": "record_observation",
        "note": text,
        "at": datetime.now(timezone.utc).isoformat(),
    }
