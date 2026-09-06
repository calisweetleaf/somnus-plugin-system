"""identifiers - production module for the plugin domain.

Source: Somnus Sovereign Systems OS somnus_plugins plus schemas/session.py donor baseline
Integrated: 2026-09-06
Purpose: Provide stdlib-first agnostic plugin identity value objects that sever donor schemas.session coupling without adapter indirection.

"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class IdentifierValidationError(ValueError):
    """Raised when a plugin identity value violates its domain contract."""


class SessionIdPayload(TypedDict):
    """JSON-ready SessionID payload with a single value field."""

    value: str


SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9:_.=-]{0,127}")

MAX_SESSION_ID_LENGTH = 128


@dataclass(frozen=True)
class IdentifiersResult:
    """Structured result for identifiers path description."""

    status: str
    normalized_path: str
    error: str = ""


def describe_path(path: Path) -> IdentifiersResult:
    """Describe a filesystem path without touching external state.

    Args:
        path: Filesystem path to normalize for downstream domain logic.

    Returns:
        Structured result containing the normalized path string.
    """
    normalized_path = path.expanduser()
    return IdentifiersResult(status="ok", normalized_path=str(normalized_path))


@dataclass(frozen=True)
class SessionID:
    """Agnostic session identity value object for the plugin domain.

    Source: Somnus Sovereign Systems OS schemas/session.py SessionID usage
    Integrated: 2026-09-06
    Purpose: Replace the donor schemas.session import with a stdlib-first
        validated identity so plugin_base PluginContext no longer depends
        on the donor codebase.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the wrapped value against the session identity contract."""
        _validate_session_value(self.value)

    @classmethod
    def from_string(cls, raw: str) -> SessionID:
        """Build a SessionID from a raw string.

        Args:
            raw: Candidate session identity with surrounding whitespace allowed.

        Returns:
            Validated SessionID with whitespace removed.

        Raises:
            IdentifierValidationError: If the candidate violates the contract.
        """
        return cls(value=raw.strip())

    def to_string(self) -> str:
        """Return the wrapped session identity string.

        Returns:
            The validated session identity value.
        """
        return self.value

    def to_dict(self) -> SessionIdPayload:
        """Return a JSON-serializable payload for this identity.

        Returns:
            Mapping with a single value field carrying the identity.
        """
        return {"value": self.value}

    @classmethod
    def from_dict(cls, payload: SessionIdPayload) -> SessionID:
        """Rebuild a SessionID from a JSON payload.

        Args:
            payload: Mapping produced by to_dict.

        Returns:
            Validated SessionID matching the payload value.

        Raises:
            IdentifierValidationError: If the payload value violates the contract.
        """
        return cls(value=payload["value"])

    def is_namespaced(self) -> bool:
        """Report whether the identity carries a namespace prefix.

        Returns:
            True when the value contains a colon separator.
        """
        return ":" in self.value

    def namespace(self) -> str:
        """Return the namespace prefix before the first colon.

        Returns:
            Namespace prefix, or an empty string when not namespaced.
        """
        head, separator, _ = self.value.partition(":")
        return head if separator else ""


def _validate_session_value(value: str) -> None:
    """Validate one session identity value against the domain contract.

    Args:
        value: Candidate identity already stripped by the caller path.

    Raises:
        IdentifierValidationError: If the value is empty, oversized, or
            contains characters outside the agnostic identity alphabet.
    """
    if not value:
        raise IdentifierValidationError("SessionID must be a non-empty string.")
    if len(value) > MAX_SESSION_ID_LENGTH:
        raise IdentifierValidationError(
            f"SessionID exceeds {MAX_SESSION_ID_LENGTH} characters."
        )
    if SESSION_ID_PATTERN.fullmatch(value) is None:
        raise IdentifierValidationError(
            "SessionID must start alphanumeric and contain only "
            "alphanumeric, colon, underscore, dot, equals, or hyphen characters."
        )
