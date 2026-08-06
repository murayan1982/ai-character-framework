"""FW-RT6-2b Control C close/concurrent-operation hardening smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or host-application repository operation occurs.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "ee896aad3c9f6d38521c3da08505e77f0c60c1c0"
EXPECTED_BASELINE_PARENT = "cee3f68ec3254a8d99a7f4c0e1f911deb1f3496f"
EXPECTED_BASELINE_SUBJECT = "refactor/test: adopt realtime event hub"
EXPECTED_BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_event_hub_session_adoption.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_event_hub_close_hardening.py",
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
        "accepted Control B surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control C surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted Control B baseline and exact seven-file Control C surface conform")


def check_source_hardening() -> None:
    source_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))

    for phrase in (
        "from contextlib import contextmanager",
        "from threading import RLock",
        "self._operation_lock = RLock()",
        "self._operation_depth = 0",
        "self._close_requested = False",
        "def _serialized_operation",
        "def _close_now",
        "_allow_closed_event: bool = False",
        "self._event_hub.close()",
    ):
        _assert(phrase in source, f"session hardening source missing: {phrase}")

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
        "emit_created",
        "_emit_created_serialized",
        "run_turn",
        "_run_turn_serialized",
        "interrupt",
        "_interrupt_serialized",
        "flush_output",
        "_flush_output_serialized",
        "decide_barge_in",
        "_decide_barge_in_serialized",
        "close",
        "_close_now",
    ):
        _assert(required in methods, f"serialized method missing: {required}")

    close_source = ast.get_source_segment(source, methods["_close_now"]) or ""
    _assert(
        close_source.index("self._closed = True")
        < close_source.index("RealtimeEventType.SESSION_CLOSED")
        < close_source.index("self._event_hub.close()"),
        "close mark/event/seal order drift",
    )

    run_source = ast.get_source_segment(source, methods["_run_turn_serialized"]) or ""
    _assert(
        "if self._closed or self._close_requested:" in run_source,
        "closed/pending run_turn guard missing",
    )
    _assert(
        "RealtimeEventType.TURN_REJECTED" not in run_source.split(
            "if self._closed or self._close_requested:", 1
        )[1].split("self._active_turn_id", 1)[0],
        "post-close run_turn still emits rejection event",
    )

    interrupt_source = ast.get_source_segment(
        source,
        methods["_interrupt_serialized"],
    ) or ""
    closed_interrupt_block = interrupt_source.split(
        "if self._closed or self._close_requested:",
        1,
    )[1].split("no_active_turn", 1)[0]
    _assert("_transition(" not in closed_interrupt_block, "closed interrupt still emits")

    flush_source = ast.get_source_segment(
        source,
        methods["_flush_output_serialized"],
    ) or ""
    closed_flush_block = flush_source.split(
        "if self._closed or self._close_requested:",
        1,
    )[1].split("self._transition(", 1)[0]
    _assert("_transition(" not in closed_flush_block, "closed flush still emits")

    print("[OK] RealtimeSession source has serialized operation and post-close rejection hardening")


def _expect_session_closed_error(action, framework, label: str) -> None:
    try:
        action()
    except framework.LifecycleTransitionError as exc:
        _assert(
            exc.code is framework.LifecycleTransitionErrorCode.SESSION_CLOSED,
            f"{label}: lifecycle code drift",
        )
    else:
        raise AssertionError(f"{label}: closed operation was accepted")


def check_close_seals_and_post_close_is_silent() -> None:
    import framework

    session = framework.create_realtime_session()
    events = []
    legacy_events = []
    canonical_token = session.on_event(events.append)
    legacy_token = session.on_legacy_event(legacy_events.append)

    result = session.run_turn(input_text="before-close")
    _assert(result.is_completed, "pre-close turn failed")
    session.close()
    session.close()
    session.dispose()

    _assert(session.is_closed, "session did not close")
    _assert(session.state is framework.RealtimeState.CLOSED, "closed state drift")
    _assert(session.phase is None, "closed phase must be None")
    _assert(events[-1].type is framework.RealtimeEventType.SESSION_CLOSED, "close event missing")
    _assert(
        legacy_events[-1].type is framework.RealtimeEventType.SESSION_CLOSED,
        "legacy close event missing",
    )
    _assert(
        sum(event.type is framework.RealtimeEventType.SESSION_CLOSED for event in events)
        == 1,
        "SESSION_CLOSED emitted more than once",
    )

    event_count = len(events)
    legacy_count = len(legacy_events)
    history_count = len(session.event_history)

    closed_turn = session.run_turn(input_text="after-close")
    _assert(closed_turn.outcome is framework.TurnOutcome.CLOSED, "closed turn result drift")
    closed_interrupt = session.interrupt()
    _assert(
        closed_interrupt.outcome is framework.InterruptOutcome.ALREADY_CLOSED,
        "closed interrupt result drift",
    )
    closed_flush = session.flush_output()
    _assert(
        closed_flush.outcome is framework.OutputFlushOutcome.CLOSED,
        "closed flush result drift",
    )
    closed_barge = session.decide_barge_in()
    _assert(not closed_barge.accepted, "closed barge-in was accepted")

    _expect_session_closed_error(session.emit_created, framework, "emit_created")
    _expect_session_closed_error(
        lambda: session.set_barge_in_policy(framework.BargeInPolicy.hard_cancel()),
        framework,
        "set_barge_in_policy",
    )
    _expect_session_closed_error(
        lambda: session.on_event(lambda _event: None),
        framework,
        "on_event",
    )
    _expect_session_closed_error(
        lambda: session.on_legacy_event(lambda _event: None),
        framework,
        "on_legacy_event",
    )

    _assert(len(events) == event_count, "post-close canonical event emitted")
    _assert(len(legacy_events) == legacy_count, "post-close legacy event emitted")
    _assert(len(session.event_history) == history_count, "post-close history changed")
    _assert(session.event_diagnostics["subscriber_count"] == 0, "close retained subscribers")
    _assert(session.off_event(canonical_token) is False, "cleared canonical token remained")
    _assert(session.off_event(legacy_token) is False, "cleared legacy token remained")
    print("[OK] SESSION_CLOSED is once-only, hub is sealed, and post-close operations emit nothing")


def check_reentrant_close_is_deferred() -> None:
    import framework

    session = framework.create_realtime_session()
    events = []
    close_requested = False

    def callback(event) -> None:
        nonlocal close_requested
        events.append(event)
        if (
            event.type is framework.RealtimeEventType.TURN_STARTED
            and not close_requested
        ):
            close_requested = True
            session.close()

    session.on_event(callback)
    result = session.run_turn(input_text="reentrant-close")

    _assert(result.is_completed, "reentrant close interrupted admitted turn")
    _assert(session.is_closed, "deferred reentrant close did not finish")
    _assert(
        [event.type for event in events[:9]]
        == [
            framework.RealtimeEventType.TURN_STARTED,
            framework.RealtimeEventType.LISTENING_STARTED,
            framework.RealtimeEventType.LISTENING_COMPLETED,
            framework.RealtimeEventType.TRANSCRIPT_FINAL,
            framework.RealtimeEventType.RESPONSE_STARTED,
            framework.RealtimeEventType.RESPONSE_COMPLETED,
            framework.RealtimeEventType.SYNTHESIS_STARTED,
            framework.RealtimeEventType.SYNTHESIS_COMPLETED,
            framework.RealtimeEventType.TURN_COMPLETED,
        ],
        "reentrant close changed admitted-turn event group",
    )
    _assert(
        events[-1].type is framework.RealtimeEventType.SESSION_CLOSED,
        "deferred close event missing",
    )
    _assert(
        [int(event.sequence) for event in events]
        == list(range(1, len(events) + 1)),
        "reentrant close sequence drift",
    )
    print("[OK] callback reentrant close is deferred until the outer event group completes")


def check_concurrent_operations_do_not_interleave() -> None:
    import framework

    session = framework.create_realtime_session()
    events = []
    session.on_event(events.append)
    results = []
    failures = []

    def run(label: str) -> None:
        try:
            results.append(session.run_turn(input_text=label))
        except Exception as exc:  # test-only capture
            failures.append(exc)

    first = Thread(target=run, args=("one",))
    second = Thread(target=run, args=("two",))
    first.start()
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)

    _assert(not first.is_alive() and not second.is_alive(), "concurrent turn thread hung")
    _assert(not failures, f"concurrent turn failed: {failures!r}")
    _assert(len(results) == 2 and all(result.is_completed for result in results), "turn results drift")
    _assert(len(events) == 18, "concurrent turn event count drift")
    _assert(
        [int(event.sequence) for event in events] == list(range(1, 19)),
        "concurrent operation sequence drift",
    )
    first_group = [event.type for event in events[:9]]
    second_group = [event.type for event in events[9:18]]
    _assert(first_group == second_group, "concurrent operation event groups interleaved")
    print("[OK] concurrent event-producing operations execute as complete non-interleaved groups")


def check_concurrent_close_waits_for_operation_boundary() -> None:
    import framework

    session = framework.create_realtime_session()
    entered_callback = Event()
    release_callback = Event()
    events = []
    failures = []

    def callback(event) -> None:
        events.append(event)
        if event.type is framework.RealtimeEventType.TURN_STARTED:
            entered_callback.set()
            if not release_callback.wait(timeout=5):
                raise RuntimeError("test callback release timeout")

    session.on_event(callback)

    def run_turn() -> None:
        try:
            session.run_turn(input_text="concurrent-close")
        except Exception as exc:
            failures.append(exc)

    def close_session() -> None:
        try:
            session.close()
        except Exception as exc:
            failures.append(exc)

    turn_thread = Thread(target=run_turn)
    close_thread = Thread(target=close_session)
    turn_thread.start()
    _assert(entered_callback.wait(timeout=5), "turn callback was not reached")
    close_thread.start()

    _assert(close_thread.is_alive(), "concurrent close did not wait for operation boundary")
    release_callback.set()
    turn_thread.join(timeout=5)
    close_thread.join(timeout=5)

    _assert(not turn_thread.is_alive() and not close_thread.is_alive(), "concurrent close thread hung")
    _assert(not failures, f"concurrent close failure: {failures!r}")
    _assert(session.is_closed, "concurrent close did not close session")
    _assert(
        events[-2].type is framework.RealtimeEventType.TURN_COMPLETED
        and events[-1].type is framework.RealtimeEventType.SESSION_CLOSED,
        "concurrent close interleaved with active turn",
    )
    count_after_close = len(events)
    _assert(session.run_turn(input_text="late").outcome is framework.TurnOutcome.CLOSED, "late result drift")
    _assert(len(events) == count_after_close, "late event accepted after concurrent close")
    print("[OK] concurrent close waits for the active operation and seals later events")


def check_public_compatibility_and_docs() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")

    for relative in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-2b-C-CLOSE-CONCURRENCY-HARDENING:BEGIN" in text,
            f"Control C marker missing: {relative}",
        )
        for phrase in (
            "reentrant close deferred: True",
            "concurrent operation groups interleave: False",
            "close後active event: False",
        ):
            _assert(phrase in text, f"Control C doc phrase missing: {phrase}")

    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_event_hub_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "FW-RT6-2b Control C — close and concurrent-operation boundary",
        "callback reentrant close:",
        "deferred until the outer operation exits",
        "post-close active event:",
        "False",
    ):
        _assert(phrase in contract, f"Control C contract phrase missing: {phrase}")

    for gate in (
        "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
        "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    ):
        text = (PROJECT_ROOT / gate).read_text(encoding="utf-8")
        _assert(
            "post-close event count should remain unchanged" in text,
            f"v5.2 post-close gate sync missing: {gate}",
        )

    print("[OK] root-public compatibility, Control C docs, and v5.2 close gates conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] close/concurrent-operation hardening stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_source_hardening()
    check_close_seals_and_post_close_is_silent()
    check_reentrant_close_is_deferred()
    check_concurrent_operations_do_not_interleave()
    check_concurrent_close_waits_for_operation_boundary()
    check_public_compatibility_and_docs()
    check_import_safety()

    print("v600_rt6_2b_control_c_status: implemented-awaiting-review")
    print("v600_rt6_2b_control_c_exact_change_surface_count: 7")
    print("v600_rt6_2b_control_c_root_public_names: 121 / unchanged")
    print("v600_rt6_2b_control_c_operation_lock: RLock")
    print("v600_rt6_2b_control_c_reentrant_close_deferred: True")
    print("v600_rt6_2b_control_c_concurrent_operation_groups_interleave: False")
    print("v600_rt6_2b_control_c_session_closed_event_count: 1")
    print("v600_rt6_2b_control_c_event_hub_sealed_after_close: True")
    print("v600_rt6_2b_control_c_post_close_active_event: False")
    print("v600_rt6_2b_control_c_terminal_registry: deferred-FW-RT6-2c")
    print("v600_rt6_2b_control_c_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2b_next_control: FW-RT6-2b Control D")
    print("v600_rt6_2b_next_control_authorized: False")
    print("[OK] FW-RT6-2b Control C close/concurrent-operation hardening passed")


if __name__ == "__main__":
    main()
