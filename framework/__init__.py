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
from .voice_input_audio import (
    VoiceInputAudioEncoding,
    VoiceInputAudioFormat,
    VoiceInputAudioRef,
    VoiceInputAudioSource,
    VoiceInputAudioSourceKind,
)
"""Public facade API for AI Character Framework."""

from framework.facade import (
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
from framework.audio.voice_output import VoiceArtifactRef
from .text_chat_result import TextChatResult
from .capabilities import CapabilityStatus, FrameworkCapabilities, get_capabilities

__all__ = [
    "OpenAIVoiceInputClient",
    "OpenAIVoiceInputClientFactory",
    "OpenAIVoiceInputPreflight",
    "OpenAIVoiceInputPreflightStatus",
    "OpenAIVoiceInputProviderAdapter",
    "OpenAIVoiceInputFakeClientMarker",
    "OpenAIVoiceInputFakeExecutionPolicy",
    "OpenAIVoiceInputFakeExecutionStatus",
    "OpenAIVoiceInputFakeExecutor",
    "OpenAIVoiceInputPrivateCredential",
    "OpenAIVoiceInputRealClientFactory",
    "OpenAIVoiceInputRealProviderExecutor",
    "OpenAIVoiceInputRealProviderPolicy",
    "OpenAIVoiceInputRealProviderStatus",
    "OpenAIVoiceInputRuntimeMode",
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
]

from .voice_input import VoiceInputErrorCode, VoiceInputOutcome, VoiceInputRequest, VoiceInputResult

# v5.2.0 public voice-input / STT contract exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['VoiceInputErrorCode', 'VoiceInputOutcome', 'VoiceInputRequest', 'VoiceInputResult']:
    if _name not in __all__:
        __all__.append(_name)
del _name

from .voice_input_session import VoiceInputSession, VoiceInputSessionInfo, create_voice_input_session

# v5.2.0 public voice-input session exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['VoiceInputSession', 'VoiceInputSessionInfo', 'create_voice_input_session']:
    if _name not in __all__:
        __all__.append(_name)
del _name

from .voice_input_capability import VoiceInputCapabilities, VoiceInputProviderConfig, VoiceInputProviderStatus, get_voice_input_capabilities, resolve_voice_input_provider_config

# v5.2.0 public voice-input capability preflight exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['VoiceInputCapabilities', 'VoiceInputProviderConfig', 'VoiceInputProviderStatus', 'get_voice_input_capabilities', 'resolve_voice_input_provider_config']:
    if _name not in __all__:
        __all__.append(_name)
del _name

from .realtime import RealtimeErrorCode, RealtimeEvent, RealtimeEventType, RealtimeState, RealtimeTurn, RealtimeTurnResult

# v5.2.0 public realtime lifecycle/event exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['RealtimeErrorCode', 'RealtimeEvent', 'RealtimeEventType', 'RealtimeState', 'RealtimeTurn', 'RealtimeTurnResult']:
    if _name not in __all__:
        __all__.append(_name)
del _name

from .realtime_session import RealtimeSession, RealtimeSessionInfo, create_realtime_session

# v5.2.0 public realtime session exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['RealtimeSession', 'RealtimeSessionInfo', 'create_realtime_session']:
    if _name not in __all__:
        __all__.append(_name)
del _name

from .output_control import BargeInDecision, BargeInPolicy, BargeInPolicyMode, InterruptOutcome, InterruptReason, InterruptRequest, InterruptResult, InterruptScope, OutputFlushOutcome, OutputFlushRequest, OutputFlushResult, TTSQueueState

# v5.2.0 public interrupt/output-control exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['BargeInDecision', 'BargeInPolicy', 'BargeInPolicyMode', 'InterruptOutcome', 'InterruptReason', 'InterruptRequest', 'InterruptResult', 'InterruptScope', 'OutputFlushOutcome', 'OutputFlushRequest', 'OutputFlushResult', 'TTSQueueState']:
    if _name not in __all__:
        __all__.append(_name)
del _name

from .motion import MotionAdapterStatus, MotionCapability, MotionErrorCode, MotionEventType, MotionIntent, MotionOutcome, MotionRequest, MotionResult, MotionState

# v5.2.0 public motion adapter exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['MotionAdapterStatus', 'MotionCapability', 'MotionErrorCode', 'MotionEventType', 'MotionIntent', 'MotionOutcome', 'MotionRequest', 'MotionResult', 'MotionState']:
    if _name not in __all__:
        __all__.append(_name)
del _name

from .motion_session import MotionSession, MotionSessionInfo, create_motion_session

# v5.2.0 public motion session exports
try:
    __all__
except NameError:
    __all__ = []
for _name in ['MotionSession', 'MotionSessionInfo', 'create_motion_session']:
    if _name not in __all__:
        __all__.append(_name)
del _name
from .motion_adapter_execution import (
    MotionAdapterExecutionConfig,
    get_motion_adapter_execution_capability,
    resolve_motion_adapter_execution_config,
)

# v5.5.0 candidate explicit motion-adapter configuration exports
try:
    __all__
except NameError:
    __all__ = []
for _name in [
    "MotionAdapterExecutionConfig",
    "get_motion_adapter_execution_capability",
    "resolve_motion_adapter_execution_config",
]:
    if _name not in __all__:
        __all__.append(_name)
del _name

# v5.4.0 provider-specific exports are resolved lazily so that
# `import framework` remains provider-safe.
_PROVIDER_SPECIFIC_LAZY_EXPORTS = {
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


def __getattr__(name: str):
    module_name = _PROVIDER_SPECIFIC_LAZY_EXPORTS.get(name)
    if module_name is not None:
        from importlib import import_module

        module = import_module(module_name, __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(
        f"module {__name__!r} has no attribute {name!r}"
    )
