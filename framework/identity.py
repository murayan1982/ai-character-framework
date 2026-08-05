"""Provider-neutral public identity primitives for v6 correlation.

The types in this module are serialization-friendly scalar subclasses. They do
not contain provider identifiers, timestamps, filesystem paths, credentials, or
host-application data.
"""

from __future__ import annotations

import re
from typing import ClassVar, TypeVar
from uuid import uuid4

_HEX_SUFFIX = re.compile(r"^[0-9a-f]{32}$")
_OpaqueIdT = TypeVar("_OpaqueIdT", bound="_OpaqueId")


class _OpaqueId(str):
    """Validated Framework-owned opaque string identity."""

    _prefix: ClassVar[str]
    _kind: ClassVar[str]

    def __new__(cls: type[_OpaqueIdT], value: str) -> _OpaqueIdT:
        if not isinstance(value, str):
            raise TypeError(f"{cls.__name__} value must be a string")
        if value != value.strip():
            raise ValueError(f"{cls.__name__} must not contain surrounding whitespace")
        if not value.startswith(cls._prefix):
            raise ValueError(f"Invalid {cls._kind} identifier.")
        suffix = value[len(cls._prefix) :]
        if not _HEX_SUFFIX.fullmatch(suffix):
            raise ValueError(f"Invalid {cls._kind} identifier.")
        return str.__new__(cls, value)

    @classmethod
    def new(cls: type[_OpaqueIdT]) -> _OpaqueIdT:
        """Create a new Framework-owned provider-neutral identity."""

        return cls(f"{cls._prefix}{uuid4().hex}")

    @classmethod
    def parse(cls: type[_OpaqueIdT], value: str) -> _OpaqueIdT:
        """Validate and normalize one serialized identity value."""

        if isinstance(value, cls):
            return value
        return cls(value)

    def to_json_value(self) -> str:
        """Return the JSON scalar representation."""

        return str(self)


class SessionId(_OpaqueId):
    """Opaque identity for one public Framework session."""

    _prefix = "fw_session_"
    _kind = "session"


class TurnId(_OpaqueId):
    """Opaque identity for one host-visible turn within a session."""

    _prefix = "fw_turn_"
    _kind = "turn"


class GenerationId(_OpaqueId):
    """Opaque identity for one Framework generation/stage attempt."""

    _prefix = "fw_generation_"
    _kind = "generation"


class EventSequence(int):
    """Positive session-local event sequence number."""

    def __new__(cls, value: int) -> "EventSequence":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("EventSequence value must be an integer")
        if value < 1:
            raise ValueError("EventSequence value must be at least 1")
        return int.__new__(cls, value)

    @classmethod
    def first(cls) -> "EventSequence":
        """Return the first public event sequence value."""

        return cls(1)

    @classmethod
    def parse(cls, value: int) -> "EventSequence":
        """Validate and normalize one serialized sequence value."""

        if isinstance(value, cls):
            return value
        return cls(value)

    def next(self) -> "EventSequence":
        """Return the next monotonic sequence value."""

        return type(self)(int(self) + 1)

    def to_json_value(self) -> int:
        """Return the JSON scalar representation."""

        return int(self)


_FRAMEWORK_ID_PREFIX = "fw_"


def _normalize_compatible_id(
    value: _OpaqueIdT | str | None,
    *,
    expected_type: type[_OpaqueIdT],
    field_name: str,
) -> _OpaqueIdT | str | None:
    """Normalize v6 serialized IDs while preserving legacy host strings.

    Values that use the reserved ``fw_`` namespace must validate as the
    expected identity kind. Non-prefixed strings remain unchanged for v5 host
    compatibility and are never reclassified as Framework-owned identities.
    """

    if value is None or isinstance(value, expected_type):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string or None")
    if value.startswith(expected_type._prefix):
        return expected_type.parse(value)
    if value.startswith(_FRAMEWORK_ID_PREFIX) or value.strip().startswith(
        _FRAMEWORK_ID_PREFIX
    ):
        raise ValueError(f"{field_name} contains an invalid Framework identity")
    return value


def normalize_session_id(
    value: SessionId | str | None,
) -> SessionId | str | None:
    """Normalize a session ID without breaking legacy host strings."""

    return _normalize_compatible_id(
        value, expected_type=SessionId, field_name="session_id"
    )


def normalize_turn_id(value: TurnId | str | None) -> TurnId | str | None:
    """Normalize a turn ID without breaking legacy host strings."""

    return _normalize_compatible_id(
        value, expected_type=TurnId, field_name="turn_id"
    )


__all__ = [
    "SessionId",
    "TurnId",
    "GenerationId",
    "EventSequence",
]
