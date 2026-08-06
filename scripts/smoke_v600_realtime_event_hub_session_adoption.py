"""FW-RT6-2b Control B RealtimeSession event-hub adoption smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or host-application repository operation occurs.
"""

from __future__ import annotations

import ast
from dataclasses import fields
import inspect
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "cee3f68ec3254a8d99a7f4c0e1f911deb1f3496f"
EXPECTED_BASELINE_PARENT = "89c0ba7ccf150658c5bace612e68bce876db4223"
EXPECTED_BASELINE_SUBJECT = "feat/test: add realtime event hub primitives"
EXPECTED_BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_event_hub.py",
    "scripts/smoke_v600_realtime_event_hub_primitives.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_event_hub_session_adoption.py",
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

CANONICAL_TURN_TYPES = (
    "realtime.turn.started",
    "realtime.listening.started",
    "realtime.listening.completed",
    "realtime.transcript.final",
    "realtime.response.started",
    "realtime.response.completed",
    "realtime.synthesis.started",
    "realtime.synthesis.completed",
    "realtime.turn.completed",
)
LEGACY_TURN_TYPES = (
    "realtime.turn.started",
    "realtime.voice_input.started",
    "realtime.voice_input.completed",
    "realtime.text_chat.started",
    "realtime.text_chat.completed",
    "realtime.voice_output.started",
    "realtime.voice_output.completed",
    "realtime.turn.completed",
)


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
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).splitlines()
        if line.strip()
    }


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^")
        == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == EXPECTED_BASELINE_SURFACE,
        "accepted Control A surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted Control A baseline and exact five-file Control B surface conform")


