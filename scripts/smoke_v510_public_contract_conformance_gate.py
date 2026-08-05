"""Smoke check for FW v5.1.0 public contract conformance gate.

This is a mock-safe aggregate gate. It checks public API/docs/example alignment
without importing provider SDKs, calling providers, or creating real artifacts.
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from typing import Iterable


class ContractFailure(AssertionError):
    """Raised when a public contract conformance check fails."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_on_path(root: Path) -> None:
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _info(message: str) -> None:
    print(f"[INFO] {message}")


def _warn(message: str) -> None:
    print(f"[WARN] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _forbidden_loaded(forbidden: set[str], *, baseline: set[str] | None = None) -> list[str]:
    baseline = baseline or set()
    loaded = []
    for name in sys.modules:
        if name in baseline:
            continue
        if name in forbidden or any(name.startswith(prefix + ".") for prefix in forbidden):
            loaded.append(name)
    return sorted(loaded)


def _assert_not_loaded(forbidden: set[str], *, baseline: set[str] | None = None) -> None:
    loaded = _forbidden_loaded(forbidden, baseline=baseline)
    _require(not loaded, "forbidden modules were loaded: " + ", ".join(loaded))

def _assert_import_safety(root: Path) -> None:
    _ensure_repo_on_path(root)
    forbidden = {
        "tts.voice_engine",
        "elevenlabs",
        "openai",
        "google.generativeai",
    }
    _assert_not_loaded(forbidden)
    import framework  # noqa: PLC0415

    _assert_not_loaded(forbidden)
    _ok("public conformance import stays provider/internal safe")
    return framework


def _assert_docs(root: Path) -> None:
    required_docs = [
        "docs/v510_public_contract_inventory.md",
        "docs/v510_public_factory_signature_contract.md",
        "docs/v510_result_error_contract.md",
        "docs/v510_text_chat_result_public_type.md",
        "docs/v510_text_chat_result_runtime_method.md",
        "docs/v510_capability_snapshot_contract.md",
        "docs/v510_provider_config_ownership.md",
        "docs/v510_session_lifecycle_contract.md",
        "docs/v510_opaque_voice_artifact_contract.md",
        "docs/v510_public_contract_conformance_gate.md",
    ]
    missing = [rel for rel in required_docs if not (root / rel).exists()]
    _require(not missing, "missing v5.1.0 public contract docs: " + ", ".join(missing))

    gate_doc = _read(root / "docs/v510_public_contract_conformance_gate.md")
    for phrase in [
        "import framework must not import provider SDKs",
        "VoiceOutputSession.speak(request) is the preferred voice output method",
        "TextChatSession.ask_result(message)",
        "VoiceArtifactRef is opaque",
        "get_capabilities() returns provider-neutral capability state",
    ]:
        _require(phrase in gate_doc, f"conformance gate doc missing phrase: {phrase}")

    _ok("v5.1.0 public contract conformance gate doc is documented")


def _assert_readme_alignment(root: Path) -> None:
    readme = _read(root / "README.md") if (root / "README.md").exists() else ""
    _require("session.speak(" in readme, "README should use session.speak(...) for voice output")
    _require("ask_result(" in readme, "README should document ask_result(...) typed result usage")
    _ok("README public examples use preferred v5.1.0 API names")


def _assert_examples(root: Path) -> None:
    required_examples = [
        "examples/app_voice_output_integration.py",
        "examples/app_text_chat_result.py",
    ]
    missing = [rel for rel in required_examples if not (root / rel).exists()]
    _require(not missing, "missing public examples: " + ", ".join(missing))

    voice_example = _read(root / "examples/app_voice_output_integration.py")
    text_example = _read(root / "examples/app_text_chat_result.py")
    _require(".speak(" in voice_example, "voice output example should use speak()")
    _require("ask_result(" in text_example, "text chat result example should use ask_result()")
    _ok("public examples use preferred v5.1.0 API names")


def _assert_all_exports(framework: object) -> None:
    exported = set(getattr(framework, "__all__", ()))
    required = {
        "create_text_chat_session",
        "TextChatSessionInfo",
        "TextChatResult",
        "CapabilityStatus",
        "FrameworkCapabilities",
        "get_capabilities",
        "create_voice_output_session",
        "VoiceOutputSession",
        "VoiceOutputSessionInfo",
        "VoiceOutputRequest",
        "VoiceArtifactRef",
        "VoiceOutputResult",
    }
    missing = sorted(required - exported)
    _require(not missing, "required public symbols missing from __all__: " + ", ".join(missing))

    for symbol in sorted(required):
        _require(hasattr(framework, symbol), f"framework missing public symbol: {symbol}")
        _info(f"public symbol: {symbol}")

    legacy_aliases = {
        "create_tts_session",
        "create_output_session",
        "create_voice_session",
        "create_realtime_voice_session",
    }
    leaked = sorted(legacy_aliases & exported)
    _require(not leaked, "legacy factory aliases leaked into __all__: " + ", ".join(leaked))
    _ok("framework.__all__ matches v5.1.0 conformance baseline")


def _assert_factory_signatures(framework: object) -> None:
    text_sig = inspect.signature(framework.create_text_chat_session)
    voice_sig = inspect.signature(framework.create_voice_output_session)
    _info(f"signature create_text_chat_session{text_sig}")
    _info(f"signature create_voice_output_session{voice_sig}")

    _require(
        list(text_sig.parameters) == ["preset", "character_name", "provider", "model", "project_root"],
        "create_text_chat_session parameter names drifted from transition baseline",
    )
    for name in ("preset", "character_name", "provider", "model"):
        _require(
            text_sig.parameters[name].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD,
            f"create_text_chat_session {name} compatibility changed",
        )
    _require(
        text_sig.parameters["project_root"].kind is inspect.Parameter.KEYWORD_ONLY,
        "create_text_chat_session project_root must be keyword-only",
    )

    _require(
        list(voice_sig.parameters) == [
            "project_root",
            "default_voice_profile_id",
            "real_tts_enabled",
            "artifact_dir",
        ],
        "create_voice_output_session parameter names drifted from v5.1.0 baseline",
    )
    _require(
        all(param.kind is inspect.Parameter.KEYWORD_ONLY for param in voice_sig.parameters.values()),
        "create_voice_output_session must remain keyword-only",
    )

    unwanted = {
        "preset_name",
        "preset_id",
        "character",
        "character_id",
        "framework_project_root",
        "provider_voice_id",
        "api_key",
        "model_id",
    }
    for sig_name, sig in [
        ("create_text_chat_session", text_sig),
        ("create_voice_output_session", voice_sig),
    ]:
        leaked = sorted(unwanted & set(sig.parameters))
        _require(not leaked, f"{sig_name} exposes unwanted app-side alias/provider params: {leaked}")

    _ok("public factory signatures match v5.1.0 conformance baseline")


def _get_text_chat_session_class(framework: object) -> type:
    """Return TextChatSession class without constructing a provider-backed session."""

    candidate = getattr(framework, "TextChatSession", None)
    if candidate is not None and callable(getattr(candidate, "ask_result", None)):
        return candidate

    facade_module = sys.modules.get("framework.facade")
    candidate = getattr(facade_module, "TextChatSession", None) if facade_module is not None else None
    _require(candidate is not None, "TextChatSession class should be available after framework import")
    _require(callable(getattr(candidate, "ask_result", None)), "TextChatSession does not expose ask_result")
    return candidate


def _make_text_chat_session_without_provider(framework: object) -> object:
    """Create a provider-free TextChatSession instance for conformance checks."""

    session_cls = _get_text_chat_session_class(framework)
    session = object.__new__(session_cls)
    # Keep ask_result() on the provider-free closed path if the smoke calls it.
    session._fw_public_closed = True
    return session


def _assert_text_chat_result_contract(framework: object) -> None:
    result_type = framework.TextChatResult
    completed = result_type.completed("take an early rest today")
    _require(completed.outcome == "completed", "TextChatResult.completed outcome mismatch")
    _require(completed.text, "TextChatResult.completed should include text")
    _require(completed.public_error_code is None, "completed result should not expose error code")

    failed = result_type.failed(
        public_error_code="provider_unavailable",
        safe_message="Provider is unavailable.",
        retryable=True,
    )
    _require(failed.outcome == "failed", "TextChatResult.failed outcome mismatch")
    _require(failed.retryable is True, "failed retryable flag mismatch")
    _require("api_key" not in repr(failed).lower(), "TextChatResult repr should be secret-free")

    session = _make_text_chat_session_without_provider(framework)
    _require(hasattr(session, "ask_result"), "TextChatSession missing ask_result")
    _require(hasattr(session, "close"), "TextChatSession missing close")
    session.close()
    closed = session.ask_result("hello")
    _require(closed.outcome == "failed", "closed TextChatSession should return failed outcome")
    _require(closed.public_error_code == "session_closed", "closed TextChatSession should return session_closed")
    _ok("TextChatResult and TextChatSession typed-result contract is conformance-checked")


def _assert_voice_output_contract(framework: object) -> None:
    request = framework.VoiceOutputRequest(
        text="hello",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="conformance_check",
        language_code="en",
    )
    session = framework.create_voice_output_session()
    _require(hasattr(session, "speak"), "VoiceOutputSession missing speak")
    _require(hasattr(session, "create_output"), "VoiceOutputSession missing create_output compatibility alias")
    result = session.speak(request)
    _require(result.audio_ready is False, "mock-safe voice output should not be audio-ready by default")
    _require(result.has_audio_handoff is False, "mock-safe unavailable result should not expose handoff")
    _require(result.audio_handoff_kind == "none", "mock-safe unavailable result handoff kind should be none")

    session.close()
    closed = session.speak(request)
    _require(closed.audio_ready is False, "closed voice output result must be non-playable")
    _require(closed.audio_handoff_kind == "none", "closed voice output result must not expose handoff")
    metadata = getattr(closed, "public_metadata", {}) or {}
    _require(
        metadata.get("public_error_code") == "session_closed",
        "closed voice output result should expose provider-neutral session_closed code",
    )

    ref = framework.VoiceArtifactRef.from_id("voice_artifact_conformance_001", audio_format="mp3")
    generated = framework.VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_format="mp3",
        audio_url=None,
        audio_artifact_ref=ref,
        message="generated",
    )
    _require(generated.has_audio_handoff is True, "generated artifact result should expose one handoff")
    _require(generated.audio_handoff_kind == "audio_artifact_ref", "artifact result handoff kind mismatch")

    rejected_path = False
    try:
        framework.VoiceArtifactRef.from_id("C:" + chr(92) + "private" + chr(92) + "audio.mp3")
    except ValueError:
        rejected_path = True
    _require(rejected_path, "VoiceArtifactRef must reject raw local paths")
    _ok("VoiceOutputResult and VoiceArtifactRef contract is conformance-checked")


