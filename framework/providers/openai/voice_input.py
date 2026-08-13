"""Stable optional OpenAI voice-input compatibility namespace.

This module re-exports the fifteen frozen v5.4 OpenAI voice-input contract
objects without importing the OpenAI SDK or executing provider, network,
audio, microphone, or runtime work. The Framework root keeps the same objects
as lazy, warning-free compatibility exports for the complete v6 lifecycle.
"""

from __future__ import annotations

from ...openai_voice_input_fake_execution import (
    OpenAIVoiceInputFakeClientMarker,
    OpenAIVoiceInputFakeExecutionPolicy,
    OpenAIVoiceInputFakeExecutionStatus,
    OpenAIVoiceInputFakeExecutor,
)
from ...openai_voice_input_provider_adapter import (
    OpenAIVoiceInputClient,
    OpenAIVoiceInputClientFactory,
    OpenAIVoiceInputPreflight,
    OpenAIVoiceInputPreflightStatus,
    OpenAIVoiceInputProviderAdapter,
)
from ...openai_voice_input_real_provider import (
    OpenAIVoiceInputPrivateCredential,
    OpenAIVoiceInputRealClientFactory,
    OpenAIVoiceInputRealProviderExecutor,
    OpenAIVoiceInputRealProviderPolicy,
    OpenAIVoiceInputRealProviderStatus,
    OpenAIVoiceInputRuntimeMode,
)

__all__ = (
    "OpenAIVoiceInputClient",
    "OpenAIVoiceInputClientFactory",
    "OpenAIVoiceInputFakeClientMarker",
    "OpenAIVoiceInputFakeExecutionPolicy",
    "OpenAIVoiceInputFakeExecutionStatus",
    "OpenAIVoiceInputFakeExecutor",
    "OpenAIVoiceInputPreflight",
    "OpenAIVoiceInputPreflightStatus",
    "OpenAIVoiceInputPrivateCredential",
    "OpenAIVoiceInputProviderAdapter",
    "OpenAIVoiceInputRealClientFactory",
    "OpenAIVoiceInputRealProviderExecutor",
    "OpenAIVoiceInputRealProviderPolicy",
    "OpenAIVoiceInputRealProviderStatus",
    "OpenAIVoiceInputRuntimeMode",
)
