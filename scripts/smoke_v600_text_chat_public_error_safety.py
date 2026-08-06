"""FW-RT6-2a Control C TextChat public error-safety smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or host-application repository operation occurs.
"""

from __future__ import annotations

import inspect
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "4e1cf483f9e6568033e2b9b00e6bb7d3b0d404f9"
EXPECTED_BASELINE_PARENT = "b351cf74a5b20e55a4aede8746841c05a58bfbb9"
EXPECTED_BASELINE_SUBJECT = "refactor/test: migrate core public metadata sanitizers"
EXPECTED_BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_safety_contract.md",
    "framework/motion.py",
    "framework/output_control.py",
    "framework/realtime.py",
    "framework/realtime_capabilities.py",
    "framework/voice_input.py",
    "scripts/smoke_v600_public_safety_consumer_migration.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_safety_contract.md",
    "framework/facade.py",
    "scripts/smoke_v600_text_chat_public_error_safety.py",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
)
SECRET = "private-provider-secret-value"
PRIVATE_PATH = r"E:\private\provider-payload.json"


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
        if line.strip()
    }


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected Control C baseline")
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "Control B parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "Control B subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == EXPECTED_BASELINE_SURFACE,
        "Control B exact surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control C surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted Control B baseline and exact five-file Control C surface conform")


class _PrivateProviderExplosion(RuntimeError):
    pass


class _FailingLLM:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def ask_stream(self, _text: str):
        raise self.error
        yield "", []

    def reset_session(self) -> None:
        return None


def _session(error: Exception):
    from framework.facade import TextChatSession, TextChatSessionInfo

    info = TextChatSessionInfo(
        preset="text_chat",
        character_name="default",
        input_language_code="ja",
        output_language_code="ja",
        llm_mode="direct_provider",
        provider="mock",
        model="mock",
        route_name=None,
    )
    return TextChatSession(_FailingLLM(error), info)


def _assert_no_private_material(value: object, *, label: str) -> None:
    serialized = repr(value)
    for forbidden in (
        SECRET,
        PRIVATE_PATH,
        "_PrivateProviderExplosion",
        "RuntimeError",
    ):
        _assert(forbidden not in serialized, f"{label}: leaked {forbidden}")


def check_streaming_error_event() -> None:
    error = _PrivateProviderExplosion(f"{SECRET} at {PRIVATE_PATH}")
    session = _session(error)
    events = []
    session.on_event(events.append)

    try:
        list(session.ask_stream("hello"))
    except _PrivateProviderExplosion as caught:
        _assert(caught is error, "ask_stream must re-raise the original exception")
    else:
        raise AssertionError("ask_stream must preserve exception re-raise behavior")

    error_events = [event for event in events if event.type == "error"]
    _assert(len(error_events) == 1, "exactly one public error event is required")
    data = error_events[0].data

    _assert(
        set(data) == {
            "public_error_code",
            "safe_message",
            "retryable",
            "public_metadata",
        },
        f"unexpected error event keys: {sorted(data)}",
    )
    _assert("error" not in data, "raw error field must be removed")
    _assert("error_type" not in data, "exception class field must be removed")
    _assert(data["public_error_code"] == "provider_request_failed", "fallback code drift")
    _assert(
        data["safe_message"] == "Text chat provider request failed.",
        "safe message drift",
    )
    _assert(data["retryable"] is True, "provider request fallback should be retryable")
    _assert(data["public_metadata"]["boundary"] == "text_chat", "boundary metadata missing")
    _assert_no_private_material(data, label="streaming error event")

    print("[OK] streaming error event contains only provider-neutral safe fields")


def check_typed_result_adoption() -> None:
    events = []
    session = _session(_PrivateProviderExplosion(f"{SECRET} at {PRIVATE_PATH}"))
    session.on_event(events.append)
    result = session.ask_result("hello")

    _assert(result.outcome == "failed", "ask_result failure outcome drift")
    _assert(
        result.public_error_code == "provider_request_failed",
        "ask_result classifier code drift",
    )
    _assert(
        result.safe_message == "Text chat provider request failed.",
        "ask_result safe message drift",
    )
    _assert(result.retryable is True, "ask_result retryability drift")
    _assert(result.public_metadata["boundary"] == "text_chat", "result boundary missing")
    _assert_no_private_material(result, label="typed result")

    error_events = [event for event in events if event.type == "error"]
    _assert(len(error_events) == 1, "ask_result path should emit one safe error event")
    _assert_no_private_material(error_events[0].data, label="ask_result error event")

    print("[OK] ask_result and streaming events share safe classification behavior")