def check_source_adoption() -> None:
    source_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    _assert(
        "from .realtime_event_hub import RealtimeEventHub" in source,
        "RealtimeEventHub import missing",
    )
    for removed in (
        "self._callbacks",
        "self._legacy_callbacks",
        "self._next_event_sequence",
        "def _allocate_event_sequence",
    ):
        _assert(removed not in source, f"legacy callback path remains: {removed}")

    session_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "RealtimeSession"
    )
    methods = {
        node.name: node
        for node in session_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for required in (
        "on_event",
        "on_legacy_event",
        "off_event",
        "_build_event_overflow",
        "_transition",
    ):
        _assert(required in methods, f"session method missing: {required}")

    transition_source = ast.get_source_segment(source, methods["_transition"]) or ""
    _assert("self._event_hub.emit(" in transition_source, "transition does not use event hub")
    _assert("overflow_event_factory=overflow_event_factory" in transition_source, "typed overflow hook missing")
    _assert("legacy_projector=lambda emitted: emitted.to_v5()" in transition_source, "legacy projector drift")

    overflow_source = ast.get_source_segment(source, methods["_build_event_overflow"]) or ""
    for phrase in (
        "RealtimeEventType.EVENT_OVERFLOW",
        "DiagnosticEventPayload(",
        'code="event_history_overflow"',
        'drop_reason="bounded_history_capacity"',
    ):
        _assert(phrase in overflow_source, f"typed overflow source missing: {phrase}")

    print("[OK] RealtimeSession source delegates callback, sequence, history, and overflow work to the hub")


def check_tokens_callback_isolation_and_order() -> None:
    import framework

    session = framework.create_realtime_session()
    canonical = []
    legacy = []

    def broken(_event) -> None:
        raise RuntimeError("private subscriber failure")

    broken_token = session.on_event(broken)
    canonical_token = session.on_event(canonical.append)
    legacy_token = session.on_legacy_event(legacy.append)

    for token in (broken_token, canonical_token, legacy_token):
        _assert(type(token) is str, "callback registration token must be a plain str")
        _assert(token.startswith("fw_event_sub_"), "callback token prefix drift")

    result = session.run_turn(input_text="first")
    _assert(result.is_completed, "callback exception broke the turn")
    _assert(
        tuple(event.type.value for event in canonical) == CANONICAL_TURN_TYPES,
        "canonical completed-turn order drift",
    )
    _assert(
        tuple(event.type.value for event in legacy) == LEGACY_TURN_TYPES,
        "legacy completed-turn order drift",
    )
    _assert(
        [int(event.sequence) for event in canonical] == list(range(1, 10)),
        "first turn sequence drift",
    )

    diagnostics = session.event_diagnostics
    _assert(isinstance(diagnostics, MappingProxyType), "event diagnostics mutable")
    _assert(diagnostics["callback_error_count"] == 9, "callback error count drift")
    _assert(diagnostics["subscriber_count"] == 3, "subscriber count drift")
    _assert(diagnostics["history_limit"] == 64, "history limit drift")
    _assert(session.off_event(broken_token) is True, "broken callback removal failed")
    _assert(session.off_event(broken_token) is False, "duplicate removal should be false")
    _assert(session.off_event(legacy_token) is True, "legacy callback removal failed")

    second = session.run_turn(input_text="second")
    _assert(second.is_completed, "second turn failed")
    _assert(len(canonical) == 18, "remaining canonical callback delivery drift")
    _assert(len(legacy) == 8, "removed legacy callback received future events")
    _assert(
        [int(event.sequence) for event in canonical] == list(range(1, 19)),
        "session-lifetime sequence drift",
    )
    _assert(
        session.event_diagnostics["callback_error_count"] == 9,
        "removed callback continued failing",
    )
    _assert(
        session.event_diagnostics["subscriber_count"] == 1,
        "post-removal subscriber count drift",
    )
    _assert(session.off_event(canonical_token) is True, "canonical removal failed")

    history = session.event_history
    _assert(type(history) is tuple, "event history must be an immutable tuple")
    _assert(len(history) == 18, "non-overflow history count drift")
    print("[OK] callback tokens, exception isolation, ordering, and session-lifetime sequence conform")


def check_typed_overflow() -> None:
    import framework
    from framework.realtime_event_payloads import DiagnosticEventPayload

    session = framework.create_realtime_session()
    canonical = []
    legacy = []
    session.on_event(canonical.append)
    session.on_legacy_event(legacy.append)

    for index in range(8):
        result = session.run_turn(input_text=f"turn-{index}")
        _assert(result.is_completed, f"overflow setup turn failed: {index}")

    _assert(len(canonical) == 80, "canonical overflow delivery count drift")
    _assert(
        [int(event.sequence) for event in canonical] == list(range(1, 81)),
        "overflow sequence is not gap-free and monotonic",
    )
    _assert(len(legacy) == 64, "overflow diagnostic entered legacy projection")

    overflow_events = [
        event
        for event in canonical
        if event.type is framework.RealtimeEventType.EVENT_OVERFLOW
    ]
    _assert(len(overflow_events) == 8, "typed overflow event count drift")
    _assert(
        all(isinstance(event.payload, DiagnosticEventPayload) for event in overflow_events),
        "overflow event payload type drift",
    )
    _assert(
        all(event.to_v5() is None for event in overflow_events),
        "overflow event unexpectedly maps to v5",
    )
    _assert(
        all(event.payload.code == "event_history_overflow" for event in overflow_events),
        "overflow diagnostic code drift",
    )
    _assert(
        all(event.payload.drop_reason == "bounded_history_capacity" for event in overflow_events),
        "overflow drop reason drift",
    )
    _assert(
        int(overflow_events[-1].payload.dropped_sequence) == 15,
        "last overflow first-dropped sequence drift",
    )
    _assert(
        overflow_events[-1].payload.overflow_count == 16,
        "cumulative overflow count drift",
    )

    history = session.event_history
    _assert(len(history) == 64, "bounded history size drift")
    _assert(
        [int(event.sequence) for event in history] == list(range(17, 81)),
        "bounded history retained range drift",
    )
    diagnostics = session.event_diagnostics
    _assert(diagnostics["emitted_event_count"] == 80, "emitted event count drift")
    _assert(diagnostics["history_overflow_count"] == 16, "history overflow count drift")
    _assert(diagnostics["callback_error_count"] == 0, "healthy callbacks recorded errors")
    print("[OK] RealtimeSession emits typed, sequenced, non-legacy overflow diagnostics")


def check_public_compatibility_and_docs() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")

    expected_factory_parameters = (
        "project_root",
        "public_metadata",
        "real_runtime_enabled",
    )
    _assert(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == expected_factory_parameters,
        "create_realtime_session signature drift",
    )

    event_fields = tuple(field.name for field in fields(framework.RealtimeEvent))
    _assert(
        event_fields
        == (
            "type",
            "state",
            "previous_state",
            "turn_id",
            "session_id",
            "boundary",
            "public_error_code",
            "safe_message",
            "retryable",
            "public_metadata",
            "sequence",
            "generation_id",
            "phase",
            "payload",
            "terminal",
            "timestamp",
            "monotonic_timestamp",
        ),
        "RealtimeEvent public model drift",
    )

    session = framework.create_realtime_session()
    _assert(hasattr(session, "event_history"), "event_history property missing")
    _assert(hasattr(session, "event_diagnostics"), "event_diagnostics property missing")
    _assert(callable(session.off_event), "off_event method missing")

    for relative in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-2b-B-REALTIME-SESSION-HUB-ADOPTION:BEGIN" in text,
            f"Control B marker missing: {relative}",
        )
        for phrase in (
            "callback exception breaks turn: False",
            "typed EVENT_OVERFLOW adopted: True",
            "post-close active-event rejection: DEFERRED / Control C",
        ):
            _assert(phrase in text, f"Control B doc phrase missing: {phrase}")

    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_event_hub_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "FW-RT6-2b Control B — RealtimeSession adoption",
        "history limit:",
        "64",
        "legacy projection:",
        "None",
        "session close seals hub:",
        "False / DEFERRED TO CONTROL C",
    ):
        _assert(phrase in contract, f"event-hub contract phrase missing: {phrase}")

    print("[OK] 121-name root API, existing event/factory contracts, and Control B docs conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] RealtimeSession hub adoption stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_source_adoption()
    check_tokens_callback_isolation_and_order()
    check_typed_overflow()
    check_public_compatibility_and_docs()
    check_import_safety()

    print("v600_rt6_2b_control_b_status: implemented-awaiting-review")
    print("v600_rt6_2b_control_b_exact_change_surface_count: 5")
    print("v600_rt6_2b_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_2b_control_b_realtime_event_model_changed: False")
    print("v600_rt6_2b_control_b_factory_signature_changed: False")
    print("v600_rt6_2b_control_b_callback_token_adopted: True")
    print("v600_rt6_2b_control_b_callback_exception_breaks_turn: False")
    print("v600_rt6_2b_control_b_bounded_history_limit: 64")
    print("v600_rt6_2b_control_b_typed_event_overflow_adopted: True")
    print("v600_rt6_2b_control_b_overflow_v5_projection: None")
    print("v600_rt6_2b_control_b_post_close_active_event_rejection: deferred-control-c")
    print("v600_rt6_2b_control_b_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2b_next_control: FW-RT6-2b Control C")
    print("v600_rt6_2b_next_control_authorized: False")
    print("[OK] FW-RT6-2b Control B RealtimeSession event-hub adoption passed")


if __name__ == "__main__":
    main()
