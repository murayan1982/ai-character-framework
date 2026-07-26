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
