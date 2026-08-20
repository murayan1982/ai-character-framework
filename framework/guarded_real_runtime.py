"""Explicit-only guarded real-runtime composition for FW-RT6-13b.

Importing this module does not import a provider SDK, inspect environment
variables or private files, construct a provider client, execute a provider,
access a microphone, perform playback, or connect to VTube Studio.  Host-owned
stage factories are reached only after both explicit real-runtime opt-ins pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Mapping

from .public_safety import public_mapping
from .realtime_capabilities import (
    RealtimeMotionCapability,
    RealtimeVoiceInputCapability,
    RealtimeVoiceOutputCapability,
    TextGenerationCapability,
)
from .realtime_session_config import RealtimeSessionConfig
from .realtime_stage import (
    MotionStage,
    RealtimeStageKind,
    TextGenerationStage,
    VoiceInputStage,
    VoiceOutputStage,
)


GuardedStageFactory = Callable[[], object]

_CANONICAL_STAGE_KINDS = (
    RealtimeStageKind.VOICE_INPUT,
    RealtimeStageKind.TEXT_GENERATION,
    RealtimeStageKind.VOICE_OUTPUT,
    RealtimeStageKind.MOTION,
)

_PROTOCOL_BY_STAGE_KIND: Mapping[RealtimeStageKind, type[object]] = {
    RealtimeStageKind.VOICE_INPUT: VoiceInputStage,
    RealtimeStageKind.TEXT_GENERATION: TextGenerationStage,
    RealtimeStageKind.VOICE_OUTPUT: VoiceOutputStage,
    RealtimeStageKind.MOTION: MotionStage,
}

_CAPABILITY_BY_STAGE_KIND: Mapping[RealtimeStageKind, type[object]] = {
    RealtimeStageKind.VOICE_INPUT: RealtimeVoiceInputCapability,
    RealtimeStageKind.TEXT_GENERATION: TextGenerationCapability,
    RealtimeStageKind.VOICE_OUTPUT: RealtimeVoiceOutputCapability,
    RealtimeStageKind.MOTION: RealtimeMotionCapability,
}


def _require_bool(value: object, *, field_name: str) -> bool:
    if type(value) is not bool:
        raise TypeError(f"{field_name} must be a boolean")
    return value


class GuardedRealRuntimeStageStatus(str, Enum):
    """Public-safe reach/preflight outcome for one canonical real stage."""

    BLOCKED = "blocked"
    CONFIGURATION_MISSING = "configuration_missing"
    NOT_REACHED = "not_reached"
    FACTORY_FAILED = "factory_failed"
    PROTOCOL_REJECTED = "protocol_rejected"
    PREFLIGHT_FAILED = "preflight_failed"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    READY = "ready"


class GuardedRealRuntimeCompositionStatus(str, Enum):
    """Aggregate guarded composition outcome."""

    DISABLED = "disabled"
    PROVIDER_EXECUTION_BLOCKED = "provider_execution_blocked"
    CONFIGURATION_INCOMPLETE = "configuration_incomplete"
    PREFLIGHT_FAILED = "preflight_failed"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class GuardedRealRuntimeStageResult:
    """Immutable provider-neutral result for one stage reach attempt."""

    stage_kind: RealtimeStageKind | str
    status: GuardedRealRuntimeStageStatus | str
    factory_reached: bool = False
    preflight_reached: bool = False
    capability_reached: bool = False
    ready: bool = False
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        stage_kind = (
            self.stage_kind
            if isinstance(self.stage_kind, RealtimeStageKind)
            else RealtimeStageKind(str(self.stage_kind))
        )
        status = (
            self.status
            if isinstance(self.status, GuardedRealRuntimeStageStatus)
            else GuardedRealRuntimeStageStatus(str(self.status))
        )
        factory_reached = _require_bool(
            self.factory_reached,
            field_name="factory_reached",
        )
        preflight_reached = _require_bool(
            self.preflight_reached,
            field_name="preflight_reached",
        )
        capability_reached = _require_bool(
            self.capability_reached,
            field_name="capability_reached",
        )
        ready = _require_bool(self.ready, field_name="ready")
        retryable = _require_bool(self.retryable, field_name="retryable")

        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")
        if preflight_reached and not factory_reached:
            raise ValueError("preflight_reached requires factory_reached")
        if capability_reached and not preflight_reached:
            raise ValueError("capability_reached requires preflight_reached")
        if ready and (
            status is not GuardedRealRuntimeStageStatus.READY
            or not capability_reached
        ):
            raise ValueError("ready requires a reached READY capability")
        if status is GuardedRealRuntimeStageStatus.READY and not ready:
            raise ValueError("READY status requires ready=True")

        object.__setattr__(self, "stage_kind", stage_kind)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "factory_reached", factory_reached)
        object.__setattr__(self, "preflight_reached", preflight_reached)
        object.__setattr__(self, "capability_reached", capability_reached)
        object.__setattr__(self, "ready", ready)
        object.__setattr__(self, "safe_message", self.safe_message.strip())
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )


@dataclass(frozen=True, slots=True)
class GuardedRealRuntimeCompositionConfig:
    """Host-owned factories and the two required real-runtime opt-ins.

    Factory callables are excluded from representation and comparison because
    their closures may retain private configuration or provider clients.  The
    Framework never reads that configuration directly.
    """

    real_runtime_enabled: bool = False
    allow_provider_execution: bool = False
    voice_input_factory: GuardedStageFactory | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    text_generation_factory: GuardedStageFactory | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    voice_output_factory: GuardedStageFactory | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    motion_factory: GuardedStageFactory | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "real_runtime_enabled",
            _require_bool(
                self.real_runtime_enabled,
                field_name="real_runtime_enabled",
            ),
        )
        object.__setattr__(
            self,
            "allow_provider_execution",
            _require_bool(
                self.allow_provider_execution,
                field_name="allow_provider_execution",
            ),
        )
        for field_name in (
            "voice_input_factory",
            "text_generation_factory",
            "voice_output_factory",
            "motion_factory",
        ):
            factory = getattr(self, field_name)
            if factory is not None and not callable(factory):
                raise TypeError(f"{field_name} must be callable or None")

    def factory_for(
        self,
        stage_kind: RealtimeStageKind,
    ) -> GuardedStageFactory | None:
        return {
            RealtimeStageKind.VOICE_INPUT: self.voice_input_factory,
            RealtimeStageKind.TEXT_GENERATION: self.text_generation_factory,
            RealtimeStageKind.VOICE_OUTPUT: self.voice_output_factory,
            RealtimeStageKind.MOTION: self.motion_factory,
        }[stage_kind]


@dataclass(frozen=True, slots=True)
class GuardedRealRuntimeCompositionResult:
    """Aggregate public-safe preflight truth and optional session handoff."""

    status: GuardedRealRuntimeCompositionStatus | str
    real_runtime_enabled: bool
    allow_provider_execution: bool
    runtime_ready: bool
    stage_results: tuple[GuardedRealRuntimeStageResult, ...]
    session_config: RealtimeSessionConfig | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    safe_message: str = ""
    retryable: bool = False
    public_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        status = (
            self.status
            if isinstance(self.status, GuardedRealRuntimeCompositionStatus)
            else GuardedRealRuntimeCompositionStatus(str(self.status))
        )
        real_runtime_enabled = _require_bool(
            self.real_runtime_enabled,
            field_name="real_runtime_enabled",
        )
        allow_provider_execution = _require_bool(
            self.allow_provider_execution,
            field_name="allow_provider_execution",
        )
        runtime_ready = _require_bool(self.runtime_ready, field_name="runtime_ready")
        retryable = _require_bool(self.retryable, field_name="retryable")

        if not isinstance(self.stage_results, tuple):
            raise TypeError("stage_results must be a tuple")
        if len(self.stage_results) != len(_CANONICAL_STAGE_KINDS):
            raise ValueError("stage_results must contain all four canonical stages")
        for expected_kind, stage_result in zip(
            _CANONICAL_STAGE_KINDS,
            self.stage_results,
        ):
            if not isinstance(stage_result, GuardedRealRuntimeStageResult):
                raise TypeError(
                    "stage_results must contain GuardedRealRuntimeStageResult values"
                )
            if stage_result.stage_kind is not expected_kind:
                raise ValueError("stage_results must use canonical stage order")
        if not isinstance(self.safe_message, str):
            raise TypeError("safe_message must be a string")
        if self.session_config is not None and not isinstance(
            self.session_config,
            RealtimeSessionConfig,
        ):
            raise TypeError("session_config must be RealtimeSessionConfig or None")
        if runtime_ready:
            if (
                status is not GuardedRealRuntimeCompositionStatus.READY
                or not real_runtime_enabled
                or not allow_provider_execution
                or self.session_config is None
                or not all(result.ready for result in self.stage_results)
            ):
                raise ValueError(
                    "runtime_ready requires both opt-ins, four ready stages, and a session config"
                )
        elif self.session_config is not None:
            raise ValueError("non-ready composition cannot expose a session config")

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "real_runtime_enabled", real_runtime_enabled)
        object.__setattr__(
            self,
            "allow_provider_execution",
            allow_provider_execution,
        )
        object.__setattr__(self, "runtime_ready", runtime_ready)
        object.__setattr__(self, "safe_message", self.safe_message.strip())
        object.__setattr__(self, "retryable", retryable)
        object.__setattr__(
            self,
            "public_metadata",
            public_mapping(self.public_metadata),
        )

    @property
    def ready_stage_kinds(self) -> tuple[str, ...]:
        return tuple(
            result.stage_kind.value for result in self.stage_results if result.ready
        )

    @property
    def failed_stage_kinds(self) -> tuple[str, ...]:
        return tuple(
            result.stage_kind.value
            for result in self.stage_results
            if result.status
            not in {
                GuardedRealRuntimeStageStatus.READY,
                GuardedRealRuntimeStageStatus.BLOCKED,
                GuardedRealRuntimeStageStatus.NOT_REACHED,
            }
        )


def _stage_result(
    stage_kind: RealtimeStageKind,
    status: GuardedRealRuntimeStageStatus,
    *,
    factory_reached: bool = False,
    preflight_reached: bool = False,
    capability_reached: bool = False,
    ready: bool = False,
    safe_message: str,
    retryable: bool = False,
) -> GuardedRealRuntimeStageResult:
    return GuardedRealRuntimeStageResult(
        stage_kind=stage_kind,
        status=status,
        factory_reached=factory_reached,
        preflight_reached=preflight_reached,
        capability_reached=capability_reached,
        ready=ready,
        safe_message=safe_message,
        retryable=retryable,
        public_metadata={
            "boundary": "guarded_real_runtime_stage",
            "raw_exception_exposed": False,
            "private_configuration_exposed": False,
            "provider_payload_exposed": False,
        },
    )


def _blocked_results(*, reason: str) -> tuple[GuardedRealRuntimeStageResult, ...]:
    return tuple(
        _stage_result(
            stage_kind,
            GuardedRealRuntimeStageStatus.BLOCKED,
            safe_message=(
                "Real runtime composition is disabled."
                if reason == "real_runtime_disabled"
                else "Provider execution requires the second explicit opt-in."
            ),
        )
        for stage_kind in _CANONICAL_STAGE_KINDS
    )


def _capability_ready(
    stage_kind: RealtimeStageKind,
    capability: object,
) -> bool:
    expected = _CAPABILITY_BY_STAGE_KIND[stage_kind]
    if not isinstance(capability, expected):
        return False
    try:
        runtime_ready = capability.runtime.usable and capability.runtime.real_runtime
    except Exception:
        return False
    if not runtime_ready:
        return False
    if stage_kind is RealtimeStageKind.VOICE_INPUT:
        return bool(capability.final_transcript_supported)
    if stage_kind is RealtimeStageKind.TEXT_GENERATION:
        return bool(capability.streaming_supported)
    if stage_kind is RealtimeStageKind.MOTION:
        return bool(capability.provider_neutral_intent_supported)
    return True


def _safe_close(stages: list[object]) -> int:
    close_failure_count = 0
    seen: set[int] = set()
    for stage in reversed(stages):
        identity = id(stage)
        if identity in seen:
            continue
        seen.add(identity)
        close_method = getattr(stage, "close", None)
        if not callable(close_method):
            continue
        try:
            close_method()
        except Exception:
            close_failure_count += 1
    return close_failure_count


def compose_guarded_real_runtime(
    config: GuardedRealRuntimeCompositionConfig,
) -> GuardedRealRuntimeCompositionResult:
    """Reach four real stages only after both explicit opt-ins pass.

    Provider exceptions are normalized into fixed provider-neutral outcomes.
    Failed compositions close every constructed stage and expose neither raw
    exceptions nor stage/provider objects.  A ready result transfers stage
    ownership through its hidden ``session_config`` to the host/session owner.
    """

    if not isinstance(config, GuardedRealRuntimeCompositionConfig):
        raise TypeError("config must be GuardedRealRuntimeCompositionConfig")

    if not config.real_runtime_enabled:
        results = _blocked_results(reason="real_runtime_disabled")
        return GuardedRealRuntimeCompositionResult(
            status=GuardedRealRuntimeCompositionStatus.DISABLED,
            real_runtime_enabled=False,
            allow_provider_execution=config.allow_provider_execution,
            runtime_ready=False,
            stage_results=results,
            safe_message="Real runtime composition is disabled.",
            public_metadata={
                "boundary": "guarded_real_runtime_composition",
                "stage_factory_call_count": 0,
                "stage_preflight_call_count": 0,
                "provider_execution_authorized": False,
            },
        )

    if not config.allow_provider_execution:
        results = _blocked_results(reason="provider_execution_not_allowed")
        return GuardedRealRuntimeCompositionResult(
            status=GuardedRealRuntimeCompositionStatus.PROVIDER_EXECUTION_BLOCKED,
            real_runtime_enabled=True,
            allow_provider_execution=False,
            runtime_ready=False,
            stage_results=results,
            safe_message="Provider execution requires the second explicit opt-in.",
            public_metadata={
                "boundary": "guarded_real_runtime_composition",
                "stage_factory_call_count": 0,
                "stage_preflight_call_count": 0,
                "provider_execution_authorized": False,
            },
        )

    missing = tuple(
        stage_kind
        for stage_kind in _CANONICAL_STAGE_KINDS
        if config.factory_for(stage_kind) is None
    )
    if missing:
        results = tuple(
            _stage_result(
                stage_kind,
                (
                    GuardedRealRuntimeStageStatus.CONFIGURATION_MISSING
                    if stage_kind in missing
                    else GuardedRealRuntimeStageStatus.NOT_REACHED
                ),
                safe_message=(
                    "Required real stage configuration is missing."
                    if stage_kind in missing
                    else "Stage was not reached because composition is incomplete."
                ),
            )
            for stage_kind in _CANONICAL_STAGE_KINDS
        )
        return GuardedRealRuntimeCompositionResult(
            status=GuardedRealRuntimeCompositionStatus.CONFIGURATION_INCOMPLETE,
            real_runtime_enabled=True,
            allow_provider_execution=True,
            runtime_ready=False,
            stage_results=results,
            safe_message="Guarded real runtime configuration is incomplete.",
            public_metadata={
                "boundary": "guarded_real_runtime_composition",
                "missing_stage_count": len(missing),
                "stage_factory_call_count": 0,
                "stage_preflight_call_count": 0,
                "provider_execution_authorized": True,
            },
        )

    stage_results: list[GuardedRealRuntimeStageResult] = []
    stages: dict[RealtimeStageKind, object] = {}
    constructed: list[object] = []
    factory_call_count = 0
    preflight_call_count = 0

    for stage_kind in _CANONICAL_STAGE_KINDS:
        factory = config.factory_for(stage_kind)
        if factory is None:
            raise AssertionError("complete composition must retain all factories")
        factory_call_count += 1
        try:
            stage = factory()
        except Exception:
            stage_results.append(
                _stage_result(
                    stage_kind,
                    GuardedRealRuntimeStageStatus.FACTORY_FAILED,
                    factory_reached=True,
                    safe_message="Real stage construction failed safely.",
                    retryable=True,
                )
            )
            continue

        constructed.append(stage)
        protocol = _PROTOCOL_BY_STAGE_KIND[stage_kind]
        try:
            conforms = isinstance(stage, protocol)
        except Exception:
            conforms = False
        if not conforms:
            stage_results.append(
                _stage_result(
                    stage_kind,
                    GuardedRealRuntimeStageStatus.PROTOCOL_REJECTED,
                    factory_reached=True,
                    safe_message="Constructed stage does not satisfy its public protocol.",
                )
            )
            continue
        try:
            raw_stage_kind = stage.stage_kind
            resolved_stage_kind = (
                raw_stage_kind
                if isinstance(raw_stage_kind, RealtimeStageKind)
                else RealtimeStageKind(str(raw_stage_kind))
            )
        except Exception:
            resolved_stage_kind = None
        if resolved_stage_kind is not stage_kind:
            stage_results.append(
                _stage_result(
                    stage_kind,
                    GuardedRealRuntimeStageStatus.PROTOCOL_REJECTED,
                    factory_reached=True,
                    safe_message="Constructed stage reports an invalid stage kind.",
                )
            )
            continue

        preflight_call_count += 1
        try:
            capability = stage.preflight()
        except Exception:
            stage_results.append(
                _stage_result(
                    stage_kind,
                    GuardedRealRuntimeStageStatus.PREFLIGHT_FAILED,
                    factory_reached=True,
                    preflight_reached=True,
                    safe_message="Real stage preflight failed safely.",
                    retryable=True,
                )
            )
            continue

        if not _capability_ready(stage_kind, capability):
            stage_results.append(
                _stage_result(
                    stage_kind,
                    GuardedRealRuntimeStageStatus.CAPABILITY_UNAVAILABLE,
                    factory_reached=True,
                    preflight_reached=True,
                    capability_reached=True,
                    safe_message="Real stage capability is unavailable.",
                    retryable=True,
                )
            )
            continue

        stages[stage_kind] = stage
        stage_results.append(
            _stage_result(
                stage_kind,
                GuardedRealRuntimeStageStatus.READY,
                factory_reached=True,
                preflight_reached=True,
                capability_reached=True,
                ready=True,
                safe_message="Real stage preflight is ready.",
            )
        )

    normalized_results = tuple(stage_results)
    if not all(result.ready for result in normalized_results):
        close_failure_count = _safe_close(constructed)
        return GuardedRealRuntimeCompositionResult(
            status=GuardedRealRuntimeCompositionStatus.PREFLIGHT_FAILED,
            real_runtime_enabled=True,
            allow_provider_execution=True,
            runtime_ready=False,
            stage_results=normalized_results,
            safe_message="Guarded real runtime preflight failed safely.",
            retryable=True,
            public_metadata={
                "boundary": "guarded_real_runtime_composition",
                "stage_factory_call_count": factory_call_count,
                "stage_preflight_call_count": preflight_call_count,
                "ready_stage_count": sum(result.ready for result in normalized_results),
                "failed_stage_count": sum(
                    not result.ready for result in normalized_results
                ),
                "cleanup_failure_count": close_failure_count,
                "provider_execution_authorized": True,
                "raw_exception_exposed": False,
                "private_configuration_exposed": False,
            },
        )

    session_config = RealtimeSessionConfig(
        real_runtime_enabled=True,
        voice_input_stage=stages[RealtimeStageKind.VOICE_INPUT],
        text_generation_stage=stages[RealtimeStageKind.TEXT_GENERATION],
        voice_output_stage=stages[RealtimeStageKind.VOICE_OUTPUT],
        motion_stage=stages[RealtimeStageKind.MOTION],
    )
    return GuardedRealRuntimeCompositionResult(
        status=GuardedRealRuntimeCompositionStatus.READY,
        real_runtime_enabled=True,
        allow_provider_execution=True,
        runtime_ready=True,
        stage_results=normalized_results,
        session_config=session_config,
        safe_message="Guarded real runtime composition is ready.",
        public_metadata={
            "boundary": "guarded_real_runtime_composition",
            "stage_factory_call_count": factory_call_count,
            "stage_preflight_call_count": preflight_call_count,
            "ready_stage_count": len(normalized_results),
            "failed_stage_count": 0,
            "provider_execution_authorized": True,
            "raw_exception_exposed": False,
            "private_configuration_exposed": False,
        },
    )


__all__ = [
    "GuardedStageFactory",
    "GuardedRealRuntimeStageStatus",
    "GuardedRealRuntimeCompositionStatus",
    "GuardedRealRuntimeStageResult",
    "GuardedRealRuntimeCompositionConfig",
    "GuardedRealRuntimeCompositionResult",
    "compose_guarded_real_runtime",
]
