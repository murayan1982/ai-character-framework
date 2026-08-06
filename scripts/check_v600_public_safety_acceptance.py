"""Aggregate FW-RT6-2a recursive public-safety acceptance checker.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or host-application repository operation occurs.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import inspect
import math
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTROL_C_COMMIT = "888d689fcf894fa7fa83eb6d0daa18b41f77726a"
EXPECTED_CONTROL_B_COMMIT = "4e1cf483f9e6568033e2b9b00e6bb7d3b0d404f9"
EXPECTED_CONTROL_A_COMMIT = "b351cf74a5b20e55a4aede8746841c05a58bfbb9"
EXPECTED_CONTROL_A_PARENT = "463496642f87daac1d280001d0385da1277a9f42"

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_public_safety_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}

CONTROL_A_SUBJECT = "feat/test: add recursive public safety primitives"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_safety_contract.md",
    "framework/public_safety.py",
    "scripts/smoke_v600_public_safety_primitives.py",
}
CONTROL_B_SUBJECT = "refactor/test: migrate core public metadata sanitizers"
CONTROL_B_SURFACE = {
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
CONTROL_C_SUBJECT = "fix/test: sanitize TextChat public error events"
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_safety_contract.md",
    "framework/facade.py",
    "scripts/smoke_v600_text_chat_public_error_safety.py",
}

MIGRATION_FILES = {
    "framework/realtime.py",
    "framework/voice_input.py",
    "framework/motion.py",
    "framework/output_control.py",
    "framework/realtime_capabilities.py",
}
TASK_LINES = (
    "- [x] common redaction moduleを追加する。",
    "- [x] mapping/list/tuple/dataclassのrecursive sanitizationを実装する。",
    "- [x] secret-like key policyを一箇所へ固定する。",
    "- [x] raw exception object/stringのpublic metadata投入を禁止する。",
    "- [x] safe error classification helperを追加する。",
    "- [x]既存 `_public_mapping` / `_redact_mapping`を段階的に置換する。",
    "- [x] nested secret testを追加する。",
)
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

SECRET = "aggregate-private-secret"
WINDOWS_PATH = r"E:\private\provider-payload.json"
POSIX_PATH = "/home/operator/private.env"


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


def _assert_commit(commit: str, parent: str, subject: str, surface: set[str]) -> None:
    _assert(_git("show", "-s", "--format=%s", commit) == subject, f"subject drift: {subject}")
    _assert(_git("rev-parse", f"{commit}^") == parent, f"parent drift: {subject}")
    _assert(_commit_surface(commit) == surface, f"surface drift: {subject}")


def check_repository_contract() -> None:
    _assert(
        _git("rev-parse", "HEAD") == EXPECTED_CONTROL_C_COMMIT,
        "unexpected Control D baseline",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control D surface: {sorted(_changed_paths())}",
    )
    _assert_commit(
        EXPECTED_CONTROL_A_COMMIT,
        EXPECTED_CONTROL_A_PARENT,
        CONTROL_A_SUBJECT,
        CONTROL_A_SURFACE,
    )
    _assert_commit(
        EXPECTED_CONTROL_B_COMMIT,
        EXPECTED_CONTROL_A_COMMIT,
        CONTROL_B_SUBJECT,
        CONTROL_B_SURFACE,
    )
    _assert_commit(
        EXPECTED_CONTROL_C_COMMIT,
        EXPECTED_CONTROL_B_COMMIT,
        CONTROL_C_SUBJECT,
        CONTROL_C_SURFACE,
    )
    print("[OK] Control A/B/C history and exact six-file Control D surface conform")


@dataclass
class _NestedRecord:
    label: str
    api_key: str
    private_path: str


def _payload() -> dict[str, object]:
    cycle: dict[str, object] = {}
    cycle["self"] = cycle
    return {
        "safe": "visible",
        "api-key": SECRET,
        "nested": [
            {"authorization": {"token": SECRET}, "path": WINDOWS_PATH},
            _NestedRecord("record", SECRET, POSIX_PATH),
            RuntimeError(f"{SECRET} at {WINDOWS_PATH}"),
            b"private-binary",
            cycle,
            math.inf,
        ],
    }


def _assert_no_private_material(value: object, *, label: str) -> None:
    serialized = repr(value)
    for forbidden in (
        SECRET,
        WINDOWS_PATH,
        POSIX_PATH,
        "RuntimeError",
        "_PrivateProviderExplosion",
    ):
        _assert(forbidden not in serialized, f"{label}: leaked {forbidden}")


def check_recursive_utility() -> None:
    from framework.public_safety import (
        REDACTED_BINARY,
        REDACTED_CYCLE,
        REDACTED_EXCEPTION,
        REDACTED_NON_FINITE,
        REDACTED_PATH,
        REDACTED_VALUE,
        classify_public_exception,
        public_mapping,
    )

    safe = public_mapping(_payload())
    _assert(isinstance(safe, MappingProxyType), "top-level mapping is mutable")
    _assert(safe["api-key"] == REDACTED_VALUE, "secret-key marker drift")
    _assert(isinstance(safe["nested"], tuple), "nested list is mutable")
    nested = safe["nested"]
    _assert(nested[0]["path"] == REDACTED_PATH, "Windows path marker drift")
    _assert(nested[1]["api_key"] == REDACTED_VALUE, "dataclass secret leaked")
    _assert(nested[1]["private_path"] == REDACTED_PATH, "dataclass path leaked")
    _assert(nested[2] == REDACTED_EXCEPTION, "exception marker drift")
    _assert(nested[3] == REDACTED_BINARY, "binary marker drift")
    _assert(nested[4]["self"] == REDACTED_CYCLE, "cycle marker drift")
    _assert(nested[5] == REDACTED_NON_FINITE, "non-finite marker drift")
    _assert_no_private_material(safe, label="recursive utility")

    cases = (
        (TimeoutError(SECRET), "timeout", True),
        (InterruptedError(SECRET), "request_cancelled", True),
        (PermissionError(SECRET), "authentication_required", False),
        (ConnectionError(SECRET), "provider_unavailable", True),
        (TypeError(SECRET), "invalid_request", False),
        (ValueError(SECRET), "invalid_request", False),
        (RuntimeError(SECRET), "fallback", True),
    )
    for error, code, retryable in cases:
        result = classify_public_exception(
            error,
            fallback_error_code="fallback",
            fallback_safe_message="The operation failed safely.",
            fallback_retryable=True,
        )
        _assert(result.public_error_code == code, f"classifier code drift: {code}")
        _assert(result.retryable is retryable, f"classifier retryability drift: {code}")
        _assert_no_private_material(result, label=f"classifier {code}")

    tree = ast.parse(inspect.getsource(classify_public_exception))
    unsafe_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"str", "repr"}
    ]
    _assert(not unsafe_calls, "common classifier inspects raw exception material")
    print("[OK] recursive utility, redaction markers, and safe classifier conform")


def check_core_consumer_migration() -> None:
    for relative in sorted(MIGRATION_FILES):
        tree = ast.parse(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8"),
            filename=relative,
        )
        imports = [
            alias
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "public_safety"
            and node.level == 1
            for alias in node.names
            if alias.name == "public_mapping"
            and alias.asname == "_recursive_public_mapping"
        ]
        helpers = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_public_mapping"
        ]
        _assert(len(imports) == 1, f"central import drift: {relative}")
        _assert(len(helpers) == 1, f"compatibility helper drift: {relative}")
        returns = [node for node in helpers[0].body if isinstance(node, ast.Return)]
        _assert(len(returns) == 1, f"wrapper return drift: {relative}")
        call = returns[0].value
        _assert(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_recursive_public_mapping",
            f"wrong wrapper delegate: {relative}",
        )

    from framework.motion import MotionCapability
    from framework.realtime_capabilities import RuntimeCapabilityState
    from framework.realtime_session import RealtimeSessionInfo
    from framework.voice_input import VoiceInputRequest
    from framework.voice_input_capability import VoiceInputCapabilities

    payload = _payload()
    consumers = (
        ("RealtimeSessionInfo", RealtimeSessionInfo(public_metadata=payload).public_metadata),
        ("VoiceInputRequest", VoiceInputRequest(metadata=payload).metadata),
        ("VoiceInputCapabilities", VoiceInputCapabilities(public_metadata=payload).public_metadata),
        ("MotionCapability", MotionCapability(public_metadata=payload).public_metadata),
        (
            "RuntimeCapabilityState",
            RuntimeCapabilityState(
                configured=True,
                runtime_available=True,
                fake_runtime=True,
                unavailable_reason=None,
                public_metadata=payload,
            ).public_metadata,
        ),
    )
    for label, metadata in consumers:
        _assert(isinstance(metadata, MappingProxyType), f"{label}: metadata mutable")
        _assert_no_private_material(metadata, label=label)

    print("[OK] five core helpers and representative dependent consumers conform")


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


def _text_session(error: Exception):
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


def check_text_chat_error_safety() -> None:
    from framework.facade import (
        FacadeConfigError,
        FacadeProviderError,
        TextChatSession,
        _classify_text_chat_exception,
        _text_chat_error_event_data,
    )

    error = _PrivateProviderExplosion(f"{SECRET} at {WINDOWS_PATH}")
    session = _text_session(error)
    events = []
    session.on_event(events.append)
    try:
        list(session.ask_stream("hello"))
    except _PrivateProviderExplosion as caught:
        _assert(caught is error, "ask_stream did not re-raise original exception")
    else:
        raise AssertionError("ask_stream exception re-raise was removed")

    error_events = [event for event in events if event.type == "error"]
    _assert(len(error_events) == 1, "streaming path must emit one error event")
    data = error_events[0].data
    _assert(
        set(data)
        == {"public_error_code", "safe_message", "retryable", "public_metadata"},
        f"unsafe or missing event keys: {sorted(data)}",
    )
    _assert("error" not in data and "error_type" not in data, "legacy error fields remain")
    _assert(data["public_error_code"] == "provider_request_failed", "fallback code drift")
    _assert(data["retryable"] is True, "fallback retryability drift")
    _assert_no_private_material(data, label="TextChat error event")

    typed = _text_session(_PrivateProviderExplosion(f"{SECRET} at {POSIX_PATH}")).ask_result("hello")
    _assert(typed.outcome == "failed", "typed result outcome drift")
    _assert(typed.public_error_code == "provider_request_failed", "typed result code drift")
    _assert(typed.retryable is True, "typed result retryability drift")
    _assert_no_private_material(typed, label="TextChat typed result")

    matrix = (
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
    for exception, code, retryable in matrix:
        classification = _classify_text_chat_exception(exception)
        _assert(classification.public_error_code == code, f"TextChat code drift: {code}")
        _assert(classification.retryable is retryable, f"TextChat retryability drift: {code}")
        _assert_no_private_material(classification, label=f"TextChat classifier {code}")

    for function in (
        TextChatSession.ask_stream,
        _classify_text_chat_exception,
        _text_chat_error_event_data,
    ):
        source = inspect.getsource(function)
        for forbidden in (
            "str(exc)",
            "repr(exc)",
            "type(exc).__name__",
            "exc.__class__.__name__",
        ):
            _assert(
                forbidden not in source,
                f"raw exception inspection remains in {function.__name__}: {forbidden}",
            )

    print("[OK] TextChat event/result classification exposes no raw exception material")


def check_public_surface_and_docs() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert(len(PUBLIC_API_NAMES) == len(set(PUBLIC_API_NAMES)), "duplicate root name")
    for name in (
        "public_mapping",
        "sanitize_public_value",
        "classify_public_exception",
        "PublicErrorClassification",
    ):
        _assert(name not in PUBLIC_API_NAMES, f"private safety primitive leaked: {name}")

    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(encoding="utf-8")
    inventory = (
        PROJECT_ROOT / "docs" / "v600_current_source_gap_inventory.md"
    ).read_text(encoding="utf-8")
    public_manifest = (
        PROJECT_ROOT / "scripts" / "smoke_v600_public_api_manifest.py"
    ).read_text(encoding="utf-8")
    version_smoke = (
        PROJECT_ROOT / "scripts" / "smoke_v600_version_metadata.py"
    ).read_text(encoding="utf-8")

    _assert("FW-RT6-2a-D-PUBLIC-SAFETY-ACCEPTANCE:BEGIN" in readme, "README acceptance missing")
    _assert("FW-RT6-2a-D-ACCEPTANCE-SYNC:BEGIN" in tasklist, "tasklist acceptance missing")
    _assert("FW-RT6-2a-D-GAP-RESOLUTION-SYNC:BEGIN" in inventory, "gap sync missing")
    for line in TASK_LINES:
        _assert(line in tasklist, f"task not accepted: {line}")

    shared = (
        "nested credential redaction: PASS",
        "raw exception exposed: False",
        "private path exposed: False",
        "root-public names: 121 / UNCHANGED",
        "next checkpoint: FW-RT6-2b",
        "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED",
    )
    for phrase in shared:
        _assert(phrase in readme, f"README phrase missing: {phrase}")
        _assert(phrase in tasklist, f"tasklist phrase missing: {phrase}")

    for phrase in (
        "G-12 TextChat raw exception string event exposure: RESOLVED",
        "G-13 common recursive public-safety utility: RESOLVED",
        "G-13 all repository metadata consumers migrated: False / INCREMENTAL FOLLOW-UP",
    ):
        _assert(phrase in inventory, f"gap phrase missing: {phrase}")

    for source, label in (
        (public_manifest, "public manifest"),
        (version_smoke, "version metadata"),
    ):
        _assert(
            'print("v600_next_checkpoint: FW-RT6-2b")' in source,
            f"{label} next checkpoint drift",
        )
        _assert(
            "FW-RT6-2a-D-PUBLIC-SAFETY-ACCEPTANCE:BEGIN" in source,
            f"{label} aggregate marker check missing",
        )

    print("[OK] tasklist, README, gap inventory, and shared status gates conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] aggregate public-safety acceptance stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_recursive_utility()
    check_core_consumer_migration()
    check_text_chat_error_safety()
    check_public_surface_and_docs()
    check_import_safety()

    print("v600_rt6_2a_control_d_status: implemented-awaiting-review")
    print("v600_rt6_2a_control_d_exact_change_surface_count: 6")
    print("v600_rt6_2a_control_d_root_public_names: 121 / unchanged")
    print("v600_rt6_2a_control_d_recursive_sanitization: PASS")
    print("v600_rt6_2a_control_d_secret_key_policy_centralized: True")
    print("v600_rt6_2a_control_d_core_helpers_delegated: 5")
    print("v600_rt6_2a_control_d_nested_credential_redaction: PASS")
    print("v600_rt6_2a_control_d_raw_exception_exposed: False")
    print("v600_rt6_2a_control_d_private_path_exposed: False")
    print("v600_rt6_2a_control_d_text_chat_exception_reraise_preserved: True")
    print("v600_rt6_2a_control_d_all_repository_metadata_paths_migrated: False")
    print("v600_rt6_2a_control_d_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2a_next_checkpoint: FW-RT6-2b")
    print("v600_rt6_2a_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-2a aggregate recursive public-safety acceptance passed")


if __name__ == "__main__":
    main()
