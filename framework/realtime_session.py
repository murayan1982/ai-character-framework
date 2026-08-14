"""Public realtime session skeleton.

This module provides a mock-safe public realtime lifecycle / event boundary. It
intentionally does not execute real STT, LLM, TTS, motion, Live2D, VTube Studio,
websocket, microphone, or provider SDK code.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Condition, Event, RLock, get_ident
import time
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Callable, Iterator, Mapping

from .capabilities import _session_realtime_snapshot
from .identity import EventSequence, GenerationId, SessionId, TurnId
from .lifecycle import (
    LifecycleTransitionError,
    LifecycleTransitionErrorCode,
    RealtimePhase,
    RecoveryAction,
    TurnOutcome,
    validate_phase_transition,
)

from .output_control import (
    BargeInDecision,
    BargeInPolicy,
    BargeInPolicyMode,
    InterruptOutcome,
    InterruptReason,
    InterruptRequest,
    InterruptResult,
    InterruptScope,
    OutputFlushRequest,
    OutputFlushResult,
    TTSQueueState,
)
from .version import REALTIME_API_VERSION

from .realtime_capabilities import RealtimeCapabilitySnapshot
from .realtime_session_config import (
    RealtimeSessionConfig,
    RealtimeSessionConstructionResult,
    RealtimeSessionConstructionStatus,
)
from .realtime_event_hub import EventHubClosedError, RealtimeEventHub
from .realtime_execution import RealtimeExecutionError, RealtimeExecutionErrorCode
from .realtime_execution_bridge import _RealtimeExecutionBridge
from .realtime_terminal_registry import (
    RealtimeTerminalRegistry,
    TerminalCommitDecision,
)
from .realtime_event_payloads import (
    AudioEventPayload,
    DiagnosticEventPayload,
    InterruptEventPayload,
    LifecycleEventPayload,
    MotionEventPayload,
    RealtimeEventPayload,
    ResponseEventPayload,
    SynthesisEventPayload,
    TranscriptEventPayload,
)
from .realtime import (
    RealtimeErrorCode,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeState,
    RealtimeTurn,
    RealtimeTurnResult,
    RealtimeTurnStartResult,
    _normalize_realtime_phase,
    _public_mapping,
    _require_runtime_event_payload,
)
if TYPE_CHECKING:
    from .barge_in_control import BargeInControlPlan
    from .interrupt_coordination import InterruptAggregateResult
    from .motion import MotionErrorCode, MotionRequest, MotionResult, MotionState
    from .motion_control import MotionControlResult
    from .motion_lifecycle import MotionLifecycleHook, MotionLifecycleNotification
    from .realtime_generation_gate import (
        GenerationAdmissionDecision,
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
    )
    from .recovery_control import RecoveryControlPlan, RecoveryResetResult
    from .session_close import (
        SessionCleanupResult,
        SessionCleanupTarget,
        SessionClosePlan,
        SessionCloseResult,
    )
    from .session_diagnostics import SessionDiagnosticsSnapshot
    from .session_compatibility import SessionCompatibilityProfile
    from .realtime_stage import (
        MotionStage,
        TextGenerationStage,
        VoiceInputStage,
        VoiceOutputStage,
    )


RealtimeEventCallback = Callable[[RealtimeEvent], None]
_PHASE_UNCHANGED = object()
_TURN_TERMINAL_EVENT_TYPES = frozenset(
    {
        RealtimeEventType.TURN_COMPLETED,
        RealtimeEventType.TURN_INTERRUPTED,
        RealtimeEventType.TURN_CANCELLED,
        RealtimeEventType.TURN_FAILED,
        RealtimeEventType.TURN_REJECTED,
    }
)
_POST_TERMINAL_COORDINATION_EVENT_TYPES = frozenset(
    {
        RealtimeEventType.AUDIO_INVALIDATED,
        RealtimeEventType.PLAYBACK_STOP_REQUESTED_TO_HOST,
        RealtimeEventType.PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST,
    }
)
_EVENT_GENERATION_AUTO = object()
_SESSION_CLOSE_TIMEOUT_SECONDS = 2.0
_MOTION_LIFECYCLE_SOURCE_SIGNALS = {
    RealtimeEventType.LISTENING_STARTED: ("listening", None),
    RealtimeEventType.RESPONSE_STARTED: ("thinking", None),
    RealtimeEventType.SYNTHESIS_STARTED: ("speaking", None),
    RealtimeEventType.TURN_INTERRUPTED: ("interrupted", TurnOutcome.INTERRUPTED),
    RealtimeEventType.TURN_CANCELLED: ("interrupted", TurnOutcome.CANCELLED),
    RealtimeEventType.TURN_COMPLETED: ("completed", TurnOutcome.COMPLETED),
    RealtimeEventType.TURN_FAILED: ("failed", TurnOutcome.FAILED),
}
_MOTION_LIFECYCLE_TERMINAL_SOURCE_TYPES = frozenset(
    {
        RealtimeEventType.TURN_INTERRUPTED,
        RealtimeEventType.TURN_CANCELLED,
        RealtimeEventType.TURN_COMPLETED,
        RealtimeEventType.TURN_FAILED,
    }
)


def _validated_injected_stages(
    *,
    voice_input_stage: object | None,
    text_generation_stage: object | None,
    voice_output_stage: object | None,
    motion_stage: object | None,
) -> dict[str, object]:
    """Return validated provider-neutral stage bindings without executing them.

    The stable stage package is imported lazily only when at least one binding is
    supplied. Ordinary ``import framework`` and no-stage session construction
    therefore retain the accepted provider/runtime-safe import boundary.
    """

    supplied = (
        voice_input_stage,
        text_generation_stage,
        voice_output_stage,
        motion_stage,
    )
    if not any(stage is not None for stage in supplied):
        return {}

    from .realtime_stage import (
        MotionStage,
        RealtimeStageKind,
        TextGenerationStage,
        VoiceInputStage,
        VoiceOutputStage,
    )

    specifications = (
        ("voice_input_stage", voice_input_stage, VoiceInputStage, RealtimeStageKind.VOICE_INPUT),
        (
            "text_generation_stage",
            text_generation_stage,
            TextGenerationStage,
            RealtimeStageKind.TEXT_GENERATION,
        ),
        (
            "voice_output_stage",
            voice_output_stage,
            VoiceOutputStage,
            RealtimeStageKind.VOICE_OUTPUT,
        ),
        ("motion_stage", motion_stage, MotionStage, RealtimeStageKind.MOTION),
    )

    bindings: dict[str, object] = {}
    for argument_name, stage, protocol, expected_kind in specifications:
        if stage is None:
            continue
        try:
            conforms = isinstance(stage, protocol)
        except Exception:
            raise TypeError(
                f"{argument_name} could not be validated against its public stage protocol"
            ) from None
        if not conforms:
            raise TypeError(
                f"{argument_name} must satisfy {protocol.__name__}"
            )
        try:
            raw_kind = stage.stage_kind
        except Exception:
            raise TypeError(
                f"{argument_name}.stage_kind could not be read safely"
            ) from None
        try:
            stage_kind = (
                raw_kind
                if isinstance(raw_kind, RealtimeStageKind)
                else RealtimeStageKind(str(raw_kind))
            )
        except (TypeError, ValueError):
            raise ValueError(
                f"{argument_name}.stage_kind must be {expected_kind.value!r}"
            ) from None
        if stage_kind is not expected_kind:
            raise ValueError(
                f"{argument_name}.stage_kind must be {expected_kind.value!r}"
            )
        bindings[expected_kind.value] = stage

    return bindings



def _normalize_realtime_session_config(
    *,
    config: RealtimeSessionConfig | None,
    real_runtime_enabled: bool | None,
    voice_input_stage: object | None,
    text_generation_stage: object | None,
    voice_output_stage: object | None,
    motion_stage: object | None,
) -> RealtimeSessionConfig:
    """Normalize legacy keyword inputs into one immutable public config."""

    if config is not None:
        if not isinstance(config, RealtimeSessionConfig):
            raise TypeError("config must be a RealtimeSessionConfig or None")
        if real_runtime_enabled is not None or any(
            stage is not None
            for stage in (
                voice_input_stage,
                text_generation_stage,
                voice_output_stage,
                motion_stage,
            )
        ):
            raise TypeError(
                "config cannot be combined with real_runtime_enabled or stage arguments"
            )
        return config

    return RealtimeSessionConfig(
        real_runtime_enabled=bool(real_runtime_enabled),
        voice_input_stage=voice_input_stage,
        text_generation_stage=text_generation_stage,
        voice_output_stage=voice_output_stage,
        motion_stage=motion_stage,
    )


def _preflight_injected_stages(
    bindings: Mapping[str, object],
) -> tuple[dict[str, object], tuple[str, ...]]:
    """Call each injected stage preflight exactly once without raw-error exposure."""

    if not bindings:
        return {}, ()

    from .realtime_capabilities import (
        RealtimeMotionCapability,
        RealtimeVoiceInputCapability,
        RealtimeVoiceOutputCapability,
        TextGenerationCapability,
    )

    expected_types: Mapping[str, type[object]] = {
        "voice_input": RealtimeVoiceInputCapability,
        "text_generation": TextGenerationCapability,
        "voice_output": RealtimeVoiceOutputCapability,
        "motion": RealtimeMotionCapability,
    }
    capabilities: dict[str, object] = {}
    failed: list[str] = []
    for stage_kind, stage in bindings.items():
        try:
            capability = stage.preflight()
        except Exception:
            failed.append(stage_kind)
            continue
        expected = expected_types[stage_kind]
        if not isinstance(capability, expected):
            failed.append(stage_kind)
            continue
        try:
            runtime_usable = capability.runtime.usable
            real_runtime = capability.runtime.real_runtime
        except Exception:
            failed.append(stage_kind)
            continue
        if not runtime_usable or not real_runtime:
            failed.append(stage_kind)
            continue
        capabilities[stage_kind] = capability
    return capabilities, tuple(failed)


def _construction_result_for_config(
    *,
    session_id: SessionId,
    config: RealtimeSessionConfig,
    injected_stage_kinds: tuple[str, ...],
    failed_stage_kinds: tuple[str, ...],
) -> RealtimeSessionConstructionResult:
    """Build one internal typed construction result for later public adoption."""

    preflight_metadata = {
        "boundary": "realtime_session_construction",
        "provider_execution_performed": False,
        "preflight_stage_count": len(injected_stage_kinds),
        "preflight_failure_count": len(failed_stage_kinds),
    }
    if not config.real_runtime_enabled:
        return RealtimeSessionConstructionResult(
            status=RealtimeSessionConstructionStatus.MOCK_READY,
            session_id=session_id,
            configuration_complete=True,
            runtime_executable=True,
            real_runtime_requested=False,
            real_runtime_enabled=False,
            safe_message="Deterministic mock realtime runtime is ready.",
            public_metadata=preflight_metadata,
        )

    missing_stage_kinds = (
        () if "text_generation" in injected_stage_kinds else ("text_generation",)
    )
    if failed_stage_kinds:
        return RealtimeSessionConstructionResult(
            status=RealtimeSessionConstructionStatus.PREFLIGHT_FAILED,
            session_id=session_id,
            configuration_complete=not missing_stage_kinds,
            runtime_executable=False,
            real_runtime_requested=True,
            real_runtime_enabled=False,
            missing_stage_kinds=missing_stage_kinds,
            failed_stage_kinds=failed_stage_kinds,
            safe_message="Realtime stage preflight failed safely.",
            retryable=True,
            public_metadata=preflight_metadata,
        )
    if missing_stage_kinds:
        return RealtimeSessionConstructionResult(
            status=RealtimeSessionConstructionStatus.CONFIGURATION_INCOMPLETE,
            session_id=session_id,
            configuration_complete=False,
            runtime_executable=False,
            real_runtime_requested=True,
            real_runtime_enabled=False,
            missing_stage_kinds=missing_stage_kinds,
            safe_message="Realtime text-generation stage configuration is missing.",
            public_metadata=preflight_metadata,
        )
    return RealtimeSessionConstructionResult(
        status=RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY,
        session_id=session_id,
        configuration_complete=True,
        runtime_executable=False,
        real_runtime_requested=True,
        real_runtime_enabled=False,
        safe_message="Real runtime configuration is ready; orchestration is not available.",
        public_metadata=preflight_metadata,
    )


class _LateNonTerminalRejected(RuntimeError):
    """Internal control-flow signal for a terminal turn's late event attempt."""

    def __init__(self, turn_id: TurnId | str) -> None:
        self.turn_id = turn_id
        super().__init__("late non-terminal realtime event rejected")


@dataclass(frozen=True)
class RealtimeSessionInfo:
    """App-safe metadata for a public realtime session."""

    api_version: str = REALTIME_API_VERSION
    session_type: str = "realtime"
    session_id: SessionId | str = field(default_factory=SessionId.new)
    state: RealtimeState | str = RealtimeState.IDLE
    supports_events: bool = True
    supports_run_turn: bool = True
    supports_voice_input: bool = True
    supports_text_chat: bool = True
    supports_voice_output: bool = True
    supports_motion: bool = False
    supports_interrupt: bool = True
    supports_output_flush: bool = True
    supports_barge_in_policy: bool = True
    supports_close: bool = True
    real_runtime_enabled: bool = False
    hard_cancel_supported: bool = False
    tts_queue_flush_supported: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)
    phase: RealtimePhase | str | None = None

    def __post_init__(self) -> None:
        state = self.state if isinstance(self.state, RealtimeState) else RealtimeState(str(self.state))
        phase = _normalize_realtime_phase(self.phase, legacy_state=state)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "public_metadata", _public_mapping(self.public_metadata))


@dataclass(frozen=True, slots=True)
class _ActiveTurnContext:
    """Internal immutable identity for one explicitly admitted turn."""

    turn: RealtimeTurn
    generation_id: GenerationId

    @property
    def turn_id(self) -> TurnId | str:
        return self.turn.turn_id


@dataclass(slots=True)
class _ActiveMotionWork:
    """One session-owned lifecycle motion while its stage call is in flight."""

    stage: object
    context: object
    request: object
    completion_event: Event = field(default_factory=Event)
    cancel_call_finished: Event = field(default_factory=Event)
    stop_call_finished: Event = field(default_factory=Event)
    cancel_call_started: bool = False
    cancel_requested: bool = False
    cancel_accepted: bool = False
    cancel_failed: bool = False
    stop_call_started: bool = False
    stop_motion_requested: bool = False
    stop_motion_supported: bool = False
    stop_motion_applied: bool = False
    stop_failed: bool = False
    future_delivery_suppressed: bool = False


@dataclass(frozen=True, slots=True)
class _MotionControlAttempt:
    """Internal split-phase result resolved after the session lock is available."""

    work: _ActiveMotionWork | None = None
    result: MotionControlResult | None = None


@dataclass(slots=True)
class _ActiveInterruptStageWork:
    """One Framework-owned text or voice stage call that may be interrupted."""

    subsystem: str
    stage: object
    context: object
    completion_event: Event = field(default_factory=Event)
    cancel_call_finished: Event = field(default_factory=Event)
    cancel_call_started: bool = False
    cancel_requested: bool = False
    cancel_accepted: bool = False
    cancel_failed: bool = False
    future_delivery_suppressed: bool = False
    typed_cancel_result: object | None = None


@dataclass(frozen=True, slots=True)
class _InterruptStageAttempt:
    """One split-phase cooperative stage-cancel attempt."""

    subsystem: str
    work: _ActiveInterruptStageWork | None = None
    result: object | None = None


@dataclass(frozen=True, slots=True)
class _InterruptCoordinationAttempt:
    """All targeted subsystem attempts captured outside the operation lock."""

    request: InterruptRequest
    turn_id: TurnId | str | None
    ordered_attempts: tuple[_InterruptStageAttempt, ...]
    motion_attempt: _MotionControlAttempt | None = None
    deadline: float = 0.0


@dataclass(frozen=True, slots=True)
class _DeferredTurnTerminal:
    """One normal terminal publication paused behind an interrupt owner."""

    result: RealtimeTurnResult
    event_type: RealtimeEventType
    new_state: RealtimeState
    reason: str
    public_error_code: RealtimeErrorCode
    safe_message: str
    retryable: bool
    public_metadata: Mapping[str, Any] | None


@dataclass(slots=True)
class _InterruptRequestWork:
    """Private sole-owner state for one resolved session/turn interrupt."""

    key: tuple[SessionId | str, TurnId | str]
    turn_id: TurnId | str
    generation_id: GenerationId | None
    owner_thread_id: int
    completion_event: Event = field(default_factory=Event)
    result: InterruptResult | None = None
    reserved_terminal: RealtimeTurnResult | None = None
    deferred_terminal: _DeferredTurnTerminal | None = None
    reservation_active: bool = True
    flush_result: OutputFlushResult | None = None
    close_after_completion: bool = False


class _InterruptTerminalReserved(RuntimeError):
    """Move a normal terminal wait outside the long session operation lock."""

    def __init__(self, work: _InterruptRequestWork) -> None:
        self.work = work
        super().__init__("interrupt terminal reservation won admission")


