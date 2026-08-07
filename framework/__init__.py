"""Public facade API for AI Character Framework."""

from __future__ import annotations

from .audio.voice_output import VoiceArtifactRef
from .capabilities import CapabilityStatus, FrameworkCapabilities, get_capabilities
from .identity import EventSequence, GenerationId, SessionId, TurnId
from .lifecycle import (
    LifecycleTransitionError,
    LifecycleTransitionErrorCode,
    RealtimePhase,
    RecoveryAction,
    TurnOutcome,
)
from .facade import (
    FacadeConfigError,
    FacadeError,
    FacadeProviderError,
    TextChatSession,
    TextChatSessionEvent,
    TextChatSessionInfo,
    TextChatStateChange,
    VoiceOutputRequest,
    VoiceOutputResult,
    VoiceOutputSession,
    VoiceOutputSessionInfo,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
    create_text_chat_session,
    create_voice_output_session,
)
from .motion import (
    MotionAdapterStatus,
    MotionCapability,
    MotionErrorCode,
    MotionEventType,
    MotionIntent,
    MotionOutcome,
    MotionRequest,
    MotionResult,
    MotionState,
)
from .motion_adapter_execution import (
    MotionAdapterExecutionConfig,
    get_motion_adapter_execution_capability,
    resolve_motion_adapter_execution_config,
)
from .motion_session import MotionSession, MotionSessionInfo, create_motion_session
from .output_control import (
    BargeInDecision,
    BargeInPolicy,
    BargeInPolicyMode,
    InterruptOutcome,
    InterruptReason,
    InterruptRequest,
    InterruptResult,
    InterruptScope,
    OutputFlushOutcome,
    OutputFlushRequest,
    OutputFlushResult,
    TTSQueueState,
)
from .public_api import (
    PROVIDER_COMPAT_LAZY_EXPORT_MODULES,
    PUBLIC_API_NAMES,
)
from .realtime import (
    RealtimeErrorCode,
    RealtimeEvent,
    RealtimeEventType,
    RealtimeState,
    RealtimeTurn,
    RealtimeTurnResult,
)
from .realtime_capabilities import (
    CapabilitySnapshotScope,
    RealtimeCapabilitySnapshot,
    RealtimeMotionCapability,
    RealtimeVoiceInputCapability,
    RealtimeVoiceOutputCapability,
    RuntimeCapabilityState,
    TextGenerationCapability,
)
from .realtime_event_payloads import (
    AudioEventPayload,
    DiagnosticEventPayload,
    InterruptEventPayload,
    LifecycleEventPayload,
    MotionEventPayload,
    RealtimeEventPayload,
    RealtimeEventPayloadKind,
    ResponseEventPayload,
    SynthesisEventPayload,
    TranscriptEventPayload,
)
from .realtime_session import RealtimeSession, RealtimeSessionInfo, create_realtime_session
from .realtime_session_config import (
    RealtimeSessionConfig,
    RealtimeSessionConstructionResult,
    RealtimeSessionConstructionStatus,
)
from .text_chat_result import TextChatResult
from .voice_input import (
    VoiceInputErrorCode,
    VoiceInputOutcome,
    VoiceInputRequest,
    VoiceInputResult,
)
from .voice_input_audio import (
    VoiceInputAudioEncoding,
    VoiceInputAudioFormat,
    VoiceInputAudioRef,
    VoiceInputAudioSource,
    VoiceInputAudioSourceKind,
)
from .voice_input_capability import (
    VoiceInputCapabilities,
    VoiceInputProviderConfig,
    VoiceInputProviderStatus,
    get_voice_input_capabilities,
    resolve_voice_input_provider_config,
)
from .voice_input_provider_adapter import (
    FakeVoiceInputProviderAdapter,
    GuardedRealVoiceInputProviderAdapter,
    VoiceInputProviderAdapter,
    VoiceInputProviderAdapterInfo,
)
from .voice_input_provider_execution import (
    VoiceInputProviderExecutionConfig,
    get_voice_input_provider_execution_status,
    resolve_voice_input_provider_execution_config,
)
from .voice_input_session import (
    VoiceInputSession,
    VoiceInputSessionInfo,
    create_voice_input_session,
)
from .version import FRAMEWORK_SOURCE_VERSION

__version__ = FRAMEWORK_SOURCE_VERSION

# One canonical, ordered source controls the root-public wildcard surface.
__all__ = list(PUBLIC_API_NAMES)


def __getattr__(name: str):
    """Resolve frozen provider-specific compatibility exports lazily."""

    module_name = PROVIDER_COMPAT_LAZY_EXPORT_MODULES.get(name)
    if module_name is not None:
        from importlib import import_module

        module = import_module(module_name, __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
