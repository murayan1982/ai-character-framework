"""Recursive public-safe metadata and error-classification primitives.

FW-RT6-2a Control A defines one provider-neutral safety utility without
migrating existing public models or sessions. Importing this module must not
inspect credentials, import provider SDKs, execute network calls, access a
microphone, perform playback, or connect to VTube Studio.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
import math
from os import PathLike
from pathlib import PurePath
import re
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlsplit


REDACTED_VALUE = "<redacted>"
REDACTED_PATH = "<redacted:path>"
REDACTED_EXCEPTION = "<redacted:exception>"
REDACTED_BINARY = "<redacted:binary>"
REDACTED_OBJECT = "<redacted:object>"
REDACTED_CYCLE = "<redacted:cycle>"
REDACTED_MAX_DEPTH = "<redacted:max-depth>"
REDACTED_NON_FINITE = "<redacted:non-finite>"

PUBLIC_SAFETY_MAX_DEPTH = 12

_SECRET_KEY_COMPACT_FRAGMENTS = (
    "apikey",
    "authorization",
    "bearer",
    "clientsecret",
    "credential",
    "password",
    "privatekey",
    "secret",
    "accesstoken",
    "refreshtoken",
    "idtoken",
    "token",
    "cookie",
)

_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[a-zA-Z]:[\\/]")
_PRIVATE_DIRECTORY_PATH = re.compile(
    r"(^|[\\/])"
    r"(users|home|private|tmp|temp|var|etc|mnt|appdata)"
    r"([\\/]|$)",
    re.IGNORECASE,
)


def _compact_key(value: object) -> str:
    return "".join(character for character in str(value).lower() if character.isalnum())


def is_secret_like_key(value: object) -> bool:
    """Return whether a metadata key is credential- or authorization-like."""

    compact = _compact_key(value)
    return any(fragment in compact for fragment in _SECRET_KEY_COMPACT_FRAGMENTS)


def _url_contains_private_material(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return True

    scheme = parsed.scheme.lower()
    if scheme == "file":
        return True
    if scheme not in {"http", "https"}:
        return False
    if parsed.username is not None or parsed.password is not None:
        return True
    return any(is_secret_like_key(key) for key, _ in parse_qsl(parsed.query))


def looks_like_private_path(value: object) -> bool:
    """Return whether a value is a local/private filesystem path.

    Ordinary HTTP(S) URLs are allowed unless they contain user information or a
    secret-like query key. Opaque identifiers and relative names without a
    private-directory signature are not treated as paths.
    """

    if isinstance(value, (PurePath, PathLike)):
        return True
    if not isinstance(value, str):
        return False

    normalized = value.strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if lowered.startswith(("http://", "https://", "file://")):
        return _url_contains_private_material(normalized)
    if normalized.startswith(("\\\\", "//", "/", "~/", "~\\")):
        return True
    if normalized.startswith(("./", "../", ".\\", "..\\")):
        return True
    if _WINDOWS_ABSOLUTE_PATH.match(normalized):
        return True
    return bool(_PRIVATE_DIRECTORY_PATH.search(normalized))


def _safe_string(value: str) -> str:
    return REDACTED_PATH if looks_like_private_path(value) else value


def _sanitize_container(
    value: object,
    *,
    depth: int,
    max_depth: int,
    active_ids: set[int],
) -> object:
    if depth >= max_depth:
        return REDACTED_MAX_DEPTH

    identity = id(value)
    if identity in active_ids:
        return REDACTED_CYCLE
    active_ids.add(identity)
    try:
        if isinstance(value, Mapping):
            safe: dict[str, object] = {}
            for raw_key, raw_value in value.items():
                key = str(raw_key)
                if is_secret_like_key(key):
                    safe[key] = REDACTED_VALUE
                else:
                    safe[key] = sanitize_public_value(
                        raw_value,
                        max_depth=max_depth,
                        _depth=depth + 1,
                        _active_ids=active_ids,
                    )
            return MappingProxyType(safe)

        if isinstance(value, (list, tuple)):
            return tuple(
                sanitize_public_value(
                    item,
                    max_depth=max_depth,
                    _depth=depth + 1,
                    _active_ids=active_ids,
                )
                for item in value
            )

        if is_dataclass(value) and not isinstance(value, type):
            safe_fields: dict[str, object] = {}
            for dataclass_field in fields(value):
                name = dataclass_field.name
                if is_secret_like_key(name):
                    safe_fields[name] = REDACTED_VALUE
                else:
                    safe_fields[name] = sanitize_public_value(
                        getattr(value, name),
                        max_depth=max_depth,
                        _depth=depth + 1,
                        _active_ids=active_ids,
                    )
            return MappingProxyType(safe_fields)
    finally:
        active_ids.remove(identity)

    return REDACTED_OBJECT


def sanitize_public_value(
    value: object,
    *,
    max_depth: int = PUBLIC_SAFETY_MAX_DEPTH,
    _depth: int = 0,
    _active_ids: set[int] | None = None,
) -> object:
    """Recursively convert a value into an immutable public-safe representation.

    Supported structures are mappings, lists, tuples, dataclass instances, and
    enums. Unknown objects are never converted through ``str`` or ``repr``.
    Exceptions, binary values, private paths, cycles, excessive nesting, and
    non-finite numbers are replaced with stable redaction markers.
    """

    if isinstance(max_depth, bool) or not isinstance(max_depth, int):
        raise TypeError("max_depth must be an integer")
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")

    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else REDACTED_NON_FINITE
    if isinstance(value, str):
        return _safe_string(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return REDACTED_BINARY
    if isinstance(value, BaseException):
        return REDACTED_EXCEPTION
    if isinstance(value, (PurePath, PathLike)):
        return REDACTED_PATH
    if isinstance(value, Enum):
        return sanitize_public_value(
            value.value,
            max_depth=max_depth,
            _depth=_depth,
            _active_ids=_active_ids,
        )

    active_ids = _active_ids if _active_ids is not None else set()
    if isinstance(value, (Mapping, list, tuple)) or (
        is_dataclass(value) and not isinstance(value, type)
    ):
        return _sanitize_container(
            value,
            depth=_depth,
            max_depth=max_depth,
            active_ids=active_ids,
        )

    return REDACTED_OBJECT


def public_mapping(
    values: Mapping[object, object] | None,
    *,
    max_depth: int = PUBLIC_SAFETY_MAX_DEPTH,
) -> Mapping[str, object]:
    """Return one recursively sanitized immutable public metadata mapping."""

    if values is None:
        return MappingProxyType({})
    if not isinstance(values, Mapping):
        raise TypeError("public metadata must be a mapping or None")
    sanitized = sanitize_public_value(values, max_depth=max_depth)
    if not isinstance(sanitized, Mapping):
        raise AssertionError("sanitized public metadata must remain a mapping")
    return sanitized


@dataclass(frozen=True, slots=True)
class PublicErrorClassification:
    """Provider-neutral safe classification with no raw exception material."""

    public_error_code: str
    safe_message: str
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.public_error_code, str) or not self.public_error_code.strip():
            raise ValueError("public_error_code must be a non-empty string")
        if not isinstance(self.safe_message, str) or not self.safe_message.strip():
            raise ValueError("safe_message must be a non-empty string")

        safe_message = _safe_string(self.safe_message.strip())
        if safe_message == REDACTED_PATH:
            safe_message = "The operation failed."

        object.__setattr__(self, "public_error_code", self.public_error_code.strip())
        object.__setattr__(self, "safe_message", safe_message)
        object.__setattr__(self, "retryable", bool(self.retryable))
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )


def classify_public_exception(
    error: BaseException,
    *,
    fallback_error_code: str = "unknown_error",
    fallback_safe_message: str = "The operation failed.",
    fallback_retryable: bool = False,
) -> PublicErrorClassification:
    """Classify built-in exception categories without exposing raw details.

    The function intentionally does not call ``str(error)``, ``repr(error)``,
    inspect provider payloads, or return the exception class name. Provider- or
    operation-specific mapping remains a later consumer-adoption responsibility.
    """

    if not isinstance(error, BaseException):
        raise TypeError("error must be an exception")

    if isinstance(error, TimeoutError):
        return PublicErrorClassification(
            public_error_code="timeout",
            safe_message="The operation timed out.",
            retryable=True,
            public_metadata={"error_category": "timeout"},
        )
    if isinstance(error, InterruptedError):
        return PublicErrorClassification(
            public_error_code="request_cancelled",
            safe_message="The operation was cancelled or interrupted.",
            retryable=True,
            public_metadata={"error_category": "cancelled"},
        )
    if isinstance(error, PermissionError):
        return PublicErrorClassification(
            public_error_code="authentication_required",
            safe_message="Authentication or permission is required.",
            retryable=False,
            public_metadata={"error_category": "permission"},
        )
    if isinstance(error, ConnectionError):
        return PublicErrorClassification(
            public_error_code="provider_unavailable",
            safe_message="The requested service is unavailable.",
            retryable=True,
            public_metadata={"error_category": "connection"},
        )
    if isinstance(error, (TypeError, ValueError)):
        return PublicErrorClassification(
            public_error_code="invalid_request",
            safe_message="The request is invalid.",
            retryable=False,
            public_metadata={"error_category": "invalid_request"},
        )

    return PublicErrorClassification(
        public_error_code=fallback_error_code,
        safe_message=fallback_safe_message,
        retryable=fallback_retryable,
        public_metadata={"error_category": "unclassified"},
    )
