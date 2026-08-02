"""Explicit-only real-motion adapter configuration and capability status.

FW-VTS-0b is provider-safe, filesystem-free, and execution-free. It accepts
only public boolean availability assertions and provider-neutral motion intents.
It does not inspect process environment, read endpoint/token/model values or
paths, import pyvts/WebSocket modules, create a provider client, connect to a
network service, or execute real motion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .motion import MotionAdapterStatus, MotionCapability, MotionIntent


_VTS_ALIASES = frozenset({"vts", "vtube_studio", "live2d"})
_DISABLED_ALIASES = frozenset({"disabled", "none"})
_VTS_HOTKEY_INTENTS = frozenset(
    {
        MotionIntent.EXPRESSION,
        MotionIntent.EMOTION,
        MotionIntent.GESTURE,
        MotionIntent.STOP_MOTION,
        MotionIntent.RESET_EXPRESSION,
    }
)

_BASE_PUBLIC_METADATA = {
    "boundary": "motion_adapter_execution",
    "configuration_source": "explicit_arguments_only",
    "provider_sdk_imported": False,
    "provider_client_created": False,
    "network_executed": False,
    "authentication_material_read": False,
    "authentication_location_read": False,
    "model_location_read": False,
    "real_motion_executed": False,
}


def _normalize_adapter(adapter: str | None) -> str | None:
    if adapter is None:
        return None
    normalized = str(adapter).strip().lower()
    if not normalized:
        return None
    if normalized in _VTS_ALIASES:
        return "vts"
    return normalized


def _normalize_intents(
    values: Iterable[MotionIntent | str] | None,
) -> tuple[MotionIntent, ...]:
    if values is None:
        return ()

    normalized: list[MotionIntent] = []
    seen: set[MotionIntent] = set()
    for value in values:
        intent = (
            value
            if isinstance(value, MotionIntent)
            else MotionIntent(str(value))
        )
        if intent not in seen:
            normalized.append(intent)
            seen.add(intent)
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class MotionAdapterExecutionConfig:
    """Public-safe explicit real-motion configuration assertions.

    This type accepts no endpoint value, token value/path, model value/path,
    provider client, SDK object, WebSocket object, or raw provider payload.
    """

    adapter: str | None = "mock"
    real_adapter_enabled: bool = False
    allow_provider_execution: bool = False
    endpoint_configured: bool = False
    runtime_available: bool = False
    token_available: bool = False
    model_selected: bool = False
    configured_intents: tuple[MotionIntent, ...] = ()

    def __post_init__(self) -> None:
        adapter = _normalize_adapter(self.adapter)
        intents = _normalize_intents(self.configured_intents)

        if adapter == "vts":
            unsupported = tuple(
                intent
                for intent in intents
                if intent not in _VTS_HOTKEY_INTENTS
            )
            if unsupported:
                names = ", ".join(intent.value for intent in unsupported)
                raise ValueError(
                    "VTS configured_intents contains unproven intent(s): "
                    + names
                )

        object.__setattr__(self, "adapter", adapter)
        object.__setattr__(
            self,
            "real_adapter_enabled",
            bool(self.real_adapter_enabled),
        )
        object.__setattr__(
            self,
            "allow_provider_execution",
            bool(self.allow_provider_execution),
        )
        object.__setattr__(
            self,
            "endpoint_configured",
            bool(self.endpoint_configured),
        )
        object.__setattr__(
            self,
            "runtime_available",
            bool(self.runtime_available),
        )
        object.__setattr__(
            self,
            "token_available",
            bool(self.token_available),
        )
        object.__setattr__(
            self,
            "model_selected",
            bool(self.model_selected),
        )
        object.__setattr__(self, "configured_intents", intents)

    @property
    def adapter_configured(self) -> bool:
        return self.adapter is not None

    @property
    def configuration_complete(self) -> bool:
        return (
            self.adapter == "vts"
            and self.real_adapter_enabled
            and self.allow_provider_execution
            and self.endpoint_configured
            and self.runtime_available
            and self.token_available
            and self.model_selected
        )

    def to_public_dict(self) -> dict[str, object]:
        return {
            "adapter": self.adapter,
            "adapter_configured": self.adapter_configured,
            "real_adapter_enabled": self.real_adapter_enabled,
            "provider_execution_allowed": self.allow_provider_execution,
            "endpoint_configured": self.endpoint_configured,
            "runtime_available": self.runtime_available,
            "token_available": self.token_available,
            "model_selected": self.model_selected,
            "configuration_complete": self.configuration_complete,
            "configured_intents": tuple(
                intent.value for intent in self.configured_intents
            ),
            "configuration_source": "explicit_arguments_only",
            "authentication_material_read": False,
            "authentication_location_read": False,
            "model_location_read": False,
        }


def resolve_motion_adapter_execution_config(
    *,
    adapter: str | None = "mock",
    real_adapter_enabled: bool = False,
    allow_provider_execution: bool = False,
    endpoint_configured: bool = False,
    runtime_available: bool = False,
    token_available: bool = False,
    model_selected: bool = False,
    configured_intents: Iterable[MotionIntent | str] | None = None,
) -> MotionAdapterExecutionConfig:
    """Resolve explicit arguments without environment or filesystem fallback."""

    return MotionAdapterExecutionConfig(
        adapter=adapter,
        real_adapter_enabled=real_adapter_enabled,
        allow_provider_execution=allow_provider_execution,
        endpoint_configured=endpoint_configured,
        runtime_available=runtime_available,
        token_available=token_available,
        model_selected=model_selected,
        configured_intents=_normalize_intents(configured_intents),
    )


def _intent_flags(
    configured_intents: tuple[MotionIntent, ...],
) -> dict[str, bool]:
    configured = frozenset(configured_intents)
    return {
        "supports_expression": MotionIntent.EXPRESSION in configured,
        "supports_emotion": MotionIntent.EMOTION in configured,
        "supports_speaking_state": (
            MotionIntent.SPEAKING_STATE in configured
        ),
        "supports_idle_motion": MotionIntent.IDLE_MOTION in configured,
        "supports_gesture": MotionIntent.GESTURE in configured,
        "supports_look_at": MotionIntent.LOOK_AT in configured,
        "supports_stop_motion": MotionIntent.STOP_MOTION in configured,
        "supports_reset_expression": (
            MotionIntent.RESET_EXPRESSION in configured
        ),
    }


def _capability(
    *,
    config: MotionAdapterExecutionConfig,
    status: MotionAdapterStatus,
    reason: str,
    safe_message: str,
    intent_flags: dict[str, bool] | None = None,
) -> MotionCapability:
    metadata = {
        **_BASE_PUBLIC_METADATA,
        **config.to_public_dict(),
        "reason": reason,
    }
    return MotionCapability(
        adapter=config.adapter or "",
        adapter_status=status,
        supports_motion_session=True,
        supports_mock_motion=True,
        supports_real_adapter=False,
        safe_message=safe_message,
        public_metadata=metadata,
        **(intent_flags or {}),
    )


def get_motion_adapter_execution_capability(
    config: MotionAdapterExecutionConfig,
) -> MotionCapability:
    """Return an execution-free provider-neutral capability snapshot."""

    if not isinstance(config, MotionAdapterExecutionConfig):
        raise TypeError(
            "config must be MotionAdapterExecutionConfig"
        )

    adapter = config.adapter

    if adapter is None:
        return _capability(
            config=config,
            status=MotionAdapterStatus.NOT_CONFIGURED,
            reason="adapter_not_configured",
            safe_message="Motion adapter is not configured.",
        )

    if adapter in _DISABLED_ALIASES:
        return _capability(
            config=config,
            status=MotionAdapterStatus.DISABLED,
            reason="adapter_disabled",
            safe_message="Motion adapter is disabled.",
        )

    if adapter == "mock":
        metadata = {
            **_BASE_PUBLIC_METADATA,
            **config.to_public_dict(),
            "reason": "mock_available",
        }
        return MotionCapability(
            adapter="mock",
            adapter_status=MotionAdapterStatus.MOCK_AVAILABLE,
            supports_motion_session=True,
            supports_mock_motion=True,
            supports_real_adapter=False,
            supports_expression=True,
            supports_emotion=True,
            supports_speaking_state=True,
            supports_idle_motion=True,
            supports_gesture=True,
            supports_look_at=True,
            supports_stop_motion=True,
            supports_reset_expression=True,
            safe_message="Mock motion adapter is available.",
            public_metadata=metadata,
        )

    if adapter != "vts":
        return _capability(
            config=config,
            status=MotionAdapterStatus.UNSUPPORTED_ADAPTER,
            reason="unsupported_adapter",
            safe_message="Motion adapter is unsupported.",
        )

    flags = _intent_flags(config.configured_intents)

    if not config.real_adapter_enabled:
        return _capability(
            config=config,
            status=MotionAdapterStatus.DISABLED,
            reason="real_adapter_disabled",
            safe_message="Real motion adapter is disabled.",
            intent_flags=flags,
        )

    if not config.allow_provider_execution:
        return _capability(
            config=config,
            status=MotionAdapterStatus.PROVIDER_EXECUTION_NOT_ALLOWED,
            reason="provider_execution_not_allowed",
            safe_message=(
                "Motion adapter provider execution is not allowed."
            ),
            intent_flags=flags,
        )

    if not config.endpoint_configured:
        return _capability(
            config=config,
            status=MotionAdapterStatus.NOT_CONFIGURED,
            reason="endpoint_not_configured",
            safe_message="Motion adapter endpoint is not configured.",
            intent_flags=flags,
        )

    if not config.runtime_available:
        return _capability(
            config=config,
            status=MotionAdapterStatus.RUNTIME_NOT_INSTALLED,
            reason="runtime_not_installed",
            safe_message="Motion adapter runtime is not available.",
            intent_flags=flags,
        )

    if not config.token_available:
        return _capability(
            config=config,
            status=MotionAdapterStatus.TOKEN_MISSING,
            reason="token_missing",
            safe_message="Motion adapter authentication token is unavailable.",
            intent_flags=flags,
        )

    if not config.model_selected:
        return _capability(
            config=config,
            status=MotionAdapterStatus.MODEL_NOT_SELECTED,
            reason="model_not_selected",
            safe_message="Motion adapter model is not selected.",
            intent_flags=flags,
        )

    return _capability(
        config=config,
        status=MotionAdapterStatus.CONFIGURED,
        reason="configuration_complete_transport_not_bound",
        safe_message=(
            "Motion adapter configuration is complete, but a real transport "
            "is not bound."
        ),
        intent_flags=flags,
    )
