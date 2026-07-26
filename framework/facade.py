from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Generator

from llm.base import BaseLLM
from config.prompt_builder import build_final_system_instruction

if TYPE_CHECKING:
    from config.loader import RuntimeConfig

from framework.audio import (
    VoiceOutputRequest,
    VoiceOutputResult,
    VoiceOutputSession,
    VoiceOutputSessionInfo,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
    create_voice_output_session,
)

DEFAULT_TEXT_CHAT_PRESET = "text_chat"

# Public-facing aliases for app developers. Internal provider identifiers remain
# owned by llm.factory / registry.llm.
PROVIDER_ALIASES = {
    "gemini": "google",
    "grok": "xai",
}


class FacadeError(Exception):
    """Base exception for public facade integration errors."""


class FacadeConfigError(FacadeError):
    """Raised when facade preset or text-only configuration is invalid."""


class FacadeProviderError(FacadeError):
    """Raised when facade provider/model resolution or creation fails."""


@dataclass(frozen=True)
class TextChatSessionInfo:
    """Public, stable session information for app integrations.

    This model intentionally exposes only integration-safe metadata. Internal
    RuntimeConfig details remain private so the runtime can evolve without
    breaking application code that depends on the public facade.
    """

    preset: str
    character_name: str
    input_language_code: str
    output_language_code: str
    llm_mode: str
    provider: str | None
    model: str | None
    route_name: str | None
    api_version: str = "4.0"
    session_type: str = "text_chat"
    supports_streaming: bool = True
    supports_reset: bool = True
    supports_interrupt: bool = True
    supports_events: bool = True
    supports_close: bool = False
    supports_voice_input: bool = False
    supports_voice_output: bool = False
    supports_live2d: bool = False


@dataclass(frozen=True)
class TextChatSessionEvent:
    """Public app-facing event emitted by a text chat session.

    Events are intentionally small and app-safe. They do not expose provider,
    runtime, plugin, STT/TTS, or VTS implementation objects.
    """

    type: str
    data: dict[str, object]


@dataclass(frozen=True)
class TextChatStateChange:
    """Public app-facing state transition emitted by a text chat session."""

    old_state: str
    new_state: str


