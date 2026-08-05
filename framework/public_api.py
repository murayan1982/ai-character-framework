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
    }
)

PUBLIC_API_NAMES = tuple(
    name
    for names in PUBLIC_API_GROUPS.values()
    for name in names
)

if len(PUBLIC_API_NAMES) != len(set(PUBLIC_API_NAMES)):
    raise RuntimeError("Canonical framework public API manifest contains duplicate names.")