def check_classification_matrix() -> None:
    from framework.facade import (
        FacadeConfigError,
        FacadeProviderError,
        _classify_text_chat_exception,
    )

    cases = (
        (FacadeConfigError(SECRET), "configuration_missing", False),
        (FacadeProviderError(SECRET), "provider_request_failed", True),
        (TimeoutError(SECRET), "timeout", True),
        (InterruptedError(SECRET), "request_cancelled", True),
        (PermissionError(SECRET), "authentication_required", False),
        (ConnectionError(SECRET), "provider_unavailable", True),
        (TypeError(SECRET), "invalid_request", False),
        (ValueError(SECRET), "invalid_request", False),
        (_PrivateProviderExplosion(SECRET), "provider_request_failed", True),
    )

    for error, expected_code, expected_retryable in cases:
        classification = _classify_text_chat_exception(error)
        _assert(
            classification.public_error_code == expected_code,
            f"classification code drift for {type(error).__name__}",
        )
        _assert(
            classification.retryable is expected_retryable,
            f"retryability drift for {type(error).__name__}",
        )
        _assert_no_private_material(
            classification,
            label=f"classification {expected_code}",
        )

    print("[OK] TextChat exception-type classification matrix conforms")


def check_source_contract() -> None:
    from framework.facade import (
        TextChatSession,
        _classify_text_chat_exception,
        _text_chat_error_event_data,
    )

    ask_stream_source = inspect.getsource(TextChatSession.ask_stream)
    classifier_source = inspect.getsource(_classify_text_chat_exception)
    event_data_source = inspect.getsource(_text_chat_error_event_data)

    for forbidden in (
        "str(exc)",
        "repr(exc)",
        "type(exc).__name__",
        "exc.__class__.__name__",
    ):
        _assert(forbidden not in ask_stream_source, f"ask_stream raw inspection remains: {forbidden}")
        _assert(forbidden not in classifier_source, f"classifier raw inspection remains: {forbidden}")
        _assert(forbidden not in event_data_source, f"event data raw inspection remains: {forbidden}")

    _assert('"error"' not in event_data_source, "legacy raw error event field remains")
    _assert('"error_type"' not in event_data_source, "legacy error_type field remains")
    _assert("raise" in ask_stream_source, "ask_stream exception re-raise was removed")

    print("[OK] source contract forbids raw exception inspection and preserves re-raise")


def check_public_surface_and_docs() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert(
        "_classify_text_chat_exception" not in PUBLIC_API_NAMES,
        "private classifier leaked to root API",
    )

    for relative in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-2a-C-TEXT-CHAT-ERROR-SAFETY:BEGIN" in text,
            f"Control C marker missing: {relative}",
        )
        _assert(
            "raw exception string in error event: False" in text,
            f"raw exception status missing: {relative}",
        )
        _assert(
            "ask_stream exception re-raise: PRESERVED" in text,
            f"compatibility statement missing: {relative}",
        )

    contract = (PROJECT_ROOT / "docs" / "v600_public_safety_contract.md").read_text(
        encoding="utf-8"
    )
    _assert("FW-RT6-2a-C-CONTRACT:BEGIN" in contract, "Control C contract missing")
    _assert("The previous `error` and `error_type` fields are removed" in contract, "field removal missing")
    _assert("FW-RT6-2b" in contract, "event sequencer deferral missing")

    print("[OK] 121-name public surface and Control C documentation conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] TextChat error-safety imports stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_streaming_error_event()
    check_typed_result_adoption()
    check_classification_matrix()
    check_source_contract()
    check_public_surface_and_docs()
    check_import_safety()

    print("v600_rt6_2a_control_c_status: implemented-awaiting-review")
    print("v600_rt6_2a_control_c_exact_change_surface_count: 5")
    print("v600_rt6_2a_control_c_root_public_names: 121 / unchanged")
    print("v600_rt6_2a_control_c_text_chat_event_type_changed: False")
    print("v600_rt6_2a_control_c_ask_stream_exception_reraise_preserved: True")
    print("v600_rt6_2a_control_c_raw_exception_string_in_event: False")
    print("v600_rt6_2a_control_c_exception_class_name_in_event: False")
    print("v600_rt6_2a_control_c_ask_result_safe_classifier_adopted: True")
    print("v600_rt6_2a_control_c_streaming_event_safe_classifier_adopted: True")
    print("v600_rt6_2a_control_c_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2a_next_control: FW-RT6-2a Control D")
    print("v600_rt6_2a_next_control_authorized: False")
    print("[OK] FW-RT6-2a Control C TextChat public error safety passed")


if __name__ == "__main__":
    main()
