"""Canonical root-public API manifest.

This module contains names and lazy-module strings only. Importing it must not
import provider SDKs, runtime orchestration, audio playback, microphone, motion
transport, or application-specific modules.
"""

from __future__ import annotations

from types import MappingProxyType

# v5.4 provider-specific names remain root-public compatibility exports.
# They are resolved lazily by ``framework.__getattr__`` and must not cause
# provider SDK imports during ``import framework``.
PROVIDER_COMPAT_LAZY_EXPORT_MODULES = MappingProxyType(
    {
        "OpenAIVoiceInputClient": ".openai_voice_input_provider_adapter",
        "OpenAIVoiceInputClientFactory": ".openai_voice_input_provider_adapter",
        "OpenAIVoiceInputPreflight": ".openai_voice_input_provider_adapter",
        "OpenAIVoiceInputPreflightStatus": ".openai_voice_input_provider_adapter",
        "OpenAIVoiceInputProviderAdapter": ".openai_voice_input_provider_adapter",
        "OpenAIVoiceInputFakeClientMarker": ".openai_voice_input_fake_execution",
        "OpenAIVoiceInputFakeExecutionPolicy": ".openai_voice_input_fake_execution",
        "OpenAIVoiceInputFakeExecutionStatus": ".openai_voice_input_fake_execution",
        "OpenAIVoiceInputFakeExecutor": ".openai_voice_input_fake_execution",
        "OpenAIVoiceInputPrivateCredential": ".openai_voice_input_real_provider",
        "OpenAIVoiceInputRealClientFactory": ".openai_voice_input_real_provider",
        "OpenAIVoiceInputRealProviderExecutor": ".openai_voice_input_real_provider",
        "OpenAIVoiceInputRealProviderPolicy": ".openai_voice_input_real_provider",
        "OpenAIVoiceInputRealProviderStatus": ".openai_voice_input_real_provider",
        "OpenAIVoiceInputRuntimeMode": ".openai_voice_input_real_provider",
    }
)
PROVIDER_COMPAT_LAZY_EXPORTS = tuple(PROVIDER_COMPAT_LAZY_EXPORT_MODULES)

VOICE_INPUT_PROVIDER_PUBLIC_EXPORTS = (
    "VoiceInputProviderExecutionConfig",
    "resolve_voice_input_provider_execution_config",
    "get_voice_input_provider_execution_status",
    "GuardedRealVoiceInputProviderAdapter",
    "VoiceInputProviderAdapterInfo",
    "VoiceInputProviderAdapter",
    "FakeVoiceInputProviderAdapter",
    "VoiceInputAudioSourceKind",
    "VoiceInputAudioSource",
    "VoiceInputAudioRef",
    "VoiceInputAudioFormat",
    "VoiceInputAudioEncoding",
)

FACADE_PUBLIC_EXPORTS = (
    "FacadeConfigError",
    "FacadeError",
    "FacadeProviderError",
    "TextChatSession",
    "TextChatSessionEvent",
    "TextChatSessionInfo",
    "TextChatStateChange",
    "VoiceOutputRequest",
    "VoiceArtifactRef",
    "VoiceOutputResult",
    "VoiceOutputSession",
    "VoiceOutputSessionInfo",
    "VoiceSynthesisRequest",
    "VoiceSynthesisResult",
    "create_text_chat_session",
    "create_voice_output_session",
    "TextChatResult",
    "CapabilityStatus",
    "FrameworkCapabilities",
    "get_capabilities",
)

VOICE_INPUT_CONTRACT_EXPORTS = (
    "VoiceInputErrorCode",
    "VoiceInputOutcome",
    "VoiceInputRequest",
    "VoiceInputResult",
)

VOICE_INPUT_SESSION_EXPORTS = (
    "VoiceInputSession",
    "VoiceInputSessionInfo",
    "create_voice_input_session",
)

VOICE_INPUT_CAPABILITY_EXPORTS = (
    "VoiceInputCapabilities",
    "VoiceInputProviderConfig",
    "VoiceInputProviderStatus",
    "get_voice_input_capabilities",
    "resolve_voice_input_provider_config",
)

REALTIME_MODEL_EXPORTS = (
    "RealtimeErrorCode",
    "RealtimeEvent",
    "RealtimeEventType",
    "RealtimeState",
    "RealtimeTurn",
    "RealtimeTurnResult",
)

REALTIME_SESSION_EXPORTS = (
    "RealtimeSession",
    "RealtimeSessionInfo",
    "create_realtime_session",
)

OUTPUT_CONTROL_EXPORTS = (
    "BargeInDecision",
    "BargeInPolicy",
    "BargeInPolicyMode",
    "InterruptOutcome",
    "InterruptReason",
    "InterruptRequest",
    "InterruptResult",
    "InterruptScope",
    "OutputFlushOutcome",
    "OutputFlushRequest",
    "OutputFlushResult",
    "TTSQueueState",
)

MOTION_MODEL_EXPORTS = (
    "MotionAdapterStatus",
    "MotionCapability",
    "MotionErrorCode",
    "MotionEventType",
    "MotionIntent",
    "MotionOutcome",
    "MotionRequest",
    "MotionResult",
    "MotionState",
)