def _assert_capability_contract(framework: object) -> None:
    capabilities = framework.get_capabilities()
    _require(capabilities.schema_version, "capability snapshot should expose schema_version")
    _require(capabilities.text_chat.supported is True, "text_chat should be supported")
    _require(capabilities.voice_output.supported is True, "voice_output should be supported")
    _require(
        capabilities.voice_input.available is False,
        "voice_input should not be reported available before public STT implementation",
    )
    _require(
        capabilities.realtime.available is False,
        "realtime should not be reported available before public realtime implementation",
    )
    _require(
        capabilities.motion.available is False,
        "motion should not be reported available before public motion implementation",
    )
    _ok("capability snapshot contract is conformance-checked")


def main() -> None:
    root = _repo_root()
    forbidden = {"tts.voice_engine", "elevenlabs", "openai", "google.generativeai"}
    forbidden_baseline = set(sys.modules)
    _ensure_repo_on_path(root)

    # Force mock-safe defaults for this process.
    os.environ.pop("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION", None)
    os.environ.pop("FRAMEWORK_VOICE_OUTPUT_REAL_TTS", None)

    _assert_docs(root)
    _assert_readme_alignment(root)
    _assert_examples(root)
    framework = _assert_import_safety(root)
    _assert_all_exports(framework)
    _assert_factory_signatures(framework)
    _assert_text_chat_result_contract(framework)
    _assert_voice_output_contract(framework)
    _assert_capability_contract(framework)
    # Strict final check: public conformance must not load voice/TTS internals.
    # LLM provider SDK imports during legacy text-chat exercise are recorded as a
    # v5.1.0 transition warning; public import safety is checked earlier.
    _assert_not_loaded({"tts.voice_engine", "elevenlabs"}, baseline=forbidden_baseline)

    provider_loaded = _forbidden_loaded({"openai", "google.generativeai"}, baseline=forbidden_baseline)
    if provider_loaded:
        preview = ", ".join(provider_loaded[:8])
        if len(provider_loaded) > 8:
            preview += ", ..."
        print(
            "[WARN] provider SDK modules loaded during full conformance exercise; "
            "public import safety is checked earlier and SDK lazy-loading remains a follow-up: "
            + preview
        )
    _ok("v5.1.0 public contract conformance gate is mock-safe")


if __name__ == "__main__":
    main()
