"""Public exports for the plugin domain.

Source: Somnus Sovereign Systems OS somnus_plugins plus schemas/session.py donor baseline
Integrated: 2026-09-06
Purpose: Provide stdlib-first agnostic plugin identity value objects that sever donor schemas.session coupling without adapter indirection.

"""
from __future__ import annotations

from .identifiers import IdentifiersResult, SessionID, SessionIdPayload, describe_path

__all__ = [
    "IdentifiersResult",
    "SessionID",
    "SessionIdPayload",
    "describe_path",
]