MOTION_SESSION_EXPORTS = (
    "MotionSession",
    "MotionSessionInfo",
    "create_motion_session",
)

MOTION_ADAPTER_EXECUTION_EXPORTS = (
    "MotionAdapterExecutionConfig",
    "get_motion_adapter_execution_capability",
    "resolve_motion_adapter_execution_config",
)

IDENTITY_PUBLIC_EXPORTS = (
    "SessionId",
    "TurnId",
    "GenerationId",
    "EventSequence",
)

LIFECYCLE_PUBLIC_EXPORTS = (
    "RealtimePhase",
    "TurnOutcome",
    "RecoveryAction",
    "LifecycleTransitionErrorCode",
    "LifecycleTransitionError",
)

REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS = (
    "RealtimeEventPayloadKind",
    "LifecycleEventPayload",
    "TranscriptEventPayload",
    "ResponseEventPayload",
    "SynthesisEventPayload",
    "AudioEventPayload",
    "MotionEventPayload",
    "InterruptEventPayload",
    "DiagnosticEventPayload",
    "RealtimeEventPayload",
)

REALTIME_CAPABILITY_PUBLIC_EXPORTS = (
    "CapabilitySnapshotScope",
    "RuntimeCapabilityState",
    "TextGenerationCapability",
    "RealtimeVoiceInputCapability",
    "RealtimeVoiceOutputCapability",
    "RealtimeMotionCapability",
    "RealtimeCapabilitySnapshot",
)

REALTIME_SESSION_CONSTRUCTION_PUBLIC_EXPORTS = (
    "RealtimeSessionConfig",
    "RealtimeSessionConstructionStatus",
    "RealtimeSessionConstructionResult",
)

REALTIME_TURN_START_PUBLIC_EXPORTS = (
    "RealtimeTurnStartResult",
)

REALTIME_EXECUTION_PUBLIC_EXPORTS = (
    "RealtimeExecutionErrorCode",
    "RealtimeExecutionError",
)

PUBLIC_API_GROUPS = MappingProxyType(
    {
        "provider_compat_lazy": PROVIDER_COMPAT_LAZY_EXPORTS,
        "voice_input_provider": VOICE_INPUT_PROVIDER_PUBLIC_EXPORTS,
        "facade": FACADE_PUBLIC_EXPORTS,
        "voice_input_contract": VOICE_INPUT_CONTRACT_EXPORTS,
        "voice_input_session": VOICE_INPUT_SESSION_EXPORTS,
        "voice_input_capability": VOICE_INPUT_CAPABILITY_EXPORTS,
        "realtime_models": REALTIME_MODEL_EXPORTS,
        "realtime_session": REALTIME_SESSION_EXPORTS,
        "output_control": OUTPUT_CONTROL_EXPORTS,
        "motion_models": MOTION_MODEL_EXPORTS,
        "motion_session": MOTION_SESSION_EXPORTS,
        "motion_adapter_execution": MOTION_ADAPTER_EXECUTION_EXPORTS,
        "identity": IDENTITY_PUBLIC_EXPORTS,
        "lifecycle": LIFECYCLE_PUBLIC_EXPORTS,
        "realtime_event_payloads": REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS,
        "realtime_capabilities": REALTIME_CAPABILITY_PUBLIC_EXPORTS,
        "realtime_session_construction": REALTIME_SESSION_CONSTRUCTION_PUBLIC_EXPORTS,
        "realtime_turn_start": REALTIME_TURN_START_PUBLIC_EXPORTS,
        "realtime_execution": REALTIME_EXECUTION_PUBLIC_EXPORTS,
    }
)

PUBLIC_API_NAMES = tuple(
    name
    for names in PUBLIC_API_GROUPS.values()
    for name in names
)

if len(PUBLIC_API_NAMES) != len(set(PUBLIC_API_NAMES)):
    raise RuntimeError("Canonical framework public API manifest contains duplicate names.")


# FW-RT6-11b freezes the v6 root-public contract as an unordered name set.
# ``PUBLIC_API_NAMES`` keeps its historical ordering so existing wildcard-import
# behavior does not change, but consumers and new conformance gates must compare
# the canonical sorted views below rather than positional slices.
ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION = "v6.root_public_api_manifest"
ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT = "non_contractual"

V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS = tuple(
    sorted(PROVIDER_COMPAT_LAZY_EXPORTS)
)
V6_ROOT_PUBLIC_EXPORTS = tuple(sorted(PUBLIC_API_NAMES))
V6_PROVIDER_NEUTRAL_ROOT_EXPORTS = tuple(
    name
    for name in V6_ROOT_PUBLIC_EXPORTS
    if name not in PROVIDER_COMPAT_LAZY_EXPORT_MODULES
)

if len(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS) != 15:
    raise RuntimeError("Expected 15 frozen v5 provider compatibility exports.")
if len(V6_ROOT_PUBLIC_EXPORTS) != 127:
    raise RuntimeError("Expected 127 frozen v6 root-public exports.")
if len(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS) != 112:
    raise RuntimeError("Expected 112 provider-neutral v6 root-public exports.")