class TextChatSession:
    """Public text-chat session facade.

    This class is the small public entry point for developers who want to use
    the framework as a library instead of launching the interactive main loop.
    It owns one LLM instance and exposes simple text-only turn methods.
    """

    def __init__(self, llm: BaseLLM, info: TextChatSessionInfo):
        self._llm = llm
        self.info = info
        self._interrupt_requested = False
        self._state = "idle"
        self._event_callbacks: list[Callable[[TextChatSessionEvent], None]] = []
        self._state_change_callbacks: list[Callable[[TextChatStateChange], None]] = []

    def on_event(
        self,
        callback: Callable[[TextChatSessionEvent], None],
    ) -> Callable[[TextChatSessionEvent], None]:
        """Register an app-facing event callback and return it.

        This callback API is separate from internal plugin hooks. It is intended
        for external apps that want to observe text session events without
        importing runtime or plugin internals.
        """
        self._event_callbacks.append(callback)
        return callback

    def on_state_change(
        self,
        callback: Callable[[TextChatStateChange], None],
    ) -> Callable[[TextChatStateChange], None]:
        """Register an app-facing state change callback and return it."""
        self._state_change_callbacks.append(callback)
        return callback

    def _emit_event(
        self,
        event_type: str,
        data: dict[str, object] | None = None,
    ) -> None:
        """Emit one app-facing event to registered callbacks."""
        event = TextChatSessionEvent(type=event_type, data=data or {})
        for callback in list(self._event_callbacks):
            callback(event)

    def _set_state(self, new_state: str) -> None:
        """Update the app-facing session state and notify callbacks."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        event = TextChatStateChange(old_state=old_state, new_state=new_state)
        for callback in list(self._state_change_callbacks):
            callback(event)

    def ask(self, text: str) -> str:
        """Send one text turn and return the full assistant response."""
        return "".join(self.ask_stream(text))



    @property
    def is_closed(self) -> bool:
        """Whether this public text chat session has been closed."""

        return bool(getattr(self, "_fw_public_closed", False))

    def close(self) -> None:
        """Close the public text chat session.

        The public close boundary is intentionally idempotent. It marks the
        session as closed without exposing provider clients or private runtime
        resources to host applications. Provider-specific cleanup hooks can be
        wired behind this method in later checkpoints.
        """

        self._fw_public_closed = True

    def dispose(self) -> None:
        """Compatibility alias for ``close()``."""

        self.close()

    def __enter__(self) -> "TextChatSession":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.close()
        return False
    def ask_result(self, message: str) -> "TextChatResult":
        """Return a provider-neutral typed result for a text chat request.

        This method is the non-breaking typed-result companion to ``ask()``.
        Existing ``ask()`` behavior is preserved for v4/v5 compatibility, while
        host apps can use ``ask_result()`` to avoid parsing raw exception strings
        or ad-hoc response shapes.
        """

        from .text_chat_result import TextChatResult

        if getattr(self, "_fw_public_closed", False):
            return TextChatResult.failed(
                public_error_code="session_closed",
                safe_message="Text chat session is closed.",
                retryable=False,
                public_metadata={"boundary": "text_chat"},
            )

        try:
            response = self.ask(message)
        except Exception as exc:  # noqa: BLE001 - public boundary converts to safe result
            return TextChatResult.failed(
                public_error_code=_text_chat_exception_to_public_error_code(exc),
                safe_message=_text_chat_exception_to_safe_message(exc),
                retryable=_text_chat_exception_is_retryable(exc),
                public_metadata={"boundary": "text_chat"},
            )

        text = _text_chat_response_to_text(response)
        if text is None:
            return TextChatResult.failed(
                public_error_code="empty_response",
                safe_message="Text chat returned no response text.",
                retryable=True,
                public_metadata={"boundary": "text_chat"},
            )

        return TextChatResult.completed(
            text,
            public_metadata={"boundary": "text_chat"},
        )
    def ask_stream(self, text: str) -> Generator[str, None, None]:
        """Send one text turn and yield assistant response chunks."""
        self._interrupt_requested = False
        self._set_state("responding")
        self._emit_event("response_started", {"text": text})

        completed = False
        try:
            for chunk, _emotions in self._llm.ask_stream(text):
                if self._interrupt_requested:
                    self._set_state("interrupted")
                    break
                if chunk:
                    self._emit_event("response_chunk", {"chunk": chunk})
                    yield chunk
            else:
                completed = True
                self._emit_event("response_completed")
        except Exception as exc:
            self._set_state("error")
            self._emit_event(
                "error",
                {
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            raise
        finally:
            if completed or self._state in {"responding", "interrupted", "error"}:
                self._set_state("idle")

    def reset(self) -> None:
        """Reset provider-owned conversation state when supported."""
        self._llm.reset_session()
        self._emit_event("reset")
        self._set_state("idle")

    def interrupt(self) -> bool:
        """Request interruption of the current or next app-facing operation.

        v4.0.0 exposes this as a public app-facing boundary. Text sessions do not
        provide provider-level hard cancellation yet, so this method records the
        request and returns whether the session accepted it.
        """
        self._interrupt_requested = True
        self._emit_event("interrupt_requested")
        return True


def _resolve_preset_name(preset: str | None) -> str:
    """Resolve facade preset priority: explicit argument -> .env -> default."""
    if preset:
        return preset

    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv()

    return os.getenv("APP_PRESET", DEFAULT_TEXT_CHAT_PRESET)


def _is_text_only_config(config: "RuntimeConfig") -> bool:
    """Return whether a RuntimeConfig is compatible with the text facade."""
    return (
        not config.input_voice_enabled
        and not config.output_voice_enabled
        and not config.vts_enabled
        and config.tts_provider == "none"
    )


def _validate_text_only_config(config: "RuntimeConfig") -> None:
    """Reject presets that would require runtime systems outside the facade."""
    if _is_text_only_config(config):
        return

    raise FacadeConfigError(
        "create_text_chat_session() currently supports text-only presets only. "
        f"Preset '{config.app_preset}' enables one or more unsupported runtime features: "
        f"input_voice_enabled={config.input_voice_enabled}, "
        f"output_voice_enabled={config.output_voice_enabled}, "
        f"vts_enabled={config.vts_enabled}, "
        f"tts_provider={config.tts_provider!r}. "
        "Use a text-only preset such as 'text_chat', or launch main.py for full runtime features."
    )


def _load_facade_config(
    preset: str | None,
    character_name: str | None,
) -> "RuntimeConfig":
    """Build RuntimeConfig for the public facade without starting the runtime loop.

    Boundary rules:
    - explicit function arguments override preset / environment defaults
    - APP_PRESET is used only when preset is not passed
    - character_name overrides the character selected by the preset
    - only text-only presets are accepted by the public text-chat facade
    """
    from config.loader import (
        RuntimeConfig,
        load_character_data,
        load_preset_file,
        normalize_language_code,
    )

    preset_name = _resolve_preset_name(preset)

    try:
        preset_data = load_preset_file(preset_name)
    except FileNotFoundError as e:
        raise FacadeConfigError(
            f"Facade preset not found: {preset_name!r}. "
            "Pass an existing text-only preset name, such as 'text_chat'."
        ) from e

    resolved_character_name = character_name or preset_data.get(
        "character_name",
        preset_data.get("character", "default"),
    )

    try:
        character_data = load_character_data(resolved_character_name)
    except FileNotFoundError as e:
        raise FacadeConfigError(
            f"Facade character not found: {resolved_character_name!r}. "
            "Pass an existing character name or update the selected preset."
        ) from e

    config = RuntimeConfig(
        app_preset=preset_name,
        input_language_code=normalize_language_code(
            preset_data.get("input_language_code", "ja"),
            default="ja",
        ),
        output_language_code=normalize_language_code(
            preset_data.get("output_language_code", "ja"),
            default="en",
        ),
        input_voice_enabled=bool(preset_data.get("input_voice_enabled", False)),
        output_voice_enabled=bool(preset_data.get("output_voice_enabled", False)),
        vts_enabled=bool(preset_data.get("vts_enabled", False)),
        tts_provider=preset_data.get("tts_provider", "none"),
        allow_text_fallback_during_stt=bool(
            preset_data.get("allow_text_fallback_during_stt", False)
        ),
        emotion_enabled=bool(preset_data.get("emotion_enabled", False)),
        vts_emotion_enabled=bool(preset_data.get("vts_emotion_enabled", False)),
        character_name=resolved_character_name,
        character_profile=character_data.profile,
        system_prompt=character_data.system_prompt,
        vts_hotkeys=character_data.vts_hotkeys,
    )

    _validate_text_only_config(config)
    return config


def _build_system_instruction(config: "RuntimeConfig") -> str:
    """Build the same final system instruction used by the runtime layer."""
    return build_final_system_instruction(config)


def _build_catalog_llm(llm_name: str, system_instruction: str) -> BaseLLM:
    """Build one catalog LLM without importing the full runtime builder."""
    from llm.factory import create_llm
    from registry.llm import LLM_CATALOG

    if llm_name not in LLM_CATALOG:
        raise FacadeProviderError(f"Unknown LLM catalog entry: {llm_name}")

    llm_config = LLM_CATALOG[llm_name]

    try:
        return create_llm(
            provider=llm_config["provider"],
            model=llm_config["model"],
            system_instruction=system_instruction,
        )
    except ValueError as e:
        raise FacadeProviderError(str(e)) from e


def _normalize_provider(provider: str) -> str:
    """Normalize public provider aliases to internal provider identifiers."""
    normalized = provider.strip().lower()
    return PROVIDER_ALIASES.get(normalized, normalized)


def _resolve_default_model_for_provider(provider: str) -> str:
    """Resolve the first registry model matching a provider.

    The registry remains the owner of default provider/model pairs. The facade
    only selects an existing catalog model when an app passes provider without a
    model override.
    """
    from registry.llm import LLM_CATALOG

    for llm_config in LLM_CATALOG.values():
        if llm_config.get("provider") == provider:
            return llm_config["model"]

    raise FacadeProviderError(
        f"No default model is registered for provider {provider!r}. "
        "Pass both provider and model, or add the provider to registry.llm.LLM_CATALOG."
    )


def _resolve_provider_model(
    provider: str,
    model: str | None,
) -> tuple[str, str]:
    """Validate facade provider/model arguments and resolve model defaults."""
    from llm.factory import get_supported_llm_providers

    resolved_provider = _normalize_provider(provider)
    supported_providers = get_supported_llm_providers()

    if resolved_provider not in supported_providers:
        public_aliases = sorted(PROVIDER_ALIASES.keys())
        raise FacadeProviderError(
            f"Unsupported facade provider: {provider!r}. "
            f"Supported providers: {sorted(supported_providers)}. "
            f"Aliases: {public_aliases}."
        )

    resolved_model = model or _resolve_default_model_for_provider(resolved_provider)
    return resolved_provider, resolved_model


def _build_direct_provider_llm(
    provider: str,
    model: str,
    system_instruction: str,
) -> BaseLLM:
    """Build one explicitly selected provider/model for facade integration use."""
    from llm.factory import create_llm

    try:
        return create_llm(
            provider=provider,
            model=model,
            system_instruction=system_instruction,
        )
    except ValueError as e:
        raise FacadeProviderError(str(e)) from e


def _build_text_chat_info(
    config: "RuntimeConfig",
    provider: str | None,
    model: str | None,
) -> TextChatSessionInfo:
    """Build the public session info model without exposing RuntimeConfig."""
    if provider:
        resolved_provider, resolved_model = _resolve_provider_model(
            provider=provider,
            model=model,
        )
        return TextChatSessionInfo(
            preset=config.app_preset,
            character_name=config.character_name,
            input_language_code=config.input_language_code,
            output_language_code=config.output_language_code,
            llm_mode="direct_provider",
            provider=resolved_provider,
            model=resolved_model,
            route_name=None,
        )

    return TextChatSessionInfo(
        preset=config.app_preset,
        character_name=config.character_name,
        input_language_code=config.input_language_code,
        output_language_code=config.output_language_code,
        llm_mode="default_route",
        provider=None,
        model=None,
        route_name="chat",
    )


def _build_text_chat_llm(
    system_instruction: str,
    info: TextChatSessionInfo,
) -> BaseLLM:
    """Build the public facade's text-chat LLM path.

    In direct provider mode, the facade builds exactly one provider/model pair.
    In default route mode, it keeps the chat route with fallback while hiding
    internal route members from the public info model.
    """
    if info.provider and info.model:
        return _build_direct_provider_llm(
            provider=info.provider,
            model=info.model,
            system_instruction=system_instruction,
        )

    from llm.fallback_llm import FallbackLLM
    from registry.llm import LLM_ROUTES

    route_config = LLM_ROUTES["chat"]
    primary = _build_catalog_llm(route_config["primary"], system_instruction)
    fallback = _build_catalog_llm(route_config["fallback"], system_instruction)

    return FallbackLLM(primary, fallback)


def create_text_chat_session(
    preset: str | None = None,
    character_name: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> TextChatSession:
    """Create a text-only chat session without starting the app runtime loop.

    Args:
        preset: Optional text-only preset name. When omitted, APP_PRESET is used
            if available, otherwise 'text_chat' is used.
        character_name: Optional character override. When omitted, the character
            configured by the selected preset is used.
        provider: Optional direct LLM provider override. When omitted, the
            facade uses the default chat route with fallback.
        model: Optional model override for the selected provider. Ignored when
            provider is omitted.
    """
    config = _load_facade_config(
        preset=preset,
        character_name=character_name,
    )
    system_instruction = _build_system_instruction(config)
    info = _build_text_chat_info(
        config=config,
        provider=provider,
        model=model,
    )
    llm = _build_text_chat_llm(
        system_instruction=system_instruction,
        info=info,
    )
    return TextChatSession(llm, info)

def _text_chat_response_to_text(response: object) -> str | None:
    """Convert known public-ish text response shapes into plain text."""

    if response is None:
        return None
    if isinstance(response, str):
        text = response.strip()
        return text or None

    for attr_name in ("text", "message", "content"):
        value = getattr(response, attr_name, None)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text

    text = str(response).strip()
    if not text or text == "None":
        return None
    return text


def _text_chat_exception_to_public_error_code(exc: Exception) -> str:
    """Map private/provider exceptions to provider-neutral public codes."""

    combined = f"{exc.__class__.__name__} {exc}".lower()
    if "closed" in combined:
        return "session_closed"
    if "interrupt" in combined or "cancel" in combined:
        return "request_cancelled"
    if "timeout" in combined or "timed out" in combined:
        return "timeout"
    if "rate" in combined or "quota" in combined:
        return "rate_limited"
    if "auth" in combined or "api key" in combined or "apikey" in combined or "credential" in combined:
        return "authentication_required"
    if "config" in combined or "preset" in combined or "character" in combined or "missing" in combined:
        return "configuration_missing"
    if "unsupported" in combined:
        return "unsupported_capability"
    if "provider" in combined or "llm" in combined or "model" in combined:
        return "provider_request_failed"
    return "unknown_error"


def _text_chat_exception_is_retryable(exc: Exception) -> bool:
    """Return whether the provider-neutral error is likely retryable."""

    return _text_chat_exception_to_public_error_code(exc) in {
        "provider_unavailable",
        "provider_request_failed",
        "rate_limited",
        "timeout",
        "request_cancelled",
        "unknown_error",
    }


def _text_chat_exception_to_safe_message(exc: Exception) -> str:
    """Return a safe public message without raw provider details."""

    code = _text_chat_exception_to_public_error_code(exc)
    messages = {
        "configuration_missing": "Text chat configuration is missing or invalid.",
        "authentication_required": "Text chat provider authentication is required.",
        "rate_limited": "Text chat provider rate limit was reached.",
        "request_cancelled": "Text chat request was cancelled or interrupted.",
        "timeout": "Text chat request timed out.",
        "unsupported_capability": "Text chat capability is not supported by this session.",
        "session_closed": "Text chat session is closed.",
        "provider_request_failed": "Text chat provider request failed.",
        "provider_unavailable": "Text chat provider is unavailable.",
        "unknown_error": "Text chat request failed.",
    }
    return messages.get(code, "Text chat request failed.")

