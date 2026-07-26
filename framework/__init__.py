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