class RealtimeSession:
    """Mock-safe public realtime session skeleton.

    The session exposes unified lifecycle, events, turn results, output-control
    methods, and cleanup semantics before real runtime orchestration is
    implemented.
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        public_metadata: Mapping[str, Any] | None = None,
        real_runtime_enabled: bool | None = None,
        voice_input_stage: VoiceInputStage | None = None,
        text_generation_stage: TextGenerationStage | None = None,
        voice_output_stage: VoiceOutputStage | None = None,
        motion_stage: MotionStage | None = None,
        config: RealtimeSessionConfig | None = None,
    ) -> None:
        normalized_config = _normalize_realtime_session_config(
            config=config,
            real_runtime_enabled=real_runtime_enabled,
            voice_input_stage=voice_input_stage,
            text_generation_stage=text_generation_stage,
            voice_output_stage=voice_output_stage,
            motion_stage=motion_stage,
        )
        self._config = normalized_config
        self._project_root = Path(project_root).resolve() if project_root is not None else None
        self._session_id = SessionId.new()
        self._injected_stages = _validated_injected_stages(
            voice_input_stage=normalized_config.voice_input_stage,
            text_generation_stage=normalized_config.text_generation_stage,
            voice_output_stage=normalized_config.voice_output_stage,
            motion_stage=normalized_config.motion_stage,
        )
        self._state = RealtimeState.IDLE
        self._phase: RealtimePhase | None = RealtimePhase.IDLE
        self._closed = False
        self._close_requested = False
        self._last_close_result: SessionCloseResult | None = None
        self._pending_close_result: tuple[
            SessionClosePlan,
            dict[SessionCleanupTarget, SessionCleanupResult],
            bool,
        ] | None = None
        self._close_finalized = Event()
        self._duplicate_close_requested = False
        self._operation_lock = RLock()
        self._callback_window_condition = Condition(self._operation_lock)
        self._callback_window_owner_thread_id: int | None = None
        self._callback_window_depth = 0
        self._operation_depth = 0
        self._execution_bridge = _RealtimeExecutionBridge(
            thread_name=f"framework-realtime-{self._session_id}",
        )
        self._event_hub = RealtimeEventHub[RealtimeEvent]()
        self._terminal_registry = RealtimeTerminalRegistry[RealtimeTurnResult]()
        from .realtime_generation_gate import RealtimeGenerationGate

        self._generation_gate = RealtimeGenerationGate()
        self._injected_stages_closed = False
        self._stage_close_count = 0
        self._stage_close_error_count = 0
        self._real_runtime_requested = normalized_config.real_runtime_enabled
        (
            self._stage_capabilities,
            self._stage_preflight_failed_kinds,
        ) = _preflight_injected_stages(self._injected_stages)
        self._capability_snapshot = _session_realtime_snapshot(
            session_id=self._session_id,
            snapshot_generation=1,
            project_root=self._project_root,
            real_runtime_requested=self._real_runtime_requested,
            stage_capabilities=self._stage_capabilities,
            failed_stage_kinds=self._stage_preflight_failed_kinds,
        )
        self._real_runtime_enabled = self._capability_snapshot.real_runtime_enabled
        self._construction_result = _construction_result_for_config(
            session_id=self._session_id,
            config=normalized_config,
            injected_stage_kinds=tuple(self._injected_stages),
            failed_stage_kinds=self._stage_preflight_failed_kinds,
        )
        self._public_metadata = _public_mapping(public_metadata)
        self._barge_in_policy = BargeInPolicy.disabled()
        self._motion_lifecycle_hook: MotionLifecycleHook | None = None
        self._motion_control_lock = RLock()
        self._active_motion_work: _ActiveMotionWork | None = None
        self._interrupt_stage_lock = RLock()
        self._active_interrupt_stage_work: dict[
            str,
            _ActiveInterruptStageWork,
        ] = {}
        self._interrupt_request_lock = RLock()
        self._interrupt_requests: dict[
            tuple[SessionId | str, TurnId | str],
            _InterruptRequestWork,
        ] = {}
        self._normal_terminal_reservations: set[
            tuple[SessionId | str, TurnId | str]
        ] = set()
        self._active_interrupt_request: _InterruptRequestWork | None = None
        self._close_admission_requested = False
        self._turn_admission_lock = RLock()
        self._active_turn_context: _ActiveTurnContext | None = None
        self._active_turn_id: TurnId | str | None = None
        self._active_generation_id: GenerationId | None = None
        self._host_playback_stop_requests: dict[
            tuple[TurnId | str | None, GenerationId | None],
            RealtimeEvent,
        ] = {}
        self._host_playback_stop_acknowledgements: dict[
            tuple[TurnId | str | None, GenerationId | None],
            RealtimeEvent,
        ] = {}
        self._info = RealtimeSessionInfo(
            session_id=self._session_id,
            state=self._state,
            phase=self._phase,
            supports_voice_input=self._capability_snapshot.supports_voice_input,
            supports_text_chat=self._capability_snapshot.supports_text_chat,
            supports_voice_output=self._capability_snapshot.supports_voice_output,
            supports_motion=self._capability_snapshot.supports_motion,
            real_runtime_enabled=self._real_runtime_enabled,
            hard_cancel_supported=self._capability_snapshot.hard_cancel_supported,
            tts_queue_flush_supported=(
                self._capability_snapshot.tts_queue_flush_supported
            ),
            public_metadata={
                "boundary": "realtime",
                "capability_snapshot_scope": self._capability_snapshot.snapshot_scope.value,
                "capability_snapshot_generation": self._capability_snapshot.snapshot_generation,
                "real_runtime_requested": self._real_runtime_requested,
                "injected_stage_count": len(self._injected_stages),
                "injected_stage_kinds": tuple(self._injected_stages),
                "stage_preflight_failure_count": len(
                    self._stage_preflight_failed_kinds
                ),
                **dict(public_metadata or {}),
            },
        )

    @property
    def info(self) -> RealtimeSessionInfo:
        return RealtimeSessionInfo(
            session_id=self._session_id,
            state=self._state,
            phase=self._phase,
            supports_voice_input=self._capability_snapshot.supports_voice_input,
            supports_text_chat=self._capability_snapshot.supports_text_chat,
            supports_voice_output=self._capability_snapshot.supports_voice_output,
            supports_motion=self._capability_snapshot.supports_motion,
            real_runtime_enabled=self._real_runtime_enabled,
            hard_cancel_supported=self._capability_snapshot.hard_cancel_supported,
            tts_queue_flush_supported=(
                self._capability_snapshot.tts_queue_flush_supported
            ),
            public_metadata={
                "boundary": "realtime",
                "barge_in_policy": self._barge_in_policy.mode.value,
                "capability_snapshot_scope": self._capability_snapshot.snapshot_scope.value,
                "capability_snapshot_generation": self._capability_snapshot.snapshot_generation,
                "real_runtime_requested": self._real_runtime_requested,
                "injected_stage_count": len(self._injected_stages),
                "injected_stage_kinds": tuple(self._injected_stages),
                "stage_preflight_failure_count": len(
                    self._stage_preflight_failed_kinds
                ),
                **dict(self._public_metadata),
            },
        )

    @property
    def capabilities(self) -> RealtimeCapabilitySnapshot:
        """Return this session's immutable truthful capability snapshot."""

        return self._capability_snapshot

    @property
    def construction_result(self) -> RealtimeSessionConstructionResult:
        """Return the immutable public-safe result of session construction."""

        return self._construction_result

    @property
    def injected_stage_kinds(self) -> tuple[str, ...]:
        """Return canonical provider-neutral kinds for injected stages."""

        return tuple(self._injected_stages)

    @property
    def stage_diagnostics(self) -> Mapping[str, int]:
        """Return count-only lifecycle diagnostics for injected stages."""

        return MappingProxyType(
            {
                "injected_stage_count": len(self._injected_stages),
                "stage_close_count": self._stage_close_count,
                "stage_close_error_count": self._stage_close_error_count,
            }
        )

    @property
    def state(self) -> RealtimeState:
        return self._state

    @property
    def phase(self) -> RealtimePhase | None:
        return self._phase

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def last_close_result(self) -> SessionCloseResult | None:
        """Return the latest immutable close observation, if close was requested."""

        return self._last_close_result

    @property
    def compatibility_profile(self) -> SessionCompatibilityProfile:
        """Return the immutable profile for the explicitly selected runtime mode."""

        from .session_compatibility import (
            StandaloneSessionKind,
            build_session_compatibility_profile,
        )

        return build_session_compatibility_profile(
            StandaloneSessionKind.REALTIME,
            unified_runtime_requested=self._real_runtime_requested,
        )

    @property
    def diagnostics_snapshot(self) -> SessionDiagnosticsSnapshot:
        """Return one coherent immutable provider-neutral operator snapshot."""

        from .session_diagnostics import build_session_diagnostics_snapshot

        with self._diagnostics_snapshot_read_section():
            generation = self._generation_gate.diagnostics
            active_turn_id = self._generation_gate.current_turn_id
            active_generation_id = self._generation_gate.current_generation_id
            terminal_records = self._terminal_registry.records
            terminal = self._terminal_registry.diagnostics
            event = self._event_hub.diagnostics
            queue_state = self.get_tts_queue_state()
            last_terminal_result = next(
                (
                    record.result
                    for record in reversed(terminal_records)
                    if record.result is not None
                ),
                None,
            )
            return build_session_diagnostics_snapshot(
                session_id=self._session_id,
                state=self._state,
                phase=self._phase,
                is_closed=self._closed,
                active_turn_id=active_turn_id,
                active_generation_id=active_generation_id,
                queue_depth=queue_state.queued_count,
                active_generation_count=generation["active_generation_count"],
                last_terminal_result=last_terminal_result,
                stale_completion_count=generation["stale_completion_count"],
                duplicate_terminal_count=terminal.duplicate_terminal_count,
                overflow_count=event.history_overflow_count,
            )

    @property
    def barge_in_policy(self) -> BargeInPolicy:
        return self._barge_in_policy

    @property
    def event_history(self) -> tuple[RealtimeEvent, ...]:
        """Return the immutable bounded canonical event-history snapshot."""

        return self._event_hub.event_history

    @property
    def event_diagnostics(self) -> Mapping[str, int]:
        """Return immutable public-safe event-hub counters."""

        diagnostics = self._event_hub.diagnostics
        return MappingProxyType(
            {
                "emitted_event_count": diagnostics.emitted_event_count,
                "callback_error_count": diagnostics.callback_error_count,
                "slow_callback_count": diagnostics.slow_callback_count,
                "history_overflow_count": diagnostics.history_overflow_count,
                "rejected_after_close_count": diagnostics.rejected_after_close_count,
                "subscriber_count": self._event_hub.subscriber_count,
                "history_limit": self._event_hub.history_limit,
            }
        )

    @property
    def terminal_results(self) -> tuple[RealtimeTurnResult, ...]:
        """Return first-terminal results in atomic commit order."""

        return tuple(
            record.result
            for record in self._terminal_registry.records
            if record.result is not None
        )

    @property
    def terminal_diagnostics(self) -> Mapping[str, int]:
        """Return immutable count-only terminal registry diagnostics."""

        diagnostics = self._terminal_registry.diagnostics
        return MappingProxyType(
            {
                "terminal_commit_count": diagnostics.terminal_commit_count,
                "duplicate_terminal_count": diagnostics.duplicate_terminal_count,
                "terminal_regression_count": diagnostics.terminal_regression_count,
                "late_non_terminal_count": diagnostics.late_non_terminal_count,
                "registry_size": diagnostics.registry_size,
            }
        )

    @property
    def generation_diagnostics(self) -> Mapping[str, int]:
        """Return immutable count-only generation freshness diagnostics."""

        return self._generation_gate.diagnostics

    def _bind_active_turn_context(
        self,
        turn: RealtimeTurn,
        generation_id: GenerationId,
    ) -> _ActiveTurnContext:
        """Bind one explicitly admitted turn without replacing another turn."""

        context = _ActiveTurnContext(turn=turn, generation_id=generation_id)
        self._active_turn_context = context
        self._active_turn_id = context.turn_id
        self._active_generation_id = context.generation_id
        return context

    def _clear_active_turn_context(self) -> None:
        """Clear explicit and compatibility active-turn identity mirrors."""

        self._active_turn_context = None
        self._active_turn_id = None
        self._active_generation_id = None

    def _active_turn_identity(
        self,
    ) -> tuple[TurnId | str | None, GenerationId | None]:
        """Return current active identity without allocating or retiring work."""

        context = self._active_turn_context
        if context is not None:
            return context.turn_id, context.generation_id
        return (
            self._generation_gate.current_turn_id or self._active_turn_id,
            self._generation_gate.current_generation_id or self._active_generation_id,
        )

    def _start_turn_generation(
        self,
        turn_id: TurnId | str,
    ) -> GenerationId:
        """Start and retain one gate-owned generation for an admitted turn."""

        generation_id = self._generation_gate.start_generation(turn_id)
        current_turn_id = self._generation_gate.current_turn_id
        if current_turn_id is None:
            raise AssertionError("started generation must retain its turn")
        self._active_turn_id = current_turn_id
        self._active_generation_id = generation_id
        return generation_id

    def _advance_generation(
        self,
        reason: GenerationAdvanceReason | str,
        *,
        turn_id: TurnId | str | None = None,
    ) -> GenerationId | None:
        """Retire the current generation only when the optional turn matches."""

        current_turn_id = self._generation_gate.current_turn_id
        if current_turn_id is None:
            return None
        if turn_id is not None and turn_id != current_turn_id:
            return None
        return self._generation_gate.advance(reason)

    def _emit_stale_completion_diagnostic(
        self,
        decision: GenerationAdmissionDecision[Any],
    ) -> RealtimeEvent:
        """Emit one state-neutral canonical diagnostic for a stale completion."""

        if decision.accepted or decision.stale_reason is None:
            raise ValueError("stale completion diagnostic requires a rejection")

        envelope = decision.envelope
        state = self._state
        phase = self._phase
        metadata: dict[str, Any] = {"boundary": "realtime"}
        if decision.retired_by is not None:
            metadata["retired_by"] = decision.retired_by.value

        def event_factory(sequence: EventSequence) -> RealtimeEvent:
            return RealtimeEvent(
                type=RealtimeEventType.STALE_RESULT_DROPPED,
                state=state,
                previous_state=state,
                turn_id=envelope.turn_id,
                session_id=self._session_id,
                boundary="realtime",
                safe_message="Stale realtime stage completion was dropped.",
                public_metadata=metadata,
                sequence=sequence,
                generation_id=envelope.generation_id,
                phase=phase,
                payload=DiagnosticEventPayload(
                    code="stale_stage_completion",
                    drop_reason=decision.stale_reason.value,
                ),
                timestamp=time.time(),
                monotonic_timestamp=time.monotonic(),
            )

        def overflow_event_factory(
            sequence: EventSequence,
            dropped_sequence: EventSequence | None,
            overflow_count: int,
        ) -> RealtimeEvent:
            return self._build_event_overflow(
                sequence=sequence,
                dropped_sequence=dropped_sequence,
                overflow_count=overflow_count,
                state=state,
                turn_id=envelope.turn_id,
                generation_id=envelope.generation_id,
                phase=phase,
            )

        with self._callback_delivery_window():
            return self._event_hub.emit(
                event_factory,
                legacy_projector=lambda emitted: emitted.to_v5(),
                overflow_event_factory=overflow_event_factory,
            )

    def _apply_stage_completion(
        self,
        envelope: RealtimeStageCompletionEnvelope[Any],
        *,
        deliver: Callable[[Any], None],
    ) -> GenerationAdmissionDecision[Any]:
        """Atomically admit and apply one current stage completion."""

        if not callable(deliver):
            raise TypeError("deliver must be callable")

        with self._serialized_operation():
            decision = self._generation_gate.apply_completion(
                envelope,
                deliver=deliver,
            )
            if not decision.accepted and not self._closed and not self._close_requested:
                self._emit_stale_completion_diagnostic(decision)
            return decision

    def _session_closed_error(self) -> LifecycleTransitionError:
        return LifecycleTransitionError(
            LifecycleTransitionErrorCode.SESSION_CLOSED,
            from_phase=self._phase,
            to_phase=None,
        )

    def _duplicate_terminal_result(
        self,
        turn_id: TurnId | str,
    ) -> RealtimeTurnResult | None:
        """Return and account for an already committed terminal result."""

        existing = self._terminal_registry.get(turn_id)
        if existing is None:
            return None
        decision = self._terminal_registry.commit(
            turn_id,
            existing.outcome,
            recovery_action=existing.recovery_action,
            reason=existing.reason,
            result=existing.result,
        )
        if decision.accepted:
            raise AssertionError("existing terminal record was recommitted")
        result = decision.record.result
        if result is None:
            raise AssertionError("session terminal record must retain its result")
        return result

    def _commit_terminal_result(
        self,
        result: RealtimeTurnResult,
        *,
        event_type: RealtimeEventType,
        new_state: RealtimeState,
        reason: str,
        public_error_code: RealtimeErrorCode = RealtimeErrorCode.NONE,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
        _interrupt_owner: _InterruptRequestWork | None = None,
    ) -> RealtimeTurnResult:
        """Commit one terminal result and let only the first owner emit."""

        key = (self._session_id, result.turn_id)
        with self._interrupt_request_lock:
            interrupt_work = self._interrupt_requests.get(key)
            if (
                interrupt_work is not None
                and interrupt_work is not _interrupt_owner
                and interrupt_work.reservation_active
                and not interrupt_work.completion_event.is_set()
            ):
                if interrupt_work.deferred_terminal is None:
                    interrupt_work.deferred_terminal = _DeferredTurnTerminal(
                        result=result,
                        event_type=event_type,
                        new_state=new_state,
                        reason=reason,
                        public_error_code=public_error_code,
                        safe_message=safe_message,
                        retryable=retryable,
                        public_metadata=public_metadata,
                    )
                raise _InterruptTerminalReserved(interrupt_work)

            decision: TerminalCommitDecision[RealtimeTurnResult] = (
                self._terminal_registry.commit(
                    result.turn_id,
                    result.outcome,
                    recovery_action=result.recovery_action,
                    reason=reason,
                    result=result,
                )
            )
        if decision.accepted:
            self._advance_generation(
                "turn_terminal",
                turn_id=result.turn_id,
            )
            self._transition(
                event_type,
                new_state,
                turn_id=result.turn_id,
                payload=LifecycleEventPayload(
                    outcome=decision.record.outcome,
                    recovery_action=decision.record.recovery_action,
                    reason=decision.record.reason,
                ),
                public_error_code=public_error_code,
                safe_message=safe_message,
                retryable=retryable,
                public_metadata=public_metadata,
            )
        committed = decision.record.result
        if committed is None:
            raise AssertionError("session terminal record must retain its result")
        return committed

    @contextmanager
    def _serialized_operation(self) -> Iterator[None]:
        """Serialize one operation and shut the runtime down only after unlock."""

        should_shutdown_bridge = False
        try:
            with self._operation_lock:
                current_thread_id = get_ident()
                while (
                    self._callback_window_owner_thread_id is not None
                    and self._callback_window_owner_thread_id != current_thread_id
                ):
                    self._callback_window_condition.wait()
                self._operation_depth += 1
                try:
                    yield
                finally:
                    self._operation_depth -= 1
                    if (
                        self._operation_depth == 0
                        and self._close_requested
                        and not self._closed
                    ):
                        self._close_now()
                        should_shutdown_bridge = True
        finally:
            if should_shutdown_bridge:
                self._finalize_close_result()

    @contextmanager
    def _callback_delivery_window(self) -> Iterator[None]:
        """Temporarily release the session operation lock for callbacks/hooks.

        ``_operation_depth`` deliberately remains reserved.  Reentrant close
        therefore keeps its accepted deferred-close semantics, while callbacks
        and motion hooks never execute under the actual session lock.  The
        callback runs on the existing caller/runtime thread; no dispatcher
        thread, task, or second event registry is introduced.
        """

        lock = self._operation_lock
        is_owned = getattr(lock, "_is_owned", None)
        if not callable(is_owned) or not is_owned():
            yield
            return

        release_save = getattr(lock, "_release_save", None)
        acquire_restore = getattr(lock, "_acquire_restore", None)
        if not callable(release_save) or not callable(acquire_restore):
            raise RuntimeError("realtime callback lock release is unavailable")

        current_thread_id = get_ident()
        if self._callback_window_owner_thread_id is None:
            self._callback_window_owner_thread_id = current_thread_id
        elif self._callback_window_owner_thread_id != current_thread_id:
            raise RuntimeError("realtime callback window ownership conflict")
        self._callback_window_depth += 1
        restore_state = release_save()
        try:
            yield
        finally:
            acquire_restore(restore_state)
            self._callback_window_depth -= 1
            if self._callback_window_depth == 0:
                self._callback_window_owner_thread_id = None
                self._callback_window_condition.notify_all()

    @contextmanager
    def _diagnostics_snapshot_read_section(self) -> Iterator[None]:
        """Acquire existing session locks without introducing lock-order deadlock."""

        while True:
            with self._operation_lock:
                acquired = self._turn_admission_lock.acquire(blocking=False)
                if acquired:
                    try:
                        yield
                    finally:
                        self._turn_admission_lock.release()
                    return
            time.sleep(0)

    def on_event(self, callback: RealtimeEventCallback) -> str:
        """Register a canonical callback and return its opaque removal token."""

        with self._operation_lock:
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return str(self._event_hub.subscribe(callback))

    def on_legacy_event(self, callback: RealtimeEventCallback) -> str:
        """Register a mapped v5 callback and return its opaque removal token."""

        with self._operation_lock:
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return str(self._event_hub.subscribe(callback, legacy=True))

    def off_event(self, token: str) -> bool:
        """Remove a canonical or legacy callback token idempotently."""

        with self._operation_lock:
            return self._event_hub.unsubscribe(token)

    def backpressure_capability(self, boundary: object):
        """Return truthful response-delta or subscriber delivery limits.

        Boundary values come from the explicit ``framework.backpressure``
        namespace. Audio-input and voice-output owners expose their own
        capability at their respective runtime boundaries.
        """

        with self._operation_lock:
            return self._event_hub.backpressure_capability(boundary)

    def backpressure_snapshot(self, boundary: object):
        """Return current count-only delivery state for an owned boundary."""

        with self._operation_lock:
            return self._event_hub.backpressure_snapshot(boundary)

    def pause_backpressure(self, boundary: object):
        """Pause new delivery admission without cancelling accepted work."""

        with self._operation_lock:
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return self._event_hub.pause_backpressure(boundary)

    def resume_backpressure(self, boundary: object):
        """Resume new delivery admission without changing accepted work."""

        with self._operation_lock:
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return self._event_hub.resume_backpressure(boundary)

    def _generation_for_event(
        self,
        turn_id: TurnId | str | None,
    ) -> GenerationId | None:
        if (
            turn_id is None
            or self._active_turn_id is None
            or self._active_generation_id is None
            or turn_id != self._active_turn_id
        ):
            return None
        return self._active_generation_id

    def _host_playback_context(
        self,
        turn_id: TurnId | str | None,
    ) -> tuple[TurnId | str | None, GenerationId | None]:
        resolved_turn_id = turn_id or self._active_turn_id
        if resolved_turn_id is None:
            return None, None
        if (
            self._active_turn_id == resolved_turn_id
            and self._active_generation_id is not None
        ):
            return resolved_turn_id, self._active_generation_id
        terminal = self._terminal_registry.get(resolved_turn_id)
        if terminal is not None and terminal.result is not None:
            return resolved_turn_id, terminal.result.generation_id
        return resolved_turn_id, None

    def _build_event_overflow(
        self,
        *,
        sequence: EventSequence,
        dropped_sequence: EventSequence | None,
        overflow_count: int,
        state: RealtimeState,
        turn_id: TurnId | str | None,
        generation_id: GenerationId | None,
        phase: RealtimePhase | None,
    ) -> RealtimeEvent:
        """Build one typed diagnostic without creating a lifecycle transition."""

        return RealtimeEvent(
            type=RealtimeEventType.EVENT_OVERFLOW,
            state=state,
            previous_state=state,
            turn_id=turn_id,
            session_id=self._session_id,
            boundary="realtime",
            safe_message="Realtime event history overflowed.",
            public_metadata={
                "boundary": "realtime",
                "history_limit": self._event_hub.history_limit,
            },
            sequence=sequence,
            generation_id=generation_id,
            phase=phase,
            payload=DiagnosticEventPayload(
                code="event_history_overflow",
                drop_reason="bounded_history_capacity",
                dropped_sequence=dropped_sequence,
                overflow_count=overflow_count,
            ),
            timestamp=time.time(),
            monotonic_timestamp=time.monotonic(),
        )

    def _set_phase(
        self,
        next_phase: RealtimePhase | str | None,
    ) -> RealtimePhase | None:
        if next_phase is None:
            self._phase = None
            return None
        resolved_next = (
            next_phase
            if isinstance(next_phase, RealtimePhase)
            else RealtimePhase(str(next_phase))
        )
        if self._closed or self._phase is None:
            raise LifecycleTransitionError(
                LifecycleTransitionErrorCode.SESSION_CLOSED,
                from_phase=self._phase,
                to_phase=resolved_next,
            )
        self._phase = validate_phase_transition(self._phase, resolved_next)
        return self._phase

    def _transition(
        self,
        event_type: RealtimeEventType,
        new_state: RealtimeState,
        *,
        turn_id: TurnId | str | None = None,
        new_phase: RealtimePhase | str | None | object = _PHASE_UNCHANGED,
        payload: RealtimeEventPayload | None = None,
        public_error_code: RealtimeErrorCode = RealtimeErrorCode.NONE,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, Any] | None = None,
        _allow_closed_event: bool = False,
        _event_generation_id: GenerationId | None | object = _EVENT_GENERATION_AUTO,
    ) -> RealtimeEvent:
        if self._closed and not _allow_closed_event:
            raise self._session_closed_error()
        if (
            turn_id is not None
            and event_type is not RealtimeEventType.SESSION_CLOSED
            and event_type not in _TURN_TERMINAL_EVENT_TYPES
            and event_type not in _POST_TERMINAL_COORDINATION_EVENT_TYPES
            and not self._terminal_registry.admit_non_terminal(turn_id)
        ):
            raise _LateNonTerminalRejected(turn_id)
        if new_phase is not _PHASE_UNCHANGED:
            self._set_phase(new_phase)
        resolved_payload = _require_runtime_event_payload(event_type, payload)
        previous_state = self._state
        self._state = new_state
        generation_id = (
            self._generation_for_event(turn_id)
            if _event_generation_id is _EVENT_GENERATION_AUTO
            else _event_generation_id
        )
        if generation_id is not None and not isinstance(generation_id, GenerationId):
            raise TypeError("_event_generation_id must be GenerationId, None, or auto")
        phase = self._phase
        metadata = {
            "boundary": "realtime",
            **dict(public_metadata or {}),
        }

        def event_factory(sequence: EventSequence) -> RealtimeEvent:
            return RealtimeEvent(
                type=event_type,
                state=new_state,
                previous_state=previous_state,
                turn_id=turn_id,
                session_id=self._session_id,
                boundary="realtime",
                public_error_code=public_error_code,
                safe_message=safe_message,
                retryable=retryable,
                public_metadata=metadata,
                sequence=sequence,
                generation_id=generation_id,
                phase=phase,
                payload=resolved_payload,
                timestamp=time.time(),
                monotonic_timestamp=time.monotonic(),
            )

        def overflow_event_factory(
            sequence: EventSequence,
            dropped_sequence: EventSequence | None,
            overflow_count: int,
        ) -> RealtimeEvent:
            return self._build_event_overflow(
                sequence=sequence,
                dropped_sequence=dropped_sequence,
                overflow_count=overflow_count,
                state=new_state,
                turn_id=turn_id,
                generation_id=generation_id,
                phase=phase,
            )

        with self._callback_delivery_window():
            emitted = self._event_hub.emit(
                event_factory,
                legacy_projector=lambda emitted: emitted.to_v5(),
                overflow_event_factory=overflow_event_factory,
            )
            self._handle_motion_lifecycle_event(emitted)
        return emitted

    def emit_created(self) -> RealtimeEvent:
        """Emit a public session-created event."""

        with self._serialized_operation():
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            return self._emit_created_serialized()

    def _emit_created_serialized(self) -> RealtimeEvent:
        return self._transition(
            RealtimeEventType.SESSION_STARTED,
            RealtimeState.IDLE,
            new_phase=RealtimePhase.IDLE,
            payload=LifecycleEventPayload(reason="session_started"),
            public_metadata={"reason": "session_started"},
        )

    def _reject_unexecutable_real_runtime_turn(
        self,
        turn: RealtimeTurn,
    ) -> RealtimeTurnResult:
        """Reject a real-runtime request before any mock or stage execution."""

        construction = self._construction_result
        status = construction.status
        if status is RealtimeSessionConstructionStatus.CONFIGURATION_INCOMPLETE:
            public_error_code = RealtimeErrorCode.CONFIGURATION_MISSING
            safe_message = "Realtime runtime configuration is incomplete."
            reason = "real_runtime_configuration_missing"
            retryable = False
        elif status is RealtimeSessionConstructionStatus.PREFLIGHT_FAILED:
            public_error_code = RealtimeErrorCode.UNAVAILABLE
            safe_message = "Realtime runtime is unavailable because stage preflight failed."
            reason = "real_runtime_preflight_failed"
            retryable = construction.retryable
        elif status is RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY:
            public_error_code = RealtimeErrorCode.UNAVAILABLE
            safe_message = "Real realtime runtime orchestration is not available."
            reason = "real_runtime_orchestration_not_available"
            retryable = False
        else:
            public_error_code = RealtimeErrorCode.UNAVAILABLE
            safe_message = "Requested realtime runtime is not executable."
            reason = "real_runtime_not_executable"
            retryable = False

        metadata = {
            "boundary": "realtime",
            "reason": reason,
            "construction_status": status.value,
            "real_runtime_requested": True,
            "real_runtime_enabled": construction.real_runtime_enabled,
            "mock_runtime": False,
            "provider_execution_performed": False,
        }
        result = RealtimeTurnResult(
            turn_id=turn.turn_id,
            outcome=TurnOutcome.REJECTED,
            input_text=turn.input_text,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            recovery_action=RecoveryAction.REUSE_SESSION,
            public_metadata=metadata,
            session_id=self._session_id,
            generation_id=None,
        )
        committed_result = self._commit_terminal_result(
            result,
            event_type=RealtimeEventType.TURN_REJECTED,
            new_state=RealtimeState.FAILED,
            reason=reason,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata=metadata,
        )
        self._clear_active_turn_context()
        self._phase = RealtimePhase.IDLE
        self._state = RealtimeState.IDLE
        return committed_result

    def _normalize_turn_start_request(
        self,
        turn: RealtimeTurn | None,
        *,
        input_text: str,
        public_metadata: Mapping[str, Any] | None,
    ) -> RealtimeTurn:
        """Bind one public start request to this session without executing it."""

        if turn is None:
            return RealtimeTurn(
                input_text=input_text,
                session_id=self._session_id,
                public_metadata=public_metadata or {},
            )
        if turn.session_id is None:
            return RealtimeTurn(
                turn_id=turn.turn_id,
                input_text=turn.input_text,
                state=turn.state,
                session_id=self._session_id,
                public_metadata=turn.public_metadata,
                phase=turn.phase,
            )
        return turn

    def _commit_state_neutral_start_rejection(
        self,
        turn: RealtimeTurn,
        *,
        public_error_code: RealtimeErrorCode,
        safe_message: str,
        reason: str,
        retryable: bool = False,
    ) -> RealtimeTurnResult:
        """Commit one rejected start without mutating the active session lifecycle."""

        metadata = {
            "boundary": "realtime_turn_start",
            "reason": reason,
            "active_turn_preserved": True,
            "generation_allocated": False,
            "automatic_previous_turn_replacement": False,
        }
        result = RealtimeTurnResult(
            turn_id=turn.turn_id,
            outcome=TurnOutcome.REJECTED,
            input_text=turn.input_text,
            public_error_code=public_error_code,
            safe_message=safe_message,
            retryable=retryable,
            recovery_action=RecoveryAction.REUSE_SESSION,
            public_metadata=metadata,
            session_id=self._session_id,
            generation_id=None,
        )
        decision = self._terminal_registry.commit(
            result.turn_id,
            result.outcome,
            recovery_action=result.recovery_action,
            reason=reason,
            result=result,
        )
        committed = decision.record.result
        if committed is None:
            raise AssertionError("start rejection terminal record must retain its result")
        if not decision.accepted:
            return committed

        state = self._state
        phase = self._phase
        payload = LifecycleEventPayload(
            outcome=TurnOutcome.REJECTED,
            recovery_action=RecoveryAction.REUSE_SESSION,
            reason=reason,
        )

        def event_factory(sequence: EventSequence) -> RealtimeEvent:
            return RealtimeEvent(
                type=RealtimeEventType.TURN_REJECTED,
                state=state,
                previous_state=state,
                turn_id=turn.turn_id,
                session_id=self._session_id,
                boundary="realtime",
                public_error_code=public_error_code,
                safe_message=safe_message,
                retryable=retryable,
                public_metadata=metadata,
                sequence=sequence,
                generation_id=None,
                phase=phase,
                payload=payload,
                timestamp=time.time(),
                monotonic_timestamp=time.monotonic(),
            )

        def overflow_event_factory(
            sequence: EventSequence,
            dropped_sequence: EventSequence | None,
            overflow_count: int,
        ) -> RealtimeEvent:
            return self._build_event_overflow(
                sequence=sequence,
                dropped_sequence=dropped_sequence,
                overflow_count=overflow_count,
                state=state,
                turn_id=turn.turn_id,
                generation_id=None,
                phase=phase,
            )

        with self._callback_delivery_window():
            self._event_hub.emit(
                event_factory,
                legacy_projector=lambda emitted: emitted.to_v5(),
                overflow_event_factory=overflow_event_factory,
            )
        return committed

    def _rejected_turn_start_result(
        self,
        turn: RealtimeTurn,
        *,
        public_error_code: RealtimeErrorCode,
        safe_message: str,
        reason: str,
        retryable: bool = False,
    ) -> RealtimeTurnStartResult:
        terminal = self._commit_state_neutral_start_rejection(
            turn,
            public_error_code=public_error_code,
            safe_message=safe_message,
            reason=reason,
            retryable=retryable,
        )
        phase = self._phase or RealtimePhase.IDLE
        return RealtimeTurnStartResult(
            accepted=False,
            session_id=self._session_id,
            turn_id=turn.turn_id,
            generation_id=None,
            phase=phase,
            terminal_result=terminal,
            public_metadata={
                "boundary": "realtime_turn_start",
                "reason": reason,
            },
        )

    def _closed_turn_start_result(
        self,
        turn: RealtimeTurn,
    ) -> RealtimeTurnStartResult:
        """Return a typed closed-session admission result without emitting events."""

        terminal = RealtimeTurnResult(
            turn_id=turn.turn_id,
            outcome=TurnOutcome.REJECTED,
            input_text=turn.input_text,
            public_error_code=RealtimeErrorCode.SESSION_CLOSED,
            safe_message="Realtime session is closed.",
            retryable=False,
            recovery_action=RecoveryAction.REUSE_SESSION,
            public_metadata={
                "boundary": "realtime_turn_start",
                "reason": "session_closed",
                "terminal_committed": False,
            },
            session_id=self._session_id,
            generation_id=None,
        )
        return RealtimeTurnStartResult(
            accepted=False,
            session_id=self._session_id,
            turn_id=turn.turn_id,
            generation_id=None,
            phase=RealtimePhase.IDLE,
            terminal_result=terminal,
            public_metadata={
                "boundary": "realtime_turn_start",
                "reason": "session_closed",
            },
        )

    def start_turn(
        self,
        turn: RealtimeTurn | None = None,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeTurnStartResult:
        """Atomically admit one explicit turn without executing its stages."""

        turn = self._normalize_turn_start_request(
            turn,
            input_text=input_text,
            public_metadata=public_metadata,
        )

        with self._turn_admission_lock:
            if self._closed or self._close_requested:
                return self._closed_turn_start_result(turn)

            with self._interrupt_request_lock:
                interrupt_work = self._active_interrupt_request
                interrupt_active = (
                    interrupt_work is not None
                    and not interrupt_work.completion_event.is_set()
                )
            if (
                interrupt_active
                and interrupt_work is not None
                and turn.turn_id != interrupt_work.turn_id
            ):
                return self._rejected_turn_start_result(
                    turn,
                    public_error_code=RealtimeErrorCode.REJECTED,
                    safe_message=(
                        "A new realtime turn cannot start while an interrupt "
                        "is in progress."
                    ),
                    reason="interrupt_in_progress",
                    retryable=True,
                )

            if turn.session_id != self._session_id:
                return self._rejected_turn_start_result(
                    turn,
                    public_error_code=RealtimeErrorCode.INVALID_REQUEST,
                    safe_message="Realtime turn belongs to a different session.",
                    reason="turn_session_mismatch",
                )

            existing_terminal = self._terminal_registry.get(turn.turn_id)
            if existing_terminal is not None:
                existing_result = existing_terminal.result
                if (
                    existing_result is not None
                    and existing_result.outcome is TurnOutcome.REJECTED
                ):
                    return RealtimeTurnStartResult(
                        accepted=False,
                        session_id=self._session_id,
                        turn_id=turn.turn_id,
                        generation_id=None,
                        phase=self._phase or RealtimePhase.IDLE,
                        terminal_result=existing_result,
                        public_metadata={
                            "boundary": "realtime_turn_start",
                            "reason": existing_terminal.reason,
                            "duplicate_terminal": True,
                        },
                    )
                raise ValueError("turn_id already owns a non-rejected terminal result")

            active_turn_id, active_generation_id = self._active_turn_identity()
            if active_turn_id is not None:
                if turn.turn_id == active_turn_id and active_generation_id is not None:
                    return RealtimeTurnStartResult(
                        accepted=True,
                        session_id=self._session_id,
                        turn_id=turn.turn_id,
                        generation_id=active_generation_id,
                        phase=self._phase or RealtimePhase.LISTENING,
                        public_metadata={
                            "boundary": "realtime_turn_start",
                            "idempotent": True,
                        },
                    )
                return self._rejected_turn_start_result(
                    turn,
                    public_error_code=RealtimeErrorCode.REJECTED,
                    safe_message="Another realtime turn is already active.",
                    reason="active_turn_exists",
                )

            if self._real_runtime_requested:
                terminal = self._reject_unexecutable_real_runtime_turn(turn)
                return RealtimeTurnStartResult(
                    accepted=False,
                    session_id=self._session_id,
                    turn_id=turn.turn_id,
                    generation_id=None,
                    phase=self._phase or RealtimePhase.IDLE,
                    terminal_result=terminal,
                    public_metadata={
                        "boundary": "realtime_turn_start",
                        "reason": terminal.public_metadata.get(
                            "reason",
                            "real_runtime_not_executable",
                        ),
                    },
                )

            generation_id = self._generation_gate.start_generation(turn.turn_id)
            context = self._bind_active_turn_context(turn, generation_id)
            try:
                self._transition(
                    RealtimeEventType.TURN_STARTED,
                    RealtimeState.LISTENING,
                    turn_id=context.turn_id,
                    new_phase=RealtimePhase.LISTENING,
                    payload=LifecycleEventPayload(reason="turn_admitted"),
                    public_metadata={
                        "boundary": "realtime_turn_start",
                        "explicit_start": True,
                    },
                )
            except Exception:
                self._advance_generation("reset", turn_id=context.turn_id)
                self._clear_active_turn_context()
                raise

            return RealtimeTurnStartResult(
                accepted=True,
                session_id=self._session_id,
                turn_id=context.turn_id,
                generation_id=context.generation_id,
                phase=self._phase or RealtimePhase.LISTENING,
                public_metadata={
                    "boundary": "realtime_turn_start",
                    "explicit_start": True,
                    "automatic_previous_turn_replacement": False,
                },
            )

    def _prepare_turn_execution(
        self,
        turn: RealtimeTurn | None = None,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> tuple[RealtimeTurn, GenerationId | None, RealtimeTurnResult | None]:
        """Synchronously reserve one turn before runtime-loop execution."""

        normalized_turn = self._normalize_turn_start_request(
            turn,
            input_text=input_text,
            public_metadata=public_metadata,
        )

        if self._closed or self._close_requested:
            return (
                normalized_turn,
                None,
                RealtimeTurnResult.closed(
                    turn_id=normalized_turn.turn_id,
                    session_id=self._session_id,
                ),
            )

        if normalized_turn.session_id == self._session_id:
            existing_terminal = self._duplicate_terminal_result(
                normalized_turn.turn_id
            )
            if existing_terminal is not None:
                return normalized_turn, None, existing_terminal

        start_result = self.start_turn(normalized_turn)
        if not start_result.accepted:
            terminal = start_result.terminal_result
            if terminal is None:
                raise AssertionError(
                    "rejected turn admission must retain a terminal result"
                )
            return normalized_turn, None, terminal

        generation_id = start_result.generation_id
        if generation_id is None:
            raise AssertionError(
                "accepted turn admission must retain a generation identity"
            )

        return normalized_turn, generation_id, None

    async def _run_admitted_turn_async(
        self,
        turn: RealtimeTurn,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
        admitted_generation_id: GenerationId,
    ) -> RealtimeTurnResult:
        """Execute one admitted turn on the session-owned runtime loop."""

        terminal_key = (self._session_id, turn.turn_id)
        with self._interrupt_request_lock:
            existing_interrupt = self._interrupt_requests.get(terminal_key)
            normal_terminal_reserved = (
                existing_interrupt is None
                or existing_interrupt.completion_event.is_set()
            )
            if normal_terminal_reserved:
                self._normal_terminal_reservations.add(terminal_key)

        reserved_work: _InterruptRequestWork | None = None
        try:
            try:
                with self._serialized_operation():
                    existing_terminal = self._duplicate_terminal_result(turn.turn_id)
                    if existing_terminal is not None:
                        return existing_terminal

                    active_turn_id, active_generation_id = self._active_turn_identity()
                    if (
                        active_turn_id != turn.turn_id
                        or active_generation_id != admitted_generation_id
                    ):
                        existing = self._terminal_registry.get(turn.turn_id)
                        if existing is not None and existing.result is not None:
                            return existing.result
                        raise RuntimeError(
                            "accepted realtime turn lost its active admission context"
                        )

                    return self._run_turn_serialized(
                        turn,
                        input_text=input_text,
                        public_metadata=public_metadata,
                        admitted_generation_id=admitted_generation_id,
                    )
            except _InterruptTerminalReserved as reservation:
                reserved_work = reservation.work

            await asyncio.to_thread(reserved_work.completion_event.wait)
            terminal = self._terminal_registry.get(turn.turn_id)
            if terminal is None or terminal.result is None:
                raise AssertionError(
                    "resolved terminal reservation must retain a turn result"
                )
            return terminal.result
        finally:
            if normal_terminal_reserved:
                with self._interrupt_request_lock:
                    self._normal_terminal_reservations.discard(terminal_key)

    def _raise_if_blocking_turn_execution_forbidden(self) -> None:
        """Reject blocking turn execution from event-loop/runtime threads."""

        if self._execution_bridge.is_runtime_thread():
            raise RealtimeExecutionError(
                RealtimeExecutionErrorCode.BLOCKING_CALL_FROM_RUNTIME_THREAD
            )

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        raise RealtimeExecutionError(
            RealtimeExecutionErrorCode.BLOCKING_CALL_IN_ACTIVE_EVENT_LOOP
        )

    async def run_turn_async(
        self,
        turn: RealtimeTurn | None = None,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeTurnResult:
        """Admit one turn and await execution on the persistent runtime loop."""

        normalized_turn, generation_id, terminal = self._prepare_turn_execution(
            turn,
            input_text=input_text,
            public_metadata=public_metadata,
        )
        if terminal is not None:
            return terminal
        if generation_id is None:
            raise AssertionError(
                "accepted async turn execution must retain a generation identity"
            )

        future = self._execution_bridge.submit(
            self._run_admitted_turn_async(
                normalized_turn,
                input_text=input_text,
                public_metadata=public_metadata,
                admitted_generation_id=generation_id,
            )
        )
        return await asyncio.shield(asyncio.wrap_future(future))

    def run_turn_blocking(
        self,
        turn: RealtimeTurn | None = None,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeTurnResult:
        """Blocking compatibility wrapper for one realtime turn."""

        self._raise_if_blocking_turn_execution_forbidden()

        normalized_turn, generation_id, terminal = self._prepare_turn_execution(
            turn,
            input_text=input_text,
            public_metadata=public_metadata,
        )
        if terminal is not None:
            return terminal
        if generation_id is None:
            raise AssertionError(
                "accepted blocking turn execution must retain a generation identity"
            )

        return self._execution_bridge.run(
            self._run_admitted_turn_async(
                normalized_turn,
                input_text=input_text,
                public_metadata=public_metadata,
                admitted_generation_id=generation_id,
            )
        )

    def run_turn(
        self,
        turn: RealtimeTurn | None = None,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
    ) -> RealtimeTurnResult:
        """Legacy blocking compatibility alias for ``run_turn_blocking``."""

        return self.run_turn_blocking(
            turn,
            input_text=input_text,
            public_metadata=public_metadata,
        )

    def _run_turn_serialized(
        self,
        turn: RealtimeTurn,
        *,
        input_text: str = "",
        public_metadata: Mapping[str, Any] | None = None,
        admitted_generation_id: GenerationId,
    ) -> RealtimeTurnResult:
        """Execute one already-admitted deterministic mock realtime turn."""

        transcript_text = turn.input_text or input_text
        committed_result: RealtimeTurnResult

        try:
            self._transition(
                RealtimeEventType.LISTENING_STARTED,
                RealtimeState.LISTENING,
                turn_id=turn.turn_id,
                new_phase=RealtimePhase.LISTENING,
                payload=LifecycleEventPayload(reason="listening_started"),
            )
            self._transition(
                RealtimeEventType.LISTENING_COMPLETED,
                RealtimeState.TRANSCRIBING,
                turn_id=turn.turn_id,
                new_phase=RealtimePhase.TRANSCRIBING,
                payload=LifecycleEventPayload(reason="listening_completed"),
                public_metadata={"mock_stage": "voice_input"},
            )
            self._transition(
                RealtimeEventType.TRANSCRIPT_FINAL,
                RealtimeState.TRANSCRIBING,
                turn_id=turn.turn_id,
                payload=TranscriptEventPayload(
                    text=transcript_text,
                    is_final=True,
                ),
                public_metadata={"mock_stage": "transcript"},
            )
            self._transition(
                RealtimeEventType.RESPONSE_STARTED,
                RealtimeState.THINKING,
                turn_id=turn.turn_id,
                new_phase=RealtimePhase.THINKING,
                payload=ResponseEventPayload(text="", is_final=False),
            )
            self._transition(
                RealtimeEventType.RESPONSE_COMPLETED,
                RealtimeState.THINKING,
                turn_id=turn.turn_id,
                payload=ResponseEventPayload(text="", is_final=True),
                public_metadata={"mock_stage": "text_chat"},
            )
            self._transition(
                RealtimeEventType.SYNTHESIS_STARTED,
                RealtimeState.SPEAKING,
                turn_id=turn.turn_id,
                new_phase=RealtimePhase.SPEAKING,
                payload=SynthesisEventPayload(request_state="started"),
            )
            self._transition(
                RealtimeEventType.SYNTHESIS_COMPLETED,
                RealtimeState.COMPLETED,
                turn_id=turn.turn_id,
                payload=SynthesisEventPayload(request_state="completed"),
                public_metadata={"mock_stage": "voice_output"},
            )
            result = RealtimeTurnResult.completed(
                turn_id=turn.turn_id,
                input_text=turn.input_text or input_text,
                output_text="",
                public_metadata={
                    "boundary": "realtime",
                    "mock_runtime": True,
                    **dict(public_metadata or {}),
                },
                session_id=self._session_id,
                generation_id=admitted_generation_id,
            )
            committed_result = self._commit_terminal_result(
                result,
                event_type=RealtimeEventType.TURN_COMPLETED,
                new_state=RealtimeState.COMPLETED,
                reason="mock_turn_completed",
            )
        except _LateNonTerminalRejected as rejection:
            existing = self._terminal_registry.get(rejection.turn_id)
            if existing is None or existing.result is None:
                raise AssertionError(
                    "late non-terminal rejection must retain a terminal result"
                )
            committed_result = existing.result

        with self._turn_admission_lock:
            context = self._active_turn_context
            if (
                context is not None
                and context.turn_id == turn.turn_id
                and context.generation_id == admitted_generation_id
            ):
                self._clear_active_turn_context()

        if not self._closed and not self._close_requested:
            if self._phase is not RealtimePhase.IDLE:
                self._set_phase(RealtimePhase.IDLE)
            self._state = RealtimeState.IDLE

        return committed_result

    @staticmethod
    def _interrupt_target_names(request: InterruptRequest) -> tuple[str, ...]:
        """Expand one accepted public scope into the five stable subsystems."""

        text = "text_generation"
        tts = "tts_generation"
        queue = "tts_queue"
        artifact = "audio_artifact"
        motion = "motion"
        by_scope = {
            InterruptScope.CURRENT_TURN: (text, tts, queue, artifact, motion),
            InterruptScope.LLM_STREAM: (text,),
            InterruptScope.TTS_QUEUE: (queue,),
            InterruptScope.VOICE_OUTPUT: (tts, queue, artifact),
            InterruptScope.MOTION: (motion,),
            InterruptScope.ALL: (text, tts, queue, artifact, motion),
        }
        selected = set(by_scope[request.scope])
        if request.cancel_llm_stream:
            selected.add(text)
        if request.cancel_tts_queue:
            selected.update((tts, queue, artifact))
        elif request.flush_output:
            selected.update((queue, artifact))
        if request.stop_motion:
            selected.add(motion)
        return tuple(
            name
            for name in (text, tts, queue, artifact, motion)
            if name in selected
        )

    def _coordination_subsystem_result(
        self,
        *,
        subsystem: str,
        outcome: object,
        turn_id: TurnId | str | None,
        generation_id: GenerationId | None = None,
        target_reached: bool = False,
        cooperative_cancel_requested: bool = False,
        cooperative_cancel_accepted: bool = False,
        cooperative_cancel_completed: bool = False,
        provider_hard_cancel_supported: bool = False,
        provider_hard_cancel_applied: bool = False,
        future_delivery_suppressed: bool = False,
        affected_count: int = 0,
        safe_message: str = "",
        retryable: bool = False,
        public_metadata: Mapping[str, object] | None = None,
    ) -> object:
        """Build one typed result without widening the root import graph."""

        from .interrupt_coordination import InterruptSubsystemResult

        return InterruptSubsystemResult(
            subsystem=subsystem,
            outcome=outcome,
            session_id=self._session_id,
            turn_id=turn_id,
            generation_id=generation_id,
            target_reached=target_reached,
            cooperative_cancel_requested=cooperative_cancel_requested,
            cooperative_cancel_accepted=cooperative_cancel_accepted,
            cooperative_cancel_completed=cooperative_cancel_completed,
            provider_hard_cancel_supported=provider_hard_cancel_supported,
            provider_hard_cancel_applied=provider_hard_cancel_applied,
            future_delivery_suppressed=future_delivery_suppressed,
            affected_count=affected_count,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata={
                "boundary": "interrupt_coordination",
                **dict(public_metadata or {}),
            },
        )

    def _begin_active_interrupt_stage_work(
        self,
        *,
        subsystem: str,
        stage: object,
        context: object,
    ) -> _ActiveInterruptStageWork | None:
        """Install one session-owned text or voice execution owner."""

        work = _ActiveInterruptStageWork(
            subsystem=subsystem,
            stage=stage,
            context=context,
        )
        with self._interrupt_stage_lock:
            if self._closed or self._close_requested:
                return None
            if subsystem in self._active_interrupt_stage_work:
                return None
            self._active_interrupt_stage_work[subsystem] = work
            return work

    def _complete_active_interrupt_stage_work(
        self,
        work: _ActiveInterruptStageWork,
    ) -> bool:
        """Release one owner and return its one-way delivery barrier."""

        with self._interrupt_stage_lock:
            suppressed = work.future_delivery_suppressed
            if self._active_interrupt_stage_work.get(work.subsystem) is work:
                del self._active_interrupt_stage_work[work.subsystem]
            work.completion_event.set()
            return suppressed

    def _isolated_stage_failure_envelope(
        self,
        *,
        stage_kind: str,
        context: object,
    ) -> object:
        """Return one provider-neutral typed result after a stage exception."""

        from .callback_isolation import criticality_for_stage, stage_failure_policy
        from .realtime_stage import (
            RealtimeStageContext,
            RealtimeStageKind,
            RealtimeStageResultEnvelope,
        )

        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        resolved_kind = RealtimeStageKind(stage_kind)
        policy = stage_failure_policy(criticality_for_stage(resolved_kind))
        metadata = {
            "boundary": "realtime_stage",
            "reason": "stage_exception",
            "stage_criticality": policy.criticality.value,
            "failure_action": policy.failure_action.value,
            "current_operation_fails": policy.current_operation_fails,
            "session_remains_open": policy.session_remains_open,
            "runtime_remains_available": policy.runtime_remains_available,
            "existing_terminal_replacement_allowed": (
                policy.existing_terminal_replacement_allowed
            ),
            "raw_exception_retained": False,
        }
        if resolved_kind is RealtimeStageKind.TEXT_GENERATION:
            from .text_chat_result import TextChatResult

            result: object = TextChatResult.failed(
                public_error_code="provider_request_failed",
                safe_message="Realtime text-generation stage failed safely.",
                retryable=True,
                public_metadata={
                    "boundary": "realtime_stage",
                    "stage_criticality": policy.criticality.value,
                    "failure_action": policy.failure_action.value,
                },
            )
        elif resolved_kind is RealtimeStageKind.VOICE_OUTPUT:
            from .audio import VoiceOutputResult

            result = VoiceOutputResult(
                request_state="failed",
                audio_ready=False,
                message="Realtime voice-output stage failed safely.",
                public_metadata={
                    "boundary": "realtime_stage",
                    "stage_criticality": policy.criticality.value,
                    "failure_action": policy.failure_action.value,
                },
            )
        else:
            raise ValueError("isolated stage failure requires text or voice output")

        return RealtimeStageResultEnvelope(
            stage_kind=resolved_kind,
            context=context,
            result=result,
            public_metadata=metadata,
        )

    def _execute_interruptible_stage(
        self,
        *,
        stage_kind: str,
        context: object,
        request: object,
    ) -> object | None:
        """Execute one injected text/TTS stage behind the common cancel gate.

        This is an internal orchestration boundary.  A caller must validate the
        returned public stage envelope before delivery.  ``None`` means the
        owner was unavailable or accepted cancellation suppressed the late
        envelope; it never means provider success.
        """

        from .realtime_stage import RealtimeStageContext

        subsystem_by_kind = {
            "text_generation": "text_generation",
            "voice_output": "tts_generation",
        }
        if stage_kind not in subsystem_by_kind:
            raise ValueError(
                "stage_kind must be text_generation or voice_output"
            )
        if not isinstance(context, RealtimeStageContext):
            raise TypeError("context must be a RealtimeStageContext")
        if context.session_id != self._session_id:
            raise ValueError("stage context belongs to another session")
        active_turn_id, active_generation_id = self._active_turn_identity()
        if (
            context.turn_id != active_turn_id
            or context.generation_id != active_generation_id
        ):
            raise ValueError("stage context is not the active generation")
        stage = self._injected_stages.get(stage_kind)
        if stage is None or stage_kind not in self._stage_capabilities:
            raise RuntimeError("interruptible stage is not runtime-ready")

        work = self._begin_active_interrupt_stage_work(
            subsystem=subsystem_by_kind[stage_kind],
            stage=stage,
            context=context,
        )
        if work is None:
            return None
        try:
            with self._interrupt_stage_lock:
                suppressed_before_start = work.future_delivery_suppressed
            if suppressed_before_start:
                return None
            try:
                envelope = stage.start(context=context, request=request)
            except Exception:
                envelope = self._isolated_stage_failure_envelope(
                    stage_kind=stage_kind,
                    context=context,
                )
        finally:
            suppressed_after_start = self._complete_active_interrupt_stage_work(work)
        if suppressed_after_start:
            return None
        return envelope

    def _inactive_stage_coordination_result(
        self,
        *,
        subsystem: str,
        turn_id: TurnId | str | None,
        generation_id: GenerationId | None,
    ) -> object:
        """Describe one configured-but-idle or unsupported stage truthfully."""

        from .interrupt_coordination import InterruptSubsystemOutcome

        if subsystem == "text_generation":
            stage_kind = "text_generation"
            capability_name = "cooperative_cancel_supported"
        else:
            stage_kind = "voice_output"
            capability_name = "generation_cancel_supported"
        stage = self._injected_stages.get(stage_kind)
        capability = self._stage_capabilities.get(stage_kind)
        supported = bool(
            capability is not None
            and getattr(capability, capability_name, False)
        )
        if stage is None or capability is None or not supported:
            return self._coordination_subsystem_result(
                subsystem=subsystem,
                outcome=InterruptSubsystemOutcome.UNSUPPORTED,
                turn_id=turn_id,
                generation_id=generation_id,
                target_reached=stage is not None and capability is not None,
                safe_message="Interrupt cancellation is unsupported for this stage.",
            )
        return self._coordination_subsystem_result(
            subsystem=subsystem,
            outcome=InterruptSubsystemOutcome.NOT_ACTIVE,
            turn_id=turn_id,
            generation_id=generation_id,
            target_reached=True,
            safe_message="No matching stage generation is active.",
        )

    def _request_active_stage_cancel(
        self,
        *,
        subsystem: str,
        turn_id: TurnId | str | None,
        generation_id: GenerationId | None,
    ) -> _InterruptStageAttempt:
        """Invoke one cooperative stage cancel outside the operation lock."""

        with self._interrupt_stage_lock:
            work = self._active_interrupt_stage_work.get(subsystem)
            if work is None or (
                turn_id is not None
                and getattr(work.context, "turn_id", None) != turn_id
            ):
                return _InterruptStageAttempt(
                    subsystem=subsystem,
                    result=self._inactive_stage_coordination_result(
                        subsystem=subsystem,
                        turn_id=turn_id,
                        generation_id=generation_id,
                    ),
                )

            stage_kind = (
                "text_generation"
                if subsystem == "text_generation"
                else "voice_output"
            )
            capability = self._stage_capabilities.get(stage_kind)
            supported = bool(
                capability is not None
                and getattr(
                    capability,
                    (
                        "cooperative_cancel_supported"
                        if subsystem == "text_generation"
                        else "generation_cancel_supported"
                    ),
                    False,
                )
            )
            if not supported:
                from .interrupt_coordination import InterruptSubsystemOutcome

                return _InterruptStageAttempt(
                    subsystem=subsystem,
                    result=self._coordination_subsystem_result(
                        subsystem=subsystem,
                        outcome=InterruptSubsystemOutcome.UNSUPPORTED,
                        turn_id=getattr(work.context, "turn_id", turn_id),
                        generation_id=getattr(
                            work.context,
                            "generation_id",
                            generation_id,
                        ),
                        target_reached=True,
                        safe_message="Active stage cancellation is unsupported.",
                    ),
                )
            cancel_owner = not work.cancel_call_started
            if cancel_owner:
                work.cancel_call_started = True
                work.cancel_requested = True

        if cancel_owner:
            accepted = False
            failed = False
            raw_result: object | None = None
            try:
                raw_result = work.stage.cancel(context=work.context)
                if type(raw_result) is bool:
                    accepted = raw_result
                elif subsystem == "tts_generation":
                    from .realtime_voice_output import (
                        VoiceSynthesisCancelOutcome,
                        VoiceSynthesisCancelResult,
                    )

                    if not isinstance(raw_result, VoiceSynthesisCancelResult):
                        failed = True
                    elif raw_result.context != work.context:
                        failed = True
                    else:
                        accepted = raw_result.outcome in {
                            VoiceSynthesisCancelOutcome.REQUESTED,
                            VoiceSynthesisCancelOutcome.COMPLETED,
                            VoiceSynthesisCancelOutcome.TIMED_OUT,
                        }
                else:
                    failed = True
            except Exception:
                failed = True
            finally:
                with self._interrupt_stage_lock:
                    work.cancel_accepted = accepted
                    work.cancel_failed = failed
                    work.typed_cancel_result = raw_result
                    if accepted:
                        work.future_delivery_suppressed = True
                work.cancel_call_finished.set()
        else:
            work.cancel_call_finished.wait()

        return _InterruptStageAttempt(subsystem=subsystem, work=work)

    def _resolve_active_stage_cancel(
        self,
        attempt: _InterruptStageAttempt,
        *,
        deadline: float,
    ) -> object:
        """Resolve one stage cancellation using only observed effect facts."""

        from .interrupt_coordination import InterruptSubsystemOutcome

        if attempt.result is not None:
            return attempt.result
        work = attempt.work
        if work is None:
            raise AssertionError("stage cancel attempt must retain work or result")
        work.cancel_call_finished.wait()
        with self._interrupt_stage_lock:
            failed = work.cancel_failed
            accepted = work.cancel_accepted
            raw_result = work.typed_cancel_result
            capability = self._stage_capabilities.get(
                "text_generation"
                if attempt.subsystem == "text_generation"
                else "voice_output"
            )
            hard_supported = bool(
                capability is not None
                and getattr(capability, "provider_hard_cancel_supported", False)
            )

        if failed:
            return self._coordination_subsystem_result(
                subsystem=attempt.subsystem,
                outcome=InterruptSubsystemOutcome.FAILED,
                turn_id=getattr(work.context, "turn_id", None),
                generation_id=getattr(work.context, "generation_id", None),
                target_reached=True,
                cooperative_cancel_requested=True,
                safe_message="Stage cancellation failed safely.",
                retryable=True,
            )

        if attempt.subsystem == "tts_generation" and type(raw_result) is not bool:
            from .realtime_voice_output import (
                VoiceSynthesisCancelOutcome,
                VoiceSynthesisCancelResult,
            )

            if not isinstance(raw_result, VoiceSynthesisCancelResult):
                raise AssertionError("typed TTS cancel result was lost")
            mapped_outcome = {
                VoiceSynthesisCancelOutcome.REQUESTED: InterruptSubsystemOutcome.REQUESTED,
                VoiceSynthesisCancelOutcome.COMPLETED: InterruptSubsystemOutcome.COMPLETED,
                VoiceSynthesisCancelOutcome.TIMED_OUT: InterruptSubsystemOutcome.TIMED_OUT,
                VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION: InterruptSubsystemOutcome.NOT_ACTIVE,
                VoiceSynthesisCancelOutcome.WORK_MISMATCH: InterruptSubsystemOutcome.NOT_ACTIVE,
                VoiceSynthesisCancelOutcome.ALREADY_TERMINAL: InterruptSubsystemOutcome.ALREADY_TERMINAL,
                VoiceSynthesisCancelOutcome.UNSUPPORTED: InterruptSubsystemOutcome.UNSUPPORTED,
                VoiceSynthesisCancelOutcome.ALREADY_CLOSED: InterruptSubsystemOutcome.ALREADY_CLOSED,
                VoiceSynthesisCancelOutcome.FAILED: InterruptSubsystemOutcome.FAILED,
            }[raw_result.outcome]
            active = mapped_outcome in {
                InterruptSubsystemOutcome.REQUESTED,
                InterruptSubsystemOutcome.COMPLETED,
                InterruptSubsystemOutcome.TIMED_OUT,
                InterruptSubsystemOutcome.FAILED,
            }
            requested = bool(raw_result.cooperative_cancel_requested)
            accepted = accepted and requested
            completed = bool(raw_result.cooperative_cancel_completed)
            hard_applied = bool(raw_result.provider_hard_cancel_applied)
            if hard_applied and not hard_supported:
                mapped_outcome = InterruptSubsystemOutcome.FAILED
                hard_applied = False
                accepted = False
                completed = False
            if mapped_outcome is InterruptSubsystemOutcome.UNSUPPORTED:
                hard_supported = False
            return self._coordination_subsystem_result(
                subsystem=attempt.subsystem,
                outcome=mapped_outcome,
                turn_id=raw_result.context.turn_id,
                generation_id=raw_result.context.generation_id,
                target_reached=(
                    False
                    if mapped_outcome is InterruptSubsystemOutcome.ALREADY_CLOSED
                    else True
                ),
                cooperative_cancel_requested=requested if active else False,
                cooperative_cancel_accepted=accepted if active else False,
                cooperative_cancel_completed=completed if active else False,
                provider_hard_cancel_supported=(
                    hard_supported if active else False
                ),
                provider_hard_cancel_applied=hard_applied if active else False,
                future_delivery_suppressed=(
                    bool(raw_result.future_delivery_suppressed) or accepted
                    if active
                    else False
                ),
                affected_count=(1 if raw_result.artifact_invalidated else 0),
                safe_message=raw_result.safe_message,
                retryable=raw_result.retryable,
            )

        if not accepted:
            return self._coordination_subsystem_result(
                subsystem=attempt.subsystem,
                outcome=InterruptSubsystemOutcome.FAILED,
                turn_id=getattr(work.context, "turn_id", None),
                generation_id=getattr(work.context, "generation_id", None),
                target_reached=True,
                cooperative_cancel_requested=True,
                safe_message="Stage rejected cooperative cancellation.",
                retryable=True,
            )

        remaining = max(0.0, deadline - time.monotonic())
        completed = work.completion_event.wait(timeout=remaining)
        return self._coordination_subsystem_result(
            subsystem=attempt.subsystem,
            outcome=(
                InterruptSubsystemOutcome.COMPLETED
                if completed
                else InterruptSubsystemOutcome.TIMED_OUT
            ),
            turn_id=getattr(work.context, "turn_id", None),
            generation_id=getattr(work.context, "generation_id", None),
            target_reached=True,
            cooperative_cancel_requested=True,
            cooperative_cancel_accepted=True,
            cooperative_cancel_completed=completed,
            provider_hard_cancel_supported=hard_supported,
            provider_hard_cancel_applied=False,
            future_delivery_suppressed=True,
            affected_count=1 if completed else 0,
            safe_message=(
                "Stage cooperative cancellation completed."
                if completed
                else "Stage cooperative cancellation timed out."
            ),
            retryable=not completed,
        )

    def _voice_output_side_effect_result(
        self,
        *,
        subsystem: str,
        context: object | None,
    ) -> object:
        """Clear pending voice work or invalidate completed artifacts."""

        from .interrupt_coordination import InterruptSubsystemOutcome

        stage = self._injected_stages.get("voice_output")
        capability = self._stage_capabilities.get("voice_output")
        capability_name = (
            "pending_flush_supported"
            if subsystem == "tts_queue"
            else "active_audio_invalidation_supported"
        )
        supported = bool(
            capability is not None
            and getattr(capability, capability_name, False)
        )
        turn_id = getattr(context, "turn_id", None)
        generation_id = getattr(context, "generation_id", None)
        if stage is None or capability is None or not supported:
            return self._coordination_subsystem_result(
                subsystem=subsystem,
                outcome=InterruptSubsystemOutcome.UNSUPPORTED,
                turn_id=turn_id,
                generation_id=generation_id,
                target_reached=stage is not None and capability is not None,
                safe_message="Voice-output control is unsupported.",
            )
        if context is None:
            return self._coordination_subsystem_result(
                subsystem=subsystem,
                outcome=InterruptSubsystemOutcome.NOT_ACTIVE,
                turn_id=None,
                target_reached=True,
                safe_message="No active turn owns voice-output work.",
            )

        try:
            if subsystem == "tts_queue":
                clear_pending = getattr(stage, "clear_pending", None)
                if not callable(clear_pending):
                    raise TypeError("voice-output stage has no pending clear boundary")
                raw_result = clear_pending(context=context)
                from .realtime_voice_output_queue import (
                    VoiceSynthesisPendingClearOutcome,
                    VoiceSynthesisPendingClearResult,
                )

                if not isinstance(raw_result, VoiceSynthesisPendingClearResult):
                    raise TypeError("pending clear returned an invalid result")
                count = raw_result.cleared_count
                completed = (
                    raw_result.outcome is VoiceSynthesisPendingClearOutcome.CLEARED
                )
                safe_message = raw_result.safe_message
            else:
                invalidate = getattr(stage, "invalidate_completed", None)
                if not callable(invalidate):
                    raise TypeError("voice-output stage has no artifact invalidation boundary")
                count = invalidate(context)
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise TypeError("artifact invalidation returned an invalid count")
                completed = count > 0
                safe_message = (
                    "Completed voice artifacts were invalidated."
                    if completed
                    else "No completed voice artifact required invalidation."
                )
        except Exception:
            return self._coordination_subsystem_result(
                subsystem=subsystem,
                outcome=InterruptSubsystemOutcome.FAILED,
                turn_id=turn_id,
                generation_id=generation_id,
                target_reached=True,
                safe_message="Voice-output control failed safely.",
                retryable=True,
            )

        return self._coordination_subsystem_result(
            subsystem=subsystem,
            outcome=(
                InterruptSubsystemOutcome.COMPLETED
                if completed
                else InterruptSubsystemOutcome.NOT_ACTIVE
            ),
            turn_id=turn_id,
            generation_id=generation_id,
            target_reached=True,
            future_delivery_suppressed=completed,
            affected_count=count,
            safe_message=safe_message,
        )

    def _motion_coordination_result(self, motion_result: object) -> object:
        """Project the accepted motion-control facts into the common model."""

        from .interrupt_coordination import InterruptSubsystemOutcome
        from .motion_control import MotionControlOutcome, MotionControlResult

        if not isinstance(motion_result, MotionControlResult):
            raise TypeError("motion_result must be a MotionControlResult")
        outcome = {
            MotionControlOutcome.REQUESTED: InterruptSubsystemOutcome.REQUESTED,
            MotionControlOutcome.COMPLETED: InterruptSubsystemOutcome.COMPLETED,
            MotionControlOutcome.NOT_ACTIVE: InterruptSubsystemOutcome.NOT_ACTIVE,
            MotionControlOutcome.ALREADY_TERMINAL: InterruptSubsystemOutcome.ALREADY_TERMINAL,
            MotionControlOutcome.UNSUPPORTED: InterruptSubsystemOutcome.UNSUPPORTED,
            MotionControlOutcome.TIMED_OUT: InterruptSubsystemOutcome.TIMED_OUT,
            MotionControlOutcome.ALREADY_CLOSED: InterruptSubsystemOutcome.ALREADY_CLOSED,
            MotionControlOutcome.FAILED: InterruptSubsystemOutcome.FAILED,
        }[motion_result.outcome]
        active = outcome in {
            InterruptSubsystemOutcome.REQUESTED,
            InterruptSubsystemOutcome.COMPLETED,
            InterruptSubsystemOutcome.TIMED_OUT,
            InterruptSubsystemOutcome.FAILED,
        }
        stage_reached = self._injected_stages.get("motion") is not None
        return self._coordination_subsystem_result(
            subsystem="motion",
            outcome=outcome,
            turn_id=motion_result.turn_id,
            generation_id=motion_result.generation_id,
            target_reached=active or (
                stage_reached
                and outcome
                not in {InterruptSubsystemOutcome.ALREADY_CLOSED}
            ),
            cooperative_cancel_requested=(
                motion_result.cancel_requested if active else False
            ),
            cooperative_cancel_accepted=(
                motion_result.cancel_accepted if active else False
            ),
            cooperative_cancel_completed=(
                motion_result.cancel_completed if active else False
            ),
            provider_hard_cancel_supported=(
                motion_result.stop_motion_supported if active else False
            ),
            provider_hard_cancel_applied=(
                motion_result.stop_motion_applied if active else False
            ),
            future_delivery_suppressed=(
                motion_result.future_delivery_suppressed if active else False
            ),
            affected_count=(
                1
                if active
                and (
                    motion_result.cancel_completed
                    or motion_result.stop_motion_applied
                )
                else 0
            ),
            safe_message=motion_result.safe_message,
            retryable=motion_result.retryable,
        )

    def _request_interrupt_coordination(
        self,
        request: InterruptRequest,
    ) -> _InterruptCoordinationAttempt:
        """Reach every selected subsystem before taking the operation lock."""

        from .interrupt_coordination import InterruptSubsystemOutcome
        from .realtime_stage import RealtimeStageContext

        target_names = self._interrupt_target_names(request)
        with self._turn_admission_lock:
            current_turn_id, current_generation_id = self._active_turn_identity()
        turn_id = request.turn_id or current_turn_id
        terminal = (
            self._terminal_registry.get(turn_id)
            if turn_id is not None
            else None
        )
        terminal_target = terminal is not None
        closed = self._closed or self._close_requested
        target_matches = (
            turn_id is not None
            and turn_id == current_turn_id
            and current_generation_id is not None
        )
        context = (
            RealtimeStageContext(
                session_id=self._session_id,
                turn_id=turn_id,
                generation_id=current_generation_id,
                public_metadata={"boundary": "interrupt_coordination"},
            )
            if target_matches
            else None
        )

        timeout_seconds = request.timeout_seconds or 0.25
        deadline = time.monotonic() + timeout_seconds
        attempts: list[_InterruptStageAttempt] = []
        for subsystem in target_names:
            if subsystem == "motion":
                continue
            if closed or terminal_target:
                outcome = (
                    InterruptSubsystemOutcome.ALREADY_CLOSED
                    if closed
                    else InterruptSubsystemOutcome.ALREADY_TERMINAL
                )
                attempts.append(
                    _InterruptStageAttempt(
                        subsystem=subsystem,
                        result=self._coordination_subsystem_result(
                            subsystem=subsystem,
                            outcome=outcome,
                            turn_id=turn_id,
                            generation_id=(
                                None if terminal_target else current_generation_id
                            ),
                            target_reached=False,
                            safe_message=(
                                "Realtime session is already closed."
                                if closed
                                else "Realtime turn is already terminal."
                            ),
                        ),
                    )
                )
                continue
            if subsystem in {"text_generation", "tts_generation"}:
                attempts.append(
                    self._request_active_stage_cancel(
                        subsystem=subsystem,
                        turn_id=turn_id,
                        generation_id=(
                            current_generation_id if target_matches else None
                        ),
                    )
                )
                continue
            attempts.append(
                _InterruptStageAttempt(
                    subsystem=subsystem,
                    result=self._voice_output_side_effect_result(
                        subsystem=subsystem,
                        context=context,
                    ),
                )
            )

        motion_attempt = (
            self._request_motion_control(request)
            if "motion" in target_names
            else None
        )
        return _InterruptCoordinationAttempt(
            request=request,
            turn_id=turn_id,
            ordered_attempts=tuple(attempts),
            motion_attempt=motion_attempt,
            deadline=deadline,
        )

    def _resolve_interrupt_stage_attempts(
        self,
        attempt: _InterruptCoordinationAttempt,
    ) -> dict[str, object]:
        """Resolve text/TTS waits before taking the long operation lock."""

        return {
            stage_attempt.subsystem: self._resolve_active_stage_cancel(
                stage_attempt,
                deadline=attempt.deadline,
            )
            for stage_attempt in attempt.ordered_attempts
        }

    def _resolve_interrupt_coordination(
        self,
        attempt: _InterruptCoordinationAttempt,
        *,
        stage_results: Mapping[str, object],
    ) -> tuple[InterruptAggregateResult, MotionControlResult | None]:
        """Resolve motion after lock admission and derive the typed aggregate."""

        from .interrupt_coordination import InterruptAggregateResult

        by_subsystem = dict(stage_results)
        # Accepted FW-RT6-8c source invariant (now composed below):
        # motion_result=self._resolve_motion_control_attempt(motion_attempt)
        motion_result = self._resolve_motion_control_attempt(attempt.motion_attempt)
        if motion_result is not None:
            by_subsystem["motion"] = self._motion_coordination_result(motion_result)
        ordered = tuple(
            by_subsystem[name]
            for name in self._interrupt_target_names(attempt.request)
        )
        aggregate = InterruptAggregateResult.from_results(
            session_id=self._session_id,
            turn_id=attempt.turn_id,
            subsystem_results=ordered,
            timeout_seconds=attempt.request.timeout_seconds,
            safe_message="Interrupt subsystem coordination completed.",
            retryable=any(result.retryable for result in ordered),
            public_metadata={
                "boundary": "interrupt_coordination",
                "default_timeout_applied": attempt.request.timeout_seconds is None,
                "whole_request_duplicate_ordering_deferred": True,
                "barge_in_execution_deferred": True,
            },
        )
        return aggregate, motion_result

    @staticmethod
    def _interrupt_targets_motion(request: InterruptRequest) -> bool:
        """Whether this existing interrupt request reaches the motion stage."""

        return request.stop_motion or request.scope in {
            InterruptScope.CURRENT_TURN,
            InterruptScope.MOTION,
            InterruptScope.ALL,
        }

    def _inactive_motion_control_result(
        self,
        *,
        request: InterruptRequest,
        outcome: object,
        safe_message: str,
    ) -> MotionControlResult:
        """Build one typed no-effect result without importing it at root import."""

        from .motion_control import MotionControlResult

        capability = self._stage_capabilities.get(
            "motion",
            self._capability_snapshot.motion,
        )

        return MotionControlResult(
            outcome=outcome,
            session_id=self._session_id,
            turn_id=request.turn_id,
            stop_motion_requested=request.stop_motion,
            stop_motion_supported=capability.stop_motion_supported,
            safe_message=safe_message,
            retryable=False,
            public_metadata={
                "boundary": "motion_control",
                "active_motion": False,
            },
        )

    def _request_motion_control(
        self,
        request: InterruptRequest,
    ) -> _MotionControlAttempt | None:
        """Reach one active motion before taking the long session operation lock.

        ``MotionStage.cancel`` and the optional explicit ``STOP_MOTION`` request
        are deliberately invoked without ``_operation_lock``.  A stage call may
        be the work currently holding that lock, so taking it first would make
        cooperative cancellation impossible.
        """

        if not self._interrupt_targets_motion(request):
            return None

        from .motion import MotionOutcome, MotionRequest
        from .motion_control import MotionControlOutcome, MotionControlResult

        cancel_owner = False
        stop_owner = False
        with self._motion_control_lock:
            if self._closed or self._close_requested:
                return _MotionControlAttempt(
                    result=self._inactive_motion_control_result(
                        request=request,
                        outcome=MotionControlOutcome.ALREADY_CLOSED,
                        safe_message="Realtime session is already closed.",
                    )
                )

            work = self._active_motion_work
            if work is None or (
                request.turn_id is not None
                and getattr(work.request, "turn_id", None) != request.turn_id
            ):
                terminal = (
                    self._terminal_registry.get(request.turn_id)
                    if request.turn_id is not None
                    else None
                )
                outcome = (
                    MotionControlOutcome.ALREADY_TERMINAL
                    if terminal is not None
                    else MotionControlOutcome.NOT_ACTIVE
                )
                return _MotionControlAttempt(
                    result=self._inactive_motion_control_result(
                        request=request,
                        outcome=outcome,
                        safe_message=(
                            "Realtime turn is already terminal."
                            if terminal is not None
                            else "There is no active motion request."
                        ),
                    )
                )

            capability = self._stage_capabilities.get(
                "motion",
                self._capability_snapshot.motion,
            )
            cancel_supported = capability.request_cancel_supported
            stop_requested = request.stop_motion
            stop_supported = capability.stop_motion_supported

            if not cancel_supported and not (stop_requested and stop_supported):
                return _MotionControlAttempt(
                    result=MotionControlResult(
                        outcome=MotionControlOutcome.UNSUPPORTED,
                        session_id=self._session_id,
                        turn_id=work.request.turn_id,
                        generation_id=work.request.generation_id,
                        request_id=work.request.request_id,
                        stop_motion_requested=stop_requested,
                        stop_motion_supported=stop_supported,
                        safe_message="Motion cancellation and stop are unsupported.",
                        retryable=False,
                        public_metadata={
                            "boundary": "motion_control",
                            "active_motion": True,
                            "request_cancel_supported": False,
                        },
                    )
                )

            if cancel_supported:
                if not work.cancel_call_started:
                    work.cancel_call_started = True
                    work.cancel_requested = True
                    cancel_owner = True

            if stop_requested:
                work.stop_motion_requested = True
                work.stop_motion_supported = stop_supported
                if stop_supported and not work.stop_call_started:
                    work.stop_call_started = True
                    stop_owner = True

        if cancel_owner:
            cancel_accepted = False
            cancel_failed = False
            try:
                raw_accepted = work.stage.cancel(context=work.context)
                if type(raw_accepted) is not bool:
                    cancel_failed = True
                else:
                    cancel_accepted = raw_accepted
            except Exception:
                cancel_failed = True
            finally:
                with self._motion_control_lock:
                    work.cancel_accepted = cancel_accepted
                    work.cancel_failed = cancel_failed
                    if cancel_accepted:
                        work.future_delivery_suppressed = True
                work.cancel_call_finished.set()
        elif work.cancel_call_started:
            work.cancel_call_finished.wait()

        if stop_owner:
            stop_applied = False
            stop_failed = False
            try:
                stop_request = MotionRequest.stop_motion(
                    turn_id=work.request.turn_id,
                    generation_id=work.request.generation_id,
                    public_metadata={
                        "boundary": "motion_control",
                        "interrupt_reason": request.reason.value,
                    },
                )
                raw_envelope = work.stage.start(
                    context=work.context,
                    request=stop_request,
                )
                stop_result = self._validated_motion_stage_result(
                    envelope=raw_envelope,
                    context=work.context,
                    request=stop_request,
                )
                stop_applied = (
                    stop_result is not None
                    and stop_result.outcome is MotionOutcome.COMPLETED
                )
                stop_failed = not stop_applied
            except Exception:
                stop_failed = True
            finally:
                with self._motion_control_lock:
                    work.stop_motion_applied = stop_applied
                    work.stop_failed = stop_failed
                work.stop_call_finished.set()
        elif work.stop_call_started:
            work.stop_call_finished.wait()

        return _MotionControlAttempt(work=work)

    def _resolve_motion_control_attempt(
        self,
        attempt: _MotionControlAttempt | None,
    ) -> MotionControlResult | None:
        """Resolve one split-phase motion attempt using only observed facts."""

        if attempt is None:
            return None
        if attempt.result is not None:
            from .motion_control import MotionControlResult

            if not isinstance(attempt.result, MotionControlResult):
                raise AssertionError("motion-control result must be typed")
            return attempt.result

        from .motion_control import MotionControlOutcome, MotionControlResult

        work = attempt.work
        if work is None:
            raise AssertionError("motion-control attempt must retain work or result")
        if work.cancel_call_started:
            work.cancel_call_finished.wait()
        if work.stop_call_started:
            work.stop_call_finished.wait()

        with self._motion_control_lock:
            cancel_requested = work.cancel_requested
            cancel_accepted = work.cancel_accepted
            cancel_completed = (
                cancel_accepted and work.completion_event.is_set()
            )
            stop_requested = work.stop_motion_requested
            stop_supported = work.stop_motion_supported
            stop_applied = work.stop_motion_applied
            future_suppressed = work.future_delivery_suppressed
            failed = work.cancel_failed or work.stop_failed

        if cancel_completed or stop_applied:
            outcome = MotionControlOutcome.COMPLETED
            safe_message = "Motion control completed."
            retryable = False
        elif cancel_accepted:
            outcome = MotionControlOutcome.REQUESTED
            safe_message = "Motion cancellation was accepted."
            retryable = False
        elif failed or cancel_requested or (stop_requested and stop_supported):
            outcome = MotionControlOutcome.FAILED
            safe_message = "Motion control failed safely."
            retryable = True
        else:
            outcome = MotionControlOutcome.UNSUPPORTED
            safe_message = "Motion cancellation and stop are unsupported."
            retryable = False

        return MotionControlResult(
            outcome=outcome,
            session_id=self._session_id,
            turn_id=work.request.turn_id,
            generation_id=work.request.generation_id,
            request_id=work.request.request_id,
            cancel_requested=cancel_requested,
            cancel_accepted=cancel_accepted,
            cancel_completed=cancel_completed,
            stop_motion_requested=stop_requested,
            stop_motion_supported=stop_supported,
            stop_motion_applied=stop_applied,
            future_delivery_suppressed=future_suppressed,
            safe_message=safe_message,
            retryable=retryable,
            public_metadata={
                "boundary": "motion_control",
                "active_motion": True,
                "cancel_call_started": work.cancel_call_started,
                "stop_call_started": work.stop_call_started,
                "duplicate_stage_control_suppressed": True,
                "whole_turn_aggregate_changed": False,
            },
        )

    def _coordinated_interrupt_result(
        self,
        *,
        request: InterruptRequest,
        current_turn_id: TurnId | str | None,
        coordination_result: InterruptAggregateResult,
    ) -> InterruptResult:
        """Map the richer aggregate onto the accepted v5.2 outer enum."""

        from .interrupt_coordination import InterruptAggregateOutcome

        effective = any(
            result.effective
            for result in coordination_result.subsystem_results
        )
        if self._closed or self._close_requested:
            outcome = "already_closed"
            safe_message = "Session is already closed."
            retryable = False
        elif coordination_result.outcome in {
            InterruptAggregateOutcome.TIMED_OUT,
            InterruptAggregateOutcome.FAILED,
        }:
            outcome = "failed"
            safe_message = "Interrupt coordination did not complete cleanly."
            retryable = True
        elif effective:
            outcome = "accepted"
            safe_message = "Interrupt coordination was accepted."
            retryable = False
        elif coordination_result.outcome is InterruptAggregateOutcome.ALREADY_TERMINAL:
            outcome = "no_active_turn"
            safe_message = "Realtime turn is already terminal."
            retryable = False
        elif current_turn_id is None and request.turn_id is None:
            outcome = "no_active_turn"
            safe_message = "There is no active realtime turn to interrupt."
            retryable = False
        elif coordination_result.outcome is InterruptAggregateOutcome.UNSUPPORTED:
            outcome = "unsupported"
            safe_message = "Requested interrupt targets are unsupported."
            retryable = False
        else:
            # Preserve the accepted explicit-unknown-turn compatibility result.
            outcome = "not_implemented"
            safe_message = "No matching active interrupt target was found."
            retryable = False

        queue_results = tuple(
            result
            for result in coordination_result.subsystem_results
            if result.subsystem.value == "tts_queue"
        )
        return InterruptResult(
            outcome=outcome,
            scope=request.scope,
            reason=request.reason,
            turn_id=request.turn_id or current_turn_id,
            safe_message=safe_message,
            retryable=retryable,
            provider_cancel_supported=any(
                result.provider_hard_cancel_supported
                for result in coordination_result.subsystem_results
            ),
            queue_flush_supported=bool(
                queue_results
                and queue_results[0].outcome.value != "unsupported"
            ),
            public_metadata={
                "boundary": "interrupt",
                "coordination_outcome": coordination_result.outcome.value,
                "coordination_effective": effective,
            },
            coordination_result=coordination_result,
        )

    @staticmethod
    def _attach_motion_control_result(
        result: InterruptResult,
        motion_result: MotionControlResult | None,
        coordination_result: InterruptAggregateResult | None = None,
    ) -> InterruptResult:
        """Project additive control results without changing other facts."""

        attached_coordination = (
            coordination_result
            if coordination_result is not None
            else result.coordination_result
        )
        if motion_result is None and attached_coordination is result.coordination_result:
            return result
        return InterruptResult(
            outcome=result.outcome,
            scope=result.scope,
            reason=result.reason,
            turn_id=result.turn_id,
            safe_message=result.safe_message,
            retryable=result.retryable,
            provider_cancel_supported=result.provider_cancel_supported,
            queue_flush_supported=result.queue_flush_supported,
            public_metadata=result.public_metadata,
            motion_result=motion_result,
            coordination_result=attached_coordination,
        )

    def get_tts_queue_state(self) -> TTSQueueState:
        """Return a mock-safe public TTS queue snapshot."""

        return TTSQueueState(
            queued_count=0,
            is_playing=False,
            supports_flush=False,
            supports_provider_cancel=False,
            playback_stop_required=False,
            safe_message="No public TTS queue is active in the mock realtime session.",
            public_metadata={
                "boundary": "tts_queue",
                "reason": "mock_queue_empty",
            },
        )

    def _claim_interrupt_request(
        self,
        request: InterruptRequest,
    ) -> tuple[str, _InterruptRequestWork | None]:
        """Choose a sole active-turn owner before any subsystem side effect."""

        with self._turn_admission_lock:
            current_turn_id, current_generation_id = self._active_turn_identity()
            resolved_turn_id = request.turn_id or current_turn_id
            with self._interrupt_request_lock:
                if resolved_turn_id is not None:
                    key = (self._session_id, resolved_turn_id)
                    existing = self._interrupt_requests.get(key)
                    if existing is not None:
                        return "duplicate", existing
                if self._close_admission_requested and not self._closed:
                    return "close_won", None
                if self._closed or self._close_requested:
                    return "legacy", None
                if (
                    resolved_turn_id is None
                    or current_turn_id is None
                    or resolved_turn_id != current_turn_id
                ):
                    return "legacy", None

                key = (self._session_id, resolved_turn_id)
                if key in self._normal_terminal_reservations:
                    return "legacy", None
                if self._terminal_registry.get(resolved_turn_id) is not None:
                    return "legacy", None

                reserved_terminal = RealtimeTurnResult.interrupted(
                    turn_id=resolved_turn_id,
                    safe_message="Realtime turn was interrupted.",
                    public_metadata={
                        "boundary": "interrupt_coordination",
                        "terminal_reserved": True,
                    },
                    session_id=self._session_id,
                    generation_id=current_generation_id,
                )
                work = _InterruptRequestWork(
                    key=key,
                    turn_id=resolved_turn_id,
                    generation_id=current_generation_id,
                    owner_thread_id=get_ident(),
                    reserved_terminal=reserved_terminal,
                )
                self._interrupt_requests[key] = work
                self._active_interrupt_request = work
                return "owner", work

    def _resolve_interrupt_terminal_reservation(
        self,
        work: _InterruptRequestWork,
        *,
        interrupt_won: bool,
    ) -> None:
        """Publish only the winning terminal after the owner resolves."""

        with self._interrupt_request_lock:
            work.reservation_active = False
            deferred = work.deferred_terminal
            work.deferred_terminal = None
        if interrupt_won or deferred is None:
            return
        self._commit_terminal_result(
            deferred.result,
            event_type=deferred.event_type,
            new_state=deferred.new_state,
            reason=deferred.reason,
            public_error_code=deferred.public_error_code,
            safe_message=deferred.safe_message,
            retryable=deferred.retryable,
            public_metadata=deferred.public_metadata,
            _interrupt_owner=work,
        )
        with self._turn_admission_lock:
            context = self._active_turn_context
            if context is not None and context.turn_id == deferred.result.turn_id:
                self._clear_active_turn_context()

    def _complete_interrupt_request(
        self,
        work: _InterruptRequestWork,
        result: InterruptResult,
    ) -> None:
        """Publish one owner result to every waiter, then honor deferred close."""

        with self._interrupt_request_lock:
            work.result = result
            work.reservation_active = False
            if self._active_interrupt_request is work:
                self._active_interrupt_request = None
            close_after_completion = work.close_after_completion
            work.completion_event.set()
        if close_after_completion:
            self.close()

    def _execute_interrupt_once(
        self,
        request: InterruptRequest,
        *,
        advance_reason: GenerationAdvanceReason | str,
        owner_work: _InterruptRequestWork | None = None,
    ) -> InterruptResult:
        """Execute the established aggregate path for one admitted owner."""

        coordination_attempt = self._request_interrupt_coordination(request)
        stage_results = self._resolve_interrupt_stage_attempts(
            coordination_attempt
        )
        with self._serialized_operation():
            coordination_result, motion_result = self._resolve_interrupt_coordination(
                coordination_attempt,
                stage_results=stage_results,
            )
            prepared_result: InterruptResult | None = None
            if owner_work is not None:
                prepared_result = self._prepare_interrupt_result(
                    request,
                    motion_result=motion_result,
                    coordination_result=coordination_result,
                )
                with self._interrupt_request_lock:
                    owner_work.result = prepared_result
            if owner_work is not None and request.flush_output:
                owner_work.flush_result = self._flush_output_serialized(
                    OutputFlushRequest(
                        scope=request.scope,
                        turn_id=owner_work.turn_id,
                        public_metadata={
                            "boundary": "interrupt_owner_flush",
                        },
                    ),
                    _interrupt_owner=owner_work,
                )
            result = self._interrupt_serialized(
                request,
                advance_reason=advance_reason,
                motion_result=motion_result,
                coordination_result=coordination_result,
                _owner_work=owner_work,
                _prepared_result=prepared_result,
            )
            if owner_work is not None:
                self._resolve_interrupt_terminal_reservation(
                    owner_work,
                    interrupt_won=result.outcome.value == "accepted",
                )
            return result

    def _ordered_interrupt(
        self,
        request: InterruptRequest,
        *,
        advance_reason: GenerationAdvanceReason | str,
    ) -> InterruptResult:
        """Converge one resolved turn on a sole whole-request owner."""

        admission, work = self._claim_interrupt_request(request)
        if admission == "close_won":
            return InterruptResult.already_closed(request=request)
        if admission == "legacy":
            return self._execute_interrupt_once(
                request,
                advance_reason=advance_reason,
            )
        if admission == "duplicate":
            if work is None:
                raise AssertionError("duplicate interrupt must retain owner work")
            if work.owner_thread_id == get_ident():
                if work.result is None:
                    return InterruptResult(
                        outcome="failed",
                        scope=request.scope,
                        reason=request.reason,
                        turn_id=work.turn_id,
                        safe_message=(
                            "Reentrant interrupt replay is not ready yet."
                        ),
                        retryable=True,
                        public_metadata={
                            "boundary": "interrupt",
                            "reason": "reentrant_owner_result_pending",
                        },
                    )
                return work.result
            work.completion_event.wait()
            if work.result is None:
                raise AssertionError("interrupt owner must retain its exact result")
            return work.result
        if admission != "owner" or work is None:
            raise AssertionError("interrupt admission must resolve to one owner")

        try:
            result = self._execute_interrupt_once(
                request,
                advance_reason=advance_reason,
                owner_work=work,
            )
        except Exception:
            result = InterruptResult(
                outcome="failed",
                scope=request.scope,
                reason=request.reason,
                turn_id=work.turn_id,
                safe_message="Interrupt ordering failed safely.",
                retryable=True,
                public_metadata={
                    "boundary": "interrupt",
                    "reason": "ordering_failure",
                },
            )
            with self._serialized_operation():
                self._resolve_interrupt_terminal_reservation(
                    work,
                    interrupt_won=False,
                )
        self._complete_interrupt_request(work, result)
        return result

    def interrupt(self, request: InterruptRequest | None = None) -> InterruptResult:
        request = request or InterruptRequest()
        return self._ordered_interrupt(request, advance_reason="interrupt")

    def _prepare_interrupt_result(
        self,
        request: InterruptRequest,
        *,
        motion_result: MotionControlResult | None = None,
        coordination_result: InterruptAggregateResult | None = None,
    ) -> InterruptResult:
        """Prepare the immutable owner result before synchronous callbacks."""

        if self._closed or self._close_requested:
            result = InterruptResult.already_closed(request=request)
        else:
            current_turn_id = (
                self._generation_gate.current_turn_id
                or self._active_turn_id
            )
            no_active_turn = current_turn_id is None and request.turn_id is None
            result = (
                self._coordinated_interrupt_result(
                    request=request,
                    current_turn_id=current_turn_id,
                    coordination_result=coordination_result,
                )
                if coordination_result is not None
                else (
                    InterruptResult.no_active_turn(request=request)
                    if no_active_turn
                    else InterruptResult.not_implemented(request=request)
                )
            )
        return self._attach_motion_control_result(
            result,
            motion_result,
            coordination_result,
        )

    def _interrupt_serialized(
        self,
        request: InterruptRequest | None = None,
        *,
        advance_reason: GenerationAdvanceReason | str = "interrupt",
        motion_result: MotionControlResult | None = None,
        coordination_result: InterruptAggregateResult | None = None,
        _owner_work: _InterruptRequestWork | None = None,
        _prepared_result: InterruptResult | None = None,
    ) -> InterruptResult:
        """Request a provider-neutral interrupt.

        Real hard cancellation is not implemented yet. This method provides a
        stable public result and emits public realtime events without touching
        provider internals.
        """

        request = request or InterruptRequest()
        if self._closed or self._close_requested:
            return _prepared_result or self._prepare_interrupt_result(
                request,
                motion_result=motion_result,
                coordination_result=coordination_result,
            )

        current_turn_id = (
            self._generation_gate.current_turn_id
            or self._active_turn_id
        )
        no_active_turn = current_turn_id is None and request.turn_id is None
        result = _prepared_result or self._prepare_interrupt_result(
            request,
            motion_result=motion_result,
            coordination_result=coordination_result,
        )
        resolved_turn_id = request.turn_id or current_turn_id
        self._advance_generation(
            advance_reason,
            turn_id=resolved_turn_id,
        )

        try:
            self._transition(
                RealtimeEventType.INTERRUPT_REQUESTED,
                self._state,
                turn_id=resolved_turn_id,
                payload=InterruptEventPayload(
                    scope=request.scope,
                    outcome=result.outcome,
                    reason=request.reason.value,
                ),
                public_metadata={
                    "scope": request.scope.value,
                    "reason": request.reason.value,
                },
            )

            if no_active_turn:
                self._transition(
                    RealtimeEventType.INTERRUPT_UNSUPPORTED,
                    self._state,
                    payload=InterruptEventPayload(
                        scope=request.scope,
                        outcome=result.outcome,
                        reason=request.reason.value,
                    ),
                    public_error_code=RealtimeErrorCode.UNSUPPORTED,
                    safe_message=result.safe_message,
                    public_metadata={
                        "scope": request.scope.value,
                        "reason": request.reason.value,
                        "interrupt_outcome": result.outcome.value,
                    },
                )
                return result

            if result.outcome.value == "accepted":
                self._transition(
                    RealtimeEventType.INTERRUPT_ACCEPTED,
                    RealtimeState.INTERRUPTED,
                    turn_id=resolved_turn_id,
                    new_phase=(
                        RealtimePhase.RECOVERING
                        if self._active_turn_id is not None
                        else _PHASE_UNCHANGED
                    ),
                    payload=InterruptEventPayload(
                        scope=request.scope,
                        outcome=result.outcome,
                        reason=request.reason.value,
                    ),
                    safe_message=result.safe_message,
                    public_metadata={
                        "scope": request.scope.value,
                        "reason": request.reason.value,
                        "coordination_outcome": (
                            coordination_result.outcome.value
                            if coordination_result is not None
                            else "unavailable"
                        ),
                    },
                )
                if coordination_result is not None and coordination_result.is_terminal:
                    self._transition(
                        RealtimeEventType.INTERRUPT_COMPLETED,
                        RealtimeState.INTERRUPTED,
                        turn_id=resolved_turn_id,
                        payload=InterruptEventPayload(
                            scope=request.scope,
                            outcome=result.outcome,
                            reason=request.reason.value,
                        ),
                        safe_message=result.safe_message,
                        public_metadata={
                            "scope": request.scope.value,
                            "reason": request.reason.value,
                            "coordination_outcome": coordination_result.outcome.value,
                        },
                    )

                if (
                    resolved_turn_id is not None
                    and resolved_turn_id == current_turn_id
                    and self._terminal_registry.get(resolved_turn_id) is None
                ):
                    interrupted = (
                        _owner_work.reserved_terminal
                        if _owner_work is not None
                        and _owner_work.reserved_terminal is not None
                        else RealtimeTurnResult.interrupted(
                            turn_id=resolved_turn_id,
                            safe_message="Realtime turn was interrupted.",
                            public_metadata={
                                "boundary": "interrupt_coordination",
                                "coordination_outcome": (
                                    coordination_result.outcome.value
                                    if coordination_result is not None
                                    else "unavailable"
                                ),
                            },
                            session_id=self._session_id,
                            generation_id=self._active_generation_id,
                        )
                    )
                    self._commit_terminal_result(
                        interrupted,
                        event_type=RealtimeEventType.TURN_INTERRUPTED,
                        new_state=RealtimeState.INTERRUPTED,
                        reason="interrupt_coordination_completed",
                        public_error_code=RealtimeErrorCode.INTERRUPTED,
                        safe_message=interrupted.safe_message,
                        retryable=True,
                        _interrupt_owner=_owner_work,
                    )
                    with self._turn_admission_lock:
                        self._clear_active_turn_context()

                self._set_phase(RealtimePhase.IDLE)
                self._state = RealtimeState.IDLE
                return result

            if result.outcome.value == "failed":
                self._transition(
                    RealtimeEventType.INTERRUPT_COMPLETED,
                    RealtimeState.INTERRUPTED,
                    turn_id=resolved_turn_id,
                    new_phase=(
                        RealtimePhase.RECOVERING
                        if self._active_turn_id is not None
                        else _PHASE_UNCHANGED
                    ),
                    payload=InterruptEventPayload(
                        scope=request.scope,
                        outcome=result.outcome,
                        reason=request.reason.value,
                    ),
                    public_error_code=RealtimeErrorCode.STAGE_FAILED,
                    safe_message=result.safe_message,
                    retryable=result.retryable,
                    public_metadata={
                        "scope": request.scope.value,
                        "reason": request.reason.value,
                        "coordination_outcome": (
                            coordination_result.outcome.value
                            if coordination_result is not None
                            else "unavailable"
                        ),
                    },
                )
                self._set_phase(RealtimePhase.IDLE)
                self._state = RealtimeState.IDLE
                return result

            next_phase = (
                RealtimePhase.RECOVERING
                if self._active_turn_id is not None
                else _PHASE_UNCHANGED
            )
            self._transition(
                RealtimeEventType.INTERRUPT_UNSUPPORTED,
                RealtimeState.INTERRUPTED,
                turn_id=resolved_turn_id,
                new_phase=next_phase,
                payload=InterruptEventPayload(
                    scope=request.scope,
                    outcome=result.outcome,
                    reason=request.reason.value,
                ),
                public_error_code=RealtimeErrorCode.UNSUPPORTED,
                safe_message=result.safe_message,
                public_metadata={
                    "scope": request.scope.value,
                    "reason": request.reason.value,
                    "interrupt_outcome": result.outcome.value,
                },
            )
        except _LateNonTerminalRejected:
            if _prepared_result is not None:
                return _prepared_result
            return self._attach_motion_control_result(
                InterruptResult.no_active_turn(
                    request=request,
                    safe_message="Realtime turn is already terminal.",
                ),
                motion_result,
                coordination_result,
            )

        self._set_phase(RealtimePhase.IDLE)
        self._state = RealtimeState.IDLE
        return result

    def cancel_current_turn(
        self,
        *,
        reason: InterruptReason | str = InterruptReason.HOST_APP_REQUEST,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> InterruptResult:
        """Request cancellation of the current realtime turn."""

        request = InterruptRequest(
            scope=InterruptScope.CURRENT_TURN,
            reason=reason,
            turn_id=self._generation_gate.current_turn_id,
            cancel_llm_stream=True,
            cancel_tts_queue=True,
            public_metadata=public_metadata or {},
        )
        return self._ordered_interrupt(request, advance_reason="cancel")

    def acknowledge_host_playback_stop(
        self,
        *,
        turn_id: TurnId | str | None = None,
        acknowledged: bool = True,
    ) -> RealtimeEvent | None:
        """Record an optional host acknowledgement without claiming physical stop."""

        if not isinstance(acknowledged, bool):
            raise TypeError("acknowledged must be a boolean")
        with self._serialized_operation():
            if self._closed or self._close_requested:
                return None
            capability = self._capability_snapshot.voice_output
            if (
                capability.playback_ownership != "host"
                or not capability.host_playback_stop_ack_supported
            ):
                return None

            resolved_turn_id, generation_id = self._host_playback_context(turn_id)
            key = (resolved_turn_id, generation_id)
            requested = self._host_playback_stop_requests.get(key)
            if requested is None:
                return None
            existing = self._host_playback_stop_acknowledgements.get(key)
            if existing is not None:
                return existing

            artifact_ref = (
                requested.payload.artifact_ref
                if isinstance(requested.payload, AudioEventPayload)
                else None
            )
            event = self._transition(
                RealtimeEventType.PLAYBACK_STOP_ACKNOWLEDGED_BY_HOST,
                self._state,
                turn_id=resolved_turn_id,
                payload=AudioEventPayload(
                    artifact_ref=artifact_ref,
                    host_stop_requested=True,
                    host_stop_acknowledged=acknowledged,
                ),
                public_metadata={
                    "playback_ownership": "host",
                    "host_stop_acknowledged": acknowledged,
                    "physical_playback_stop_confirmed": False,
                },
                _event_generation_id=generation_id,
            )
            self._host_playback_stop_acknowledgements[key] = event
            return event

    def _request_host_playback_stop_serialized(
        self,
        *,
        turn_id: TurnId | str | None,
        artifact_ref: str | None = None,
        reason: str,
    ) -> RealtimeEvent | None:
        capability = self._capability_snapshot.voice_output
        if (
            capability.playback_ownership != "host"
            or not capability.host_playback_stop_request_supported
        ):
            return None

        resolved_turn_id, generation_id = self._host_playback_context(turn_id)
        key = (resolved_turn_id, generation_id)
        existing = self._host_playback_stop_requests.get(key)
        if existing is not None:
            return existing

        event = self._transition(
            RealtimeEventType.PLAYBACK_STOP_REQUESTED_TO_HOST,
            self._state,
            turn_id=resolved_turn_id,
            payload=AudioEventPayload(
                artifact_ref=artifact_ref,
                host_stop_requested=True,
            ),
            public_metadata={
                "playback_ownership": "host",
                "reason": reason,
                "physical_playback_stop_confirmed": False,
            },
            _event_generation_id=generation_id,
        )
        self._host_playback_stop_requests[key] = event
        return event

    def _record_voice_artifact_invalidation(
        self,
        *,
        turn_id: TurnId | str | None,
        generation_id: GenerationId | None,
        invalidated_artifact_count: int,
        artifact_ref: str | None = None,
    ) -> RealtimeEvent:
        """Adopt a positive FW-RT6-6d invalidation fact into canonical events."""

        if (
            isinstance(invalidated_artifact_count, bool)
            or not isinstance(invalidated_artifact_count, int)
        ):
            raise TypeError("invalidated_artifact_count must be an integer")
        if invalidated_artifact_count <= 0:
            raise ValueError("invalidated_artifact_count must be positive")

        with self._serialized_operation():
            return self._transition(
                RealtimeEventType.AUDIO_INVALIDATED,
                self._state,
                turn_id=turn_id,
                payload=AudioEventPayload(
                    artifact_ref=artifact_ref,
                    invalidated=True,
                ),
                public_metadata={
                    "invalidated_artifact_count": invalidated_artifact_count,
                    "physical_playback_stop_confirmed": False,
                },
                _event_generation_id=generation_id,
            )

    def flush_output(self, request: OutputFlushRequest | None = None) -> OutputFlushResult:
        request = request or OutputFlushRequest()
        with self._interrupt_request_lock:
            interrupt_work = self._active_interrupt_request
            interrupt_active = (
                interrupt_work is not None
                and not interrupt_work.completion_event.is_set()
            )
            same_turn = bool(
                interrupt_work is not None
                and (
                    request.turn_id is None
                    or request.turn_id == interrupt_work.turn_id
                )
            )
            reentrant_owner = bool(
                interrupt_active
                and same_turn
                and interrupt_work is not None
                and interrupt_work.owner_thread_id == get_ident()
            )
            if (
                reentrant_owner
                and interrupt_work is not None
                and interrupt_work.flush_result is not None
            ):
                return interrupt_work.flush_result
            should_wait = bool(interrupt_active and not reentrant_owner)
        if should_wait:
            if interrupt_work is None:
                raise AssertionError("active interrupt flush must retain owner work")
            interrupt_work.completion_event.wait()
            if (
                interrupt_work.flush_result is not None
                and (
                    request.turn_id is None
                    or request.turn_id == interrupt_work.turn_id
                )
            ):
                return interrupt_work.flush_result
        with self._serialized_operation():
            return self._flush_output_serialized(
                request,
                _interrupt_owner=(
                    interrupt_work
                    if reentrant_owner and interrupt_work is not None
                    else None
                ),
            )

    def _flush_output_serialized(
        self,
        request: OutputFlushRequest | None = None,
        *,
        _interrupt_owner: _InterruptRequestWork | None = None,
    ) -> OutputFlushResult:
        """Request a provider-neutral output flush.

        Real queue flush / playback stop is not implemented yet. Empty mock queue
        and closed-session cases are represented as typed public results.
        """

        request = request or OutputFlushRequest()
        if self._closed or self._close_requested:
            return OutputFlushResult.closed(request=request)

        resolved_turn_id = request.turn_id or self._active_turn_id
        queue_state = self.get_tts_queue_state()
        result = (
            OutputFlushResult.nothing_to_flush(request=request)
            if queue_state.queued_count == 0 and not queue_state.is_playing
            else OutputFlushResult.not_implemented(request=request)
        )
        if _interrupt_owner is not None:
            with self._interrupt_request_lock:
                _interrupt_owner.flush_result = result
        try:
            self._transition(
                RealtimeEventType.OUTPUT_FLUSH_REQUESTED,
                self._state,
                turn_id=resolved_turn_id,
                public_metadata={
                    "scope": request.scope.value,
                    "stop_playback": request.stop_playback,
                    "clear_queued_audio": request.clear_queued_audio,
                },
            )

            host_stop_event = None
            if request.stop_playback and queue_state.playback_stop_required:
                host_stop_event = self._request_host_playback_stop_serialized(
                    turn_id=resolved_turn_id,
                    reason="output_flush",
                )

            if queue_state.queued_count == 0 and not queue_state.is_playing:
                self._transition(
                    RealtimeEventType.OUTPUT_FLUSH_COMPLETED,
                    self._state,
                    turn_id=resolved_turn_id,
                    safe_message=result.safe_message,
                    public_metadata={
                        "flush_outcome": result.outcome.value,
                        "queued_count": queue_state.queued_count,
                        "host_playback_stop_requested": host_stop_event is not None,
                        "physical_playback_stop_confirmed": False,
                    },
                )
                return result

            self._transition(
                RealtimeEventType.OUTPUT_FLUSH_UNSUPPORTED,
                self._state,
                turn_id=resolved_turn_id,
                public_error_code=RealtimeErrorCode.UNSUPPORTED,
                safe_message=result.safe_message,
                public_metadata={
                    "flush_outcome": result.outcome.value,
                    "queued_count": queue_state.queued_count,
                    "host_playback_stop_requested": host_stop_event is not None,
                    "physical_playback_stop_confirmed": False,
                },
            )
            return result
        except _LateNonTerminalRejected:
            if _interrupt_owner is not None:
                return result
            return OutputFlushResult.nothing_to_flush(
                request=request,
                safe_message="Realtime turn is already terminal.",
            )

    def set_barge_in_policy(self, policy: BargeInPolicy) -> BargeInPolicy:
        """Set the public barge-in policy for future host-app decisions."""

        with self._serialized_operation():
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            if not isinstance(policy, BargeInPolicy):
                raise TypeError("policy must be a BargeInPolicy")
            self._barge_in_policy = policy
            return self._barge_in_policy

    def set_motion_lifecycle_hook(
        self,
        hook: MotionLifecycleHook | None,
    ) -> None:
        """Set the single host/plugin lifecycle-to-motion mapping hook.

        Registration is explicit and session-owned. ``None`` disables mapping.
        The hook cannot be replaced while a turn is active so one admitted turn
        always observes one deterministic mapping owner.
        """

        with self._serialized_operation():
            if self._closed or self._close_requested:
                raise self._session_closed_error()
            if self._active_turn_identity()[0] is not None:
                raise RuntimeError(
                    "motion lifecycle hook cannot change while a turn is active"
                )
            if hook is not None and not callable(hook):
                raise TypeError("hook must be callable or None")
            self._motion_lifecycle_hook = hook

    @staticmethod
    def _realtime_state_for_motion_state(state: MotionState) -> RealtimeState:
        from .motion import MotionState

        if state is MotionState.IDLE:
            return RealtimeState.IDLE
        if state is MotionState.INTERRUPTED:
            return RealtimeState.INTERRUPTED
        if state in {MotionState.FAILED, MotionState.UNAVAILABLE}:
            return RealtimeState.FAILED
        if state is MotionState.CLOSED:
            return RealtimeState.CLOSED
        return RealtimeState.MOTION

    @staticmethod
    def _realtime_error_for_motion_error(
        error_code: MotionErrorCode,
    ) -> RealtimeErrorCode:
        from .motion import MotionErrorCode

        if error_code is MotionErrorCode.NONE:
            return RealtimeErrorCode.NONE
        if error_code is MotionErrorCode.INTERRUPTED:
            return RealtimeErrorCode.INTERRUPTED
        if error_code is MotionErrorCode.SESSION_CLOSED:
            return RealtimeErrorCode.SESSION_CLOSED
        if error_code is MotionErrorCode.PROVIDER_ERROR:
            return RealtimeErrorCode.PROVIDER_ERROR
        if error_code in {MotionErrorCode.UNSUPPORTED, MotionErrorCode.NOT_IMPLEMENTED}:
            return RealtimeErrorCode.UNSUPPORTED
        if error_code in {
            MotionErrorCode.NOT_CONFIGURED,
            MotionErrorCode.TOKEN_MISSING,
            MotionErrorCode.RUNTIME_NOT_INSTALLED,
            MotionErrorCode.MODEL_NOT_SELECTED,
        }:
            return RealtimeErrorCode.CONFIGURATION_MISSING
        return RealtimeErrorCode.UNAVAILABLE

    def _emit_motion_lifecycle_event(
        self,
        event_type: RealtimeEventType,
        *,
        source_event: RealtimeEvent,
        request: MotionRequest,
        result: MotionResult | None = None,
    ) -> RealtimeEvent | None:
        """Emit one state-neutral motion event through the session sequencer."""

        from .motion import MotionRequest, MotionResult, MotionState

        if not isinstance(request, MotionRequest):
            raise TypeError("request must be a MotionRequest")
        if result is not None and not isinstance(result, MotionResult):
            raise TypeError("result must be a MotionResult or None")
        if self._closed or self._close_requested:
            return None

        motion_state = result.state if result is not None else MotionState.PREPARING
        realtime_state = self._realtime_state_for_motion_state(motion_state)
        error_code = (
            self._realtime_error_for_motion_error(result.public_error_code)
            if result is not None
            else RealtimeErrorCode.NONE
        )
        metadata = {
            "boundary": "motion",
            "source_event_type": source_event.type.value,
            "source_sequence": int(source_event.sequence),
            "lifecycle_triggered": True,
        }

        def event_factory(sequence: EventSequence) -> RealtimeEvent:
            return RealtimeEvent(
                type=event_type,
                state=realtime_state,
                previous_state=self._state,
                turn_id=request.turn_id,
                session_id=self._session_id,
                boundary="motion",
                public_error_code=error_code,
                safe_message=result.safe_message if result is not None else "",
                retryable=result.retryable if result is not None else False,
                public_metadata=metadata,
                sequence=sequence,
                generation_id=request.generation_id,
                phase=RealtimePhase.MOTION,
                payload=MotionEventPayload(
                    request_id=request.request_id,
                    outcome=result.outcome if result is not None else None,
                ),
                timestamp=time.time(),
                monotonic_timestamp=time.monotonic(),
            )

        def overflow_event_factory(
            sequence: EventSequence,
            dropped_sequence: EventSequence | None,
            overflow_count: int,
        ) -> RealtimeEvent:
            return RealtimeEvent(
                type=RealtimeEventType.EVENT_OVERFLOW,
                state=realtime_state,
                previous_state=self._state,
                turn_id=request.turn_id,
                session_id=self._session_id,
                boundary="motion",
                safe_message="Realtime motion event history overflowed.",
                public_metadata={"boundary": "motion"},
                sequence=sequence,
                generation_id=request.generation_id,
                phase=RealtimePhase.MOTION,
                payload=DiagnosticEventPayload(
                    code="motion_event_history_overflow",
                    drop_reason="history_limit",
                    dropped_sequence=dropped_sequence,
                    overflow_count=overflow_count,
                ),
                timestamp=time.time(),
                monotonic_timestamp=time.monotonic(),
            )

        try:
            with self._callback_delivery_window():
                return self._event_hub.emit(
                    event_factory,
                    legacy_projector=lambda emitted: emitted.to_v5(),
                    overflow_event_factory=overflow_event_factory,
                )
        except EventHubClosedError:
            return None

    def _motion_lifecycle_failure_result(
        self,
        *,
        request: MotionRequest,
        reason: str,
    ) -> MotionResult:
        from .motion import (
            MotionAdapterStatus,
            MotionErrorCode,
            MotionOutcome,
            MotionRequest,
            MotionResult,
            MotionState,
        )

        if not isinstance(request, MotionRequest):
            raise TypeError("request must be a MotionRequest")
        from .callback_isolation import criticality_for_stage, stage_failure_policy

        failure_policy = stage_failure_policy(criticality_for_stage("motion"))
        if reason == "stage_not_configured":
            outcome = MotionOutcome.NOT_CONFIGURED
            status = MotionAdapterStatus.NOT_CONFIGURED
            error_code = MotionErrorCode.NOT_CONFIGURED
            state = MotionState.UNAVAILABLE
            safe_message = "Realtime motion stage is not configured."
        elif reason == "stage_preflight_failed":
            outcome = MotionOutcome.UNAVAILABLE
            status = MotionAdapterStatus.DISABLED
            error_code = MotionErrorCode.UNAVAILABLE
            state = MotionState.UNAVAILABLE
            safe_message = "Realtime motion stage is unavailable."
        elif reason == "stale_generation":
            outcome = MotionOutcome.INTERRUPTED
            status = MotionAdapterStatus.CONFIGURED
            error_code = MotionErrorCode.INTERRUPTED
            state = MotionState.INTERRUPTED
            safe_message = "Stale realtime motion completion was dropped."
        else:
            outcome = MotionOutcome.FAILED
            status = MotionAdapterStatus.CONFIGURED
            error_code = MotionErrorCode.PROVIDER_ERROR
            state = MotionState.FAILED
            safe_message = "Realtime motion stage failed safely."

        return MotionResult(
            outcome=outcome,
            state=state,
            adapter_status=status,
            public_error_code=error_code,
            safe_message=safe_message,
            retryable=False,
            request_id=request.request_id,
            session_id=self._session_id,
            turn_id=request.turn_id,
            generation_id=request.generation_id,
            public_metadata={
                "boundary": "motion",
                "reason": reason,
                "conversation_terminal_changed": False,
                "stage_criticality": failure_policy.criticality.value,
                "failure_action": failure_policy.failure_action.value,
                "session_remains_open": failure_policy.session_remains_open,
                "runtime_remains_available": (
                    failure_policy.runtime_remains_available
                ),
            },
        )

    def _motion_lifecycle_terminal_source_is_current(
        self,
        notification: MotionLifecycleNotification,
    ) -> bool:
        record = self._terminal_registry.get(notification.turn_id)
        return record is not None and record.outcome is notification.outcome

    def _validated_motion_stage_result(
        self,
        *,
        envelope: object,
        context: object,
        request: MotionRequest,
    ) -> MotionResult | None:
        from .motion import MotionRequest, MotionResult
        from .realtime_stage import (
            RealtimeStageContext,
            RealtimeStageKind,
            RealtimeStageResultEnvelope,
        )

        if (
            not isinstance(request, MotionRequest)
            or not isinstance(context, RealtimeStageContext)
            or not isinstance(envelope, RealtimeStageResultEnvelope)
            or envelope.stage_kind is not RealtimeStageKind.MOTION
            or envelope.context != context
            or not isinstance(envelope.result, MotionResult)
        ):
            return None
        result = envelope.result
        if (
            not result.is_terminal
            or result.request_id != request.request_id
            or result.turn_id != request.turn_id
            or result.generation_id != request.generation_id
        ):
            return None
        return result

    def _begin_active_motion_work(
        self,
        *,
        stage: object,
        context: object,
        request: MotionRequest,
    ) -> _ActiveMotionWork | None:
        """Install the one pending/active motion owner for this session."""

        work = _ActiveMotionWork(
            stage=stage,
            context=context,
            request=request,
        )
        with self._motion_control_lock:
            if self._closed or self._close_requested:
                return None
            if self._active_motion_work is not None:
                return None
            self._active_motion_work = work
        return work

    def _complete_active_motion_work(self, work: _ActiveMotionWork) -> bool:
        """Clear one work item and return its one-way delivery barrier state."""

        with self._motion_control_lock:
            suppressed = work.future_delivery_suppressed
            if self._active_motion_work is work:
                self._active_motion_work = None
            work.completion_event.set()
        return suppressed

    def _execute_motion_lifecycle_request(
        self,
        *,
        source_event: RealtimeEvent,
        notification: MotionLifecycleNotification,
        request: MotionRequest,
    ) -> None:
        from .motion import MotionOutcome, MotionRequest, MotionResult
        from .realtime_generation_gate import RealtimeStageCompletionEnvelope
        from .realtime_stage import RealtimeStageContext

        if not isinstance(request, MotionRequest):
            return
        if self._closed or self._close_requested:
            return

        self._emit_motion_lifecycle_event(
            RealtimeEventType.MOTION_REQUESTED,
            source_event=source_event,
            request=request,
        )
        if self._closed or self._close_requested:
            return

        stage = self._injected_stages.get("motion")
        if stage is None:
            failure = self._motion_lifecycle_failure_result(
                request=request,
                reason="stage_not_configured",
            )
            self._emit_motion_lifecycle_event(
                RealtimeEventType.MOTION_FAILED,
                source_event=source_event,
                request=request,
                result=failure,
            )
            return
        if "motion" in self._stage_preflight_failed_kinds:
            failure = self._motion_lifecycle_failure_result(
                request=request,
                reason="stage_preflight_failed",
            )
            self._emit_motion_lifecycle_event(
                RealtimeEventType.MOTION_FAILED,
                source_event=source_event,
                request=request,
                result=failure,
            )
            return

        context = RealtimeStageContext(
            session_id=self._session_id,
            turn_id=notification.turn_id,
            generation_id=notification.generation_id,
            public_metadata={
                "boundary": "motion_lifecycle",
                "source_event_type": source_event.type.value,
                "source_sequence": int(source_event.sequence),
            },
        )
        work = self._begin_active_motion_work(
            stage=stage,
            context=context,
            request=request,
        )
        if work is None:
            failure = self._motion_lifecycle_failure_result(
                request=request,
                reason="stage_failed",
            )
            self._emit_motion_lifecycle_event(
                RealtimeEventType.MOTION_FAILED,
                source_event=source_event,
                request=request,
                result=failure,
            )
            return
        self._emit_motion_lifecycle_event(
            RealtimeEventType.MOTION_STARTED,
            source_event=source_event,
            request=request,
        )
        if self._closed or self._close_requested:
            self._complete_active_motion_work(work)
            return

        with self._motion_control_lock:
            pending_suppressed = work.future_delivery_suppressed
        if pending_suppressed:
            self._complete_active_motion_work(work)
            return

        try:
            raw_envelope = stage.start(context=context, request=request)
            result = self._validated_motion_stage_result(
                envelope=raw_envelope,
                context=context,
                request=request,
            )
        except Exception:
            result = None
        delivery_suppressed = self._complete_active_motion_work(work)
        if delivery_suppressed:
            return
        if result is None:
            result = self._motion_lifecycle_failure_result(
                request=request,
                reason="stage_failed",
            )
        if not isinstance(result, MotionResult):
            raise AssertionError("motion lifecycle execution must normalize a result")
        if self._closed or self._close_requested:
            return

        if source_event.type in _MOTION_LIFECYCLE_TERMINAL_SOURCE_TYPES:
            if not self._motion_lifecycle_terminal_source_is_current(notification):
                return
        else:
            completion = RealtimeStageCompletionEnvelope(
                turn_id=notification.turn_id,
                generation_id=notification.generation_id,
                stage="motion_completion",
                value=result,
            )
            applied_results: list[MotionResult] = []
            decision = self._apply_stage_completion(
                completion,
                deliver=applied_results.append,
            )
            if not decision.accepted:
                result = self._motion_lifecycle_failure_result(
                    request=request,
                    reason="stale_generation",
                )
                if self._closed or self._close_requested:
                    return
            else:
                result = applied_results[0]

        result_event_type = (
            RealtimeEventType.MOTION_COMPLETED
            if result.outcome is MotionOutcome.COMPLETED
            else RealtimeEventType.MOTION_FAILED
        )
        self._emit_motion_lifecycle_event(
            result_event_type,
            source_event=source_event,
            request=request,
            result=result,
        )

    def _handle_motion_lifecycle_event(self, event: RealtimeEvent) -> None:
        """Run the optional hook only after its canonical source event publishes."""

        mapping = _MOTION_LIFECYCLE_SOURCE_SIGNALS.get(event.type)
        hook = self._motion_lifecycle_hook
        if (
            mapping is None
            or hook is None
            or self._closed
            or self._close_requested
            or event.turn_id is None
            or event.generation_id is None
            or event.sequence is None
        ):
            return

        from .motion_lifecycle import (
            MotionLifecycleHookOutcome,
            MotionLifecycleNotification,
            invoke_motion_lifecycle_hook,
        )

        signal, outcome = mapping
        try:
            notification = MotionLifecycleNotification(
                signal=signal,
                session_id=self._session_id,
                turn_id=event.turn_id,
                generation_id=event.generation_id,
                source_sequence=event.sequence,
                outcome=outcome,
                public_metadata={
                    "boundary": "motion_lifecycle",
                    "source_event_type": event.type.value,
                },
            )
            hook_result = invoke_motion_lifecycle_hook(hook, notification)
        except Exception:
            return
        if (
            hook_result.outcome is not MotionLifecycleHookOutcome.MAPPED
            or hook_result.request is None
            or self._closed
            or self._close_requested
        ):
            return
        self._execute_motion_lifecycle_request(
            source_event=event,
            notification=notification,
            request=hook_result.request,
        )

    def decide_barge_in(
        self,
        *,
        turn_id: TurnId | str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> BargeInDecision:
        with self._serialized_operation():
            if self._closed or self._close_requested:
                return BargeInDecision.rejected(policy=self._barge_in_policy)
            return self._decide_barge_in_serialized(
                turn_id=turn_id,
                public_metadata=public_metadata,
            )

    def _decide_barge_in_serialized(
        self,
        *,
        turn_id: TurnId | str | None = None,
        public_metadata: Mapping[str, Any] | None = None,
    ) -> BargeInDecision:
        """Return a provider-neutral public barge-in decision."""

        resolved_turn_id = turn_id or self._active_turn_id
        try:
            self._transition(
                RealtimeEventType.BARGE_IN_DETECTED,
                self._state,
                turn_id=resolved_turn_id,
                payload=InterruptEventPayload(
                    scope=InterruptScope.ALL,
                    outcome=(
                        "unsupported"
                        if self._barge_in_policy.mode is BargeInPolicyMode.DISABLED
                        else "accepted"
                    ),
                    reason="barge_in_detected",
                ),
                public_metadata={
                    "policy_mode": self._barge_in_policy.mode.value,
                    **dict(public_metadata or {}),
                },
            )

            if self._barge_in_policy.mode is BargeInPolicyMode.DISABLED:
                decision = BargeInDecision.rejected(policy=self._barge_in_policy)
                self._transition(
                    RealtimeEventType.BARGE_IN_REJECTED,
                    self._state,
                    turn_id=resolved_turn_id,
                    payload=InterruptEventPayload(
                        scope=InterruptScope.ALL,
                        outcome="unsupported",
                        reason="barge_in_rejected",
                    ),
                    safe_message=decision.safe_message,
                    public_metadata={"policy_mode": self._barge_in_policy.mode.value},
                )
                return decision

            decision = BargeInDecision.accepted_for_policy(
                self._barge_in_policy,
                turn_id=resolved_turn_id,
                public_metadata=public_metadata or {},
            )
            self._transition(
                RealtimeEventType.BARGE_IN_ACCEPTED,
                self._state,
                turn_id=resolved_turn_id,
                payload=InterruptEventPayload(
                    scope=InterruptScope.ALL,
                    outcome="accepted",
                    reason="barge_in_accepted",
                ),
                safe_message=decision.safe_message,
                public_metadata={
                    "policy_mode": self._barge_in_policy.mode.value,
                    "should_flush_queue": decision.should_flush_queue,
                    "should_cancel_current_turn": decision.should_cancel_current_turn,
                },
            )
            return decision
        except _LateNonTerminalRejected:
            return BargeInDecision.rejected(
                policy=self._barge_in_policy,
                safe_message="Realtime turn is already terminal.",
            )

    def execute_barge_in(self, plan: BargeInControlPlan) -> InterruptResult:
        """Execute one accepted control plan through the interrupt owner.

        Detection and policy decision remain host-owned and separate.  This
        method neither rebuilds nor broadens the plan: an executing plan's
        exact ``coordinator_request`` is handed to the accepted ordered
        interrupt path, while a non-executing plan returns a typed unsupported
        result without emitting interrupt effects.
        """

        from .barge_in_control import BargeInControlPlan

        if not isinstance(plan, BargeInControlPlan):
            raise TypeError("plan must be a BargeInControlPlan")

        capabilities = self._capability_snapshot
        if (
            plan.provider_hard_cancel_supported
            is not capabilities.hard_cancel_supported
            or plan.queue_flush_supported
            is not capabilities.tts_queue_flush_supported
        ):
            raise ValueError(
                "barge-in plan capabilities must match the executing session"
            )

        request = plan.coordinator_request
        if request is not None:
            return self._ordered_interrupt(request, advance_reason="interrupt")

        result_request = plan.decision.interrupt_request or InterruptRequest(
            scope=plan.decision.policy.interrupt_scope,
            reason=InterruptReason.USER_BARGE_IN,
            public_metadata={
                "boundary": "barge_in_execution",
                "requested_policy_mode": plan.requested_mode.value,
                "effective_policy_mode": plan.effective_mode.value,
                "capability_downgraded": plan.capability_downgraded,
            },
        )
        if self._closed or self._close_requested:
            return InterruptResult.already_closed(request=result_request)
        return InterruptResult(
            outcome=InterruptOutcome.UNSUPPORTED,
            scope=result_request.scope,
            reason=result_request.reason,
            turn_id=result_request.turn_id,
            safe_message=(
                "Barge-in control plan has no supported interrupt execution."
            ),
            retryable=False,
            provider_cancel_supported=plan.provider_hard_cancel_supported,
            queue_flush_supported=plan.queue_flush_supported,
            public_metadata={
                "boundary": "barge_in_execution",
                "requested_policy_mode": plan.requested_mode.value,
                "effective_policy_mode": plan.effective_mode.value,
                "capability_downgraded": plan.capability_downgraded,
                "delegated_to_interrupt_coordinator": False,
                "microphone_detection_required": False,
            },
        )

    def _reset_has_active_operation(self) -> bool:
        """Return whether a reset would collide with in-flight stage control."""

        with self._interrupt_request_lock:
            interrupt_work = self._active_interrupt_request
            if (
                interrupt_work is not None
                and not interrupt_work.completion_event.is_set()
            ):
                return True
        with self._interrupt_stage_lock:
            if self._active_interrupt_stage_work:
                return True
        with self._motion_control_lock:
            return self._active_motion_work is not None

    def reset(self, plan: RecoveryControlPlan) -> RecoveryResetResult:
        """Execute one explicit recovery plan through the generation owner.

        Planning and execution remain separate.  Non-reset dispositions are
        projected to their typed result without side effects.  A reset reuses
        the session's sole ``RealtimeGenerationGate`` to retire the previous
        generation and reserve one distinct replacement.  If the turn remains
        active, the replacement is immediately rebound to that exact turn;
        otherwise the next admitted turn consumes the reserved generation.

        Provider/network work is never performed here.  In-flight stage or
        interrupt ownership is rejected as a typed retryable conflict rather
        than being raced or silently reinterpreted.
        """

        from .recovery_control import (
            RecoveryControlPlan,
            RecoveryResetErrorCode,
            RecoveryResetResult,
        )

        if not isinstance(plan, RecoveryControlPlan):
            raise TypeError("plan must be a RecoveryControlPlan")
        if not plan.execute_reset:
            return RecoveryResetResult.for_non_reset_plan(plan)

        with self._serialized_operation():
            with self._turn_admission_lock:
                with self._interrupt_request_lock:
                    close_admitted = self._close_admission_requested
                if self._closed or self._close_requested or close_admitted:
                    return RecoveryResetResult.failed(
                        plan,
                        error_code=RecoveryResetErrorCode.SESSION_CLOSED,
                        safe_message="Realtime session is closed.",
                    )
                if self._reset_has_active_operation():
                    return RecoveryResetResult.failed(
                        plan,
                        error_code=RecoveryResetErrorCode.ACTIVE_OPERATION,
                        safe_message=(
                            "Realtime reset cannot run while stage control is active."
                        ),
                        retryable=True,
                    )

                active_turn_id = self._generation_gate.current_turn_id
                active_generation_id = self._generation_gate.current_generation_id
                context = self._active_turn_context
                if context is not None and active_generation_id is not None:
                    if (
                        context.turn_id != active_turn_id
                        or context.generation_id != active_generation_id
                    ):
                        return RecoveryResetResult.failed(
                            plan,
                            error_code=(
                                RecoveryResetErrorCode.GENERATION_MISMATCH
                            ),
                            safe_message=(
                                "Realtime reset generation context does not match."
                            ),
                        )

                reset_generations = self._generation_gate.reset_generation()
                if reset_generations is None:
                    return RecoveryResetResult.failed(
                        plan,
                        error_code=RecoveryResetErrorCode.GENERATION_MISMATCH,
                        safe_message=(
                            "Realtime reset requires a previous generation."
                        ),
                    )
                previous_generation_id, replacement_generation_id = (
                    reset_generations
                )

                reusable_turn = (
                    active_turn_id is not None
                    and active_generation_id == previous_generation_id
                    and self._terminal_registry.get(active_turn_id) is None
                )
                if reusable_turn:
                    current_generation_id = self._generation_gate.start_generation(
                        active_turn_id
                    )
                    if current_generation_id != replacement_generation_id:
                        raise AssertionError(
                            "reset replacement generation must be reused exactly"
                        )
                    if context is not None and context.turn_id == active_turn_id:
                        self._bind_active_turn_context(
                            context.turn,
                            current_generation_id,
                        )
                    else:
                        self._active_turn_id = active_turn_id
                        self._active_generation_id = current_generation_id
                else:
                    current_generation_id = replacement_generation_id
                    self._clear_active_turn_context()

                for registry in (
                    self._host_playback_stop_requests,
                    self._host_playback_stop_acknowledgements,
                ):
                    for key in tuple(registry):
                        if key[1] == previous_generation_id:
                            del registry[key]

                self._state = RealtimeState.IDLE
                self._phase = RealtimePhase.IDLE
                return RecoveryResetResult.applied(
                    plan,
                    previous_generation_id=previous_generation_id,
                    current_generation_id=current_generation_id,
                )

    def _close_injected_stages(
        self,
        *,
        timeout_seconds: float,
    ) -> SessionCleanupResult:
        from .session_close import (
            SessionCleanupResult,
            SessionCleanupTarget,
            _run_bounded_cleanup_operations,
        )

        if self._injected_stages_closed:
            return SessionCleanupResult.already_closed(
                SessionCleanupTarget.STAGE
            )
        self._injected_stages_closed = True
        result, completed_count, error_count = _run_bounded_cleanup_operations(
            (stage.close for stage in self._injected_stages.values()),
            timeout_seconds=timeout_seconds,
            target=SessionCleanupTarget.STAGE,
            timeout_message="Realtime stage cleanup timed out.",
            failure_message="Realtime stage cleanup failed.",
        )
        self._stage_close_count += completed_count
        self._stage_close_error_count += error_count
        return result

    def _set_already_closed_result(self) -> None:
        """Record one repeated close without re-running cleanup or events."""

        from .session_close import SessionCloseResult

        with self._operation_lock:
            if self._closed:
                if not self._close_finalized.is_set():
                    self._duplicate_close_requested = True
                else:
                    self._last_close_result = SessionCloseResult.already_closed(
                        public_metadata={"boundary": "realtime"}
                    )

    def _finalize_close_result(self) -> None:
        """Stop the bridge after unlock, then publish the complete typed result."""

        from .session_close import (
            SessionCleanupResult,
            SessionCleanupTarget,
            SessionCloseResult,
            _runtime_close_result,
        )

        pending = self._pending_close_result
        if pending is None:
            return
        plan, observed, active_turn_terminalized = pending
        if plan.execution_bridge_shutdown_required:
            bridge_stopped = self._execution_bridge.shutdown(
                timeout_seconds=plan.bridge_shutdown_timeout_seconds
            )
            observed[SessionCleanupTarget.EXECUTION_BRIDGE] = (
                SessionCleanupResult.completed(
                    SessionCleanupTarget.EXECUTION_BRIDGE
                )
                if bridge_stopped
                else SessionCleanupResult.timed_out_result(
                    SessionCleanupTarget.EXECUTION_BRIDGE,
                    safe_message="Realtime execution bridge shutdown timed out.",
                )
            )
        first_result = _runtime_close_result(
            plan,
            observed=observed,
            active_turn_terminalized=active_turn_terminalized,
            public_metadata={"boundary": "realtime"},
        )
        self._last_close_result = (
            SessionCloseResult.already_closed(
                public_metadata={"boundary": "realtime"}
            )
            if self._duplicate_close_requested
            else first_result
        )
        self._pending_close_result = None
        self._close_finalized.set()

    def close(self) -> None:
        from .session_close import SessionCloseResult

        while True:
            with self._interrupt_request_lock:
                if (
                    self._closed
                    or self._close_requested
                    or (
                        self._close_admission_requested
                        and self._active_interrupt_request is None
                    )
                ):
                    duplicate = self._closed
                    if duplicate:
                        if self._close_finalized.is_set():
                            self._last_close_result = (
                                SessionCloseResult.already_closed(
                                    public_metadata={"boundary": "realtime"}
                                )
                            )
                        else:
                            self._duplicate_close_requested = True
                    return
                interrupt_work = self._active_interrupt_request
                if (
                    interrupt_work is not None
                    and not interrupt_work.completion_event.is_set()
                ):
                    if interrupt_work.owner_thread_id == get_ident():
                        interrupt_work.close_after_completion = True
                        return
                    wait_for_interrupt = interrupt_work.completion_event
                else:
                    self._close_admission_requested = True
                    break
            wait_for_interrupt.wait()

        with self._motion_control_lock:
            active_motion = self._active_motion_work
            active_motion_turn_id = (
                getattr(active_motion.request, "turn_id", None)
                if active_motion is not None
                else None
            )
        if active_motion is not None:
            self._request_motion_control(
                InterruptRequest(
                    scope=InterruptScope.MOTION,
                    reason=InterruptReason.SESSION_CLOSED,
                    turn_id=active_motion_turn_id,
                )
            )

        should_shutdown_bridge = False
        with self._operation_lock:
            if self._closed or self._close_requested:
                if self._closed:
                    self._set_already_closed_result()
                return
            if self._operation_depth > 0:
                self._close_requested = True
                return
            self._close_now()
            should_shutdown_bridge = True

        if should_shutdown_bridge:
            self._finalize_close_result()

    def _close_now(self) -> None:
        if self._closed:
            return
        from .session_close import (
            SessionCleanupResult,
            SessionCleanupTarget,
            build_session_close_plan,
        )

        active_turn_id = self._active_turn_id
        active_generation_id = self._active_generation_id
        active_turn_terminal_required = (
            active_turn_id is not None
            and self._terminal_registry.get(active_turn_id) is None
        )
        plan = build_session_close_plan(
            active_turn_terminal_required=active_turn_terminal_required,
            stage_cleanup_required=bool(self._injected_stages),
            callback_hub_close_required=True,
            execution_bridge_shutdown_required=True,
            stage_cleanup_timeout_seconds=_SESSION_CLOSE_TIMEOUT_SECONDS,
            bridge_shutdown_timeout_seconds=_SESSION_CLOSE_TIMEOUT_SECONDS,
            public_metadata={"boundary": "realtime"},
        )
        observed: dict[SessionCleanupTarget, SessionCleanupResult] = {}
        active_turn_terminalized = False

        self._close_requested = False
        self._closed = True
        self._motion_lifecycle_hook = None
        if active_turn_terminal_required:
            terminal = RealtimeTurnResult.closed(
                turn_id=active_turn_id,
                session_id=self._session_id,
                generation_id=active_generation_id,
                public_metadata={
                    "boundary": "realtime",
                    "reason": "session_closed",
                },
            )
            decision = self._terminal_registry.commit(
                active_turn_id,
                terminal.outcome,
                recovery_action=terminal.recovery_action,
                reason="session_closed",
                result=terminal,
            )
            active_turn_terminalized = decision.accepted
            if not active_turn_terminalized:
                raise AssertionError("active realtime turn must close exactly once")
            observed[SessionCleanupTarget.ACTIVE_TURN] = (
                SessionCleanupResult.completed(SessionCleanupTarget.ACTIVE_TURN)
            )

        self._advance_generation("session_closed", turn_id=active_turn_id)
        self._clear_active_turn_context()
        self._phase = None
        if plan.stage_cleanup_required:
            observed[SessionCleanupTarget.STAGE] = self._close_injected_stages(
                timeout_seconds=plan.stage_cleanup_timeout_seconds
            )
        callback_errors_before = self._event_hub.diagnostics.callback_error_count
        try:
            self._transition(
                RealtimeEventType.SESSION_CLOSED,
                RealtimeState.CLOSED,
                turn_id=active_turn_id,
                payload=LifecycleEventPayload(
                    outcome=TurnOutcome.CLOSED,
                    recovery_action=RecoveryAction.NONE,
                    reason="session_closed",
                ),
                public_metadata={"reason": "session_closed"},
                _allow_closed_event=True,
                _event_generation_id=active_generation_id,
            )
        finally:
            callback_closed = self._event_hub.close()
            callback_failed = (
                self._event_hub.diagnostics.callback_error_count
                > callback_errors_before
            )
            if callback_failed:
                observed[SessionCleanupTarget.CALLBACK_HUB] = (
                    SessionCleanupResult.failed_result(
                        SessionCleanupTarget.CALLBACK_HUB,
                        safe_message="Realtime callback cleanup failed.",
                    )
                )
            else:
                observed[SessionCleanupTarget.CALLBACK_HUB] = (
                    SessionCleanupResult.completed(
                        SessionCleanupTarget.CALLBACK_HUB
                    )
                    if callback_closed
                    else SessionCleanupResult.already_closed(
                        SessionCleanupTarget.CALLBACK_HUB
                    )
                )
        self._pending_close_result = (
            plan,
            observed,
            active_turn_terminalized,
        )
        if not plan.execution_bridge_shutdown_required:
            self._finalize_close_result()

    def dispose(self) -> None:
        self.close()

    def __enter__(self) -> "RealtimeSession":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def create_realtime_session(
    *,
    project_root: str | Path | None = None,
    public_metadata: Mapping[str, Any] | None = None,
    real_runtime_enabled: bool | None = None,
    voice_input_stage: VoiceInputStage | None = None,
    text_generation_stage: TextGenerationStage | None = None,
    voice_output_stage: VoiceOutputStage | None = None,
    motion_stage: MotionStage | None = None,
    config: RealtimeSessionConfig | None = None,
) -> RealtimeSession:
    """Create one provider-neutral realtime session composition root.

    Construction may call supplied stage ``preflight()`` methods, but does not
    call stage execution, cancellation, capability refresh, or provider runtime
    operations. Real orchestration remains a later control.
    """

    return RealtimeSession(
        project_root=project_root,
        public_metadata=public_metadata,
        real_runtime_enabled=real_runtime_enabled,
        voice_input_stage=voice_input_stage,
        text_generation_stage=text_generation_stage,
        voice_output_stage=voice_output_stage,
        motion_stage=motion_stage,
        config=config,
    )
