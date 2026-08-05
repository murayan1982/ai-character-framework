"""Provider-neutral public capability snapshot for FW host apps.

This module is intentionally lightweight. Importing it must not import provider
SDKs, runtime audio modules, voice input adapters, motion adapters, or
application-specific configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

from .version import CAPABILITIES_SCHEMA_VERSION


CapabilityState = Literal[
    "supported",
    "configured",
    "available",
    "blocked",
    "unavailable",
    "fallback",
]


@dataclass(frozen=True, slots=True)
class CapabilityStatus:
    """Provider-neutral status for one public framework capability.

    `supported`, `configured`, and `available` are deliberately separate.
    A feature can be implemented but not configured, configured but blocked by a
    guard, or detected but not currently available.
    """

    name: str
    status: CapabilityState
    supported: bool
    configured: bool
    available: bool
    blocked: bool = False
    reason_code: str | None = None
    safe_message: str | None = None
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        """Whether the capability is currently usable by a host app."""

        return self.available and not self.blocked

    @property
    def is_unavailable(self) -> bool:
        """Whether the capability is not currently usable."""

        return not self.is_available

    def to_public_dict(self) -> dict[str, object]:
        """Return a provider-neutral dictionary representation."""

        return {
            "name": self.name,
            "status": self.status,
            "supported": self.supported,
            "configured": self.configured,
            "available": self.available,
            "blocked": self.blocked,
            "reason_code": self.reason_code,
            "safe_message": self.safe_message,
            "public_metadata": dict(self.public_metadata),
        }


@dataclass(frozen=True, slots=True)
class FrameworkCapabilities:
    """Versioned snapshot of public FW capabilities."""

    schema_version: str
    text_chat: CapabilityStatus
    voice_output: CapabilityStatus
    voice_input: CapabilityStatus
    realtime: CapabilityStatus
    motion: CapabilityStatus
    public_metadata: Mapping[str, str] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, object]:
        """Return a provider-neutral dictionary representation."""

        return {
            "schema_version": self.schema_version,
            "text_chat": self.text_chat.to_public_dict(),
            "voice_output": self.voice_output.to_public_dict(),
            "voice_input": self.voice_input.to_public_dict(),
            "realtime": self.realtime.to_public_dict(),
            "motion": self.motion.to_public_dict(),
            "public_metadata": dict(self.public_metadata),
        }


def get_capabilities(
    *,
    project_root: str | Path | None = None,
    real_tts_enabled: bool | None = None,
) -> FrameworkCapabilities:
    """Return a mock-safe runtime capability snapshot.

    The snapshot reports public boundary status without importing provider SDKs
    or performing provider API calls. It is safe to call during application
    startup and before provider credentials are configured.
    """

    resolved_project_root = Path(project_root).resolve() if project_root is not None else None
    return FrameworkCapabilities(
        schema_version=CAPABILITIES_SCHEMA_VERSION,
        text_chat=_text_chat_capability(),
        voice_output=_voice_output_capability(real_tts_enabled=real_tts_enabled),
        voice_input=_missing_capability("voice_input", "public_boundary_missing", "Voice input public boundary is not implemented yet."),
        realtime=_missing_capability("realtime", "public_boundary_missing", "Realtime public session boundary is not implemented yet."),
        motion=_missing_capability("motion", "public_boundary_missing", "Motion public adapter boundary is not implemented yet."),
        public_metadata={
            "boundary": "capabilities",
            "project_root_provided": "true" if resolved_project_root is not None else "false",
        },
    )


def _text_chat_capability() -> CapabilityStatus:
    return CapabilityStatus(
        name="text_chat",
        status="available",
        supported=True,
        configured=True,
        available=True,
        blocked=False,
        reason_code="public_boundary_available",
        safe_message="Text chat public boundary is available.",
        public_metadata={"boundary": "text_chat"},
    )


def _voice_output_capability(*, real_tts_enabled: bool | None) -> CapabilityStatus:
    enabled = _env_flag("FRAMEWORK_VOICE_OUTPUT_REAL_TTS") if real_tts_enabled is None else bool(real_tts_enabled)
    provider_configured = bool(os.environ.get("FRAMEWORK_VOICE_OUTPUT_PROVIDER"))
    execution_allowed = _env_flag("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION")

    metadata = {
        "boundary": "voice_output",
        "real_tts_enabled": str(enabled).lower(),
        "provider_configured": str(provider_configured).lower(),
        "provider_execution_allowed": str(execution_allowed).lower(),
        "provider_details_exposed": "false",
    }

    if not enabled:
        return CapabilityStatus(
            name="voice_output",
            status="unavailable",
            supported=True,
            configured=False,
            available=False,
            blocked=False,
            reason_code="real_tts_disabled",
            safe_message="Voice output public boundary is available, but real TTS is disabled.",
            public_metadata=metadata,
        )

    if not provider_configured:
        return CapabilityStatus(
            name="voice_output",
            status="unavailable",
            supported=True,
            configured=False,
            available=False,
            blocked=False,
            reason_code="provider_not_configured",
            safe_message="Voice output provider is not configured.",
            public_metadata=metadata,
        )

    if not execution_allowed:
        return CapabilityStatus(
            name="voice_output",
            status="blocked",
            supported=True,
            configured=True,
            available=False,
            blocked=True,
            reason_code="provider_execution_guarded",
            safe_message="Voice output provider execution is guarded by default.",
            public_metadata=metadata,
        )

    return CapabilityStatus(
        name="voice_output",
        status="configured",
        supported=True,
        configured=True,
        available=False,
        blocked=False,
        reason_code="real_provider_not_probed",
        safe_message="Voice output provider is configured, but availability was not probed by the mock-safe capability snapshot.",
        public_metadata=metadata,
    )


def _missing_capability(name: str, reason_code: str, safe_message: str) -> CapabilityStatus:
    return CapabilityStatus(
        name=name,
        status="unavailable",
        supported=False,
        configured=False,
        available=False,
        blocked=False,
        reason_code=reason_code,
        safe_message=safe_message,
        public_metadata={"boundary": name},
    )


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}
