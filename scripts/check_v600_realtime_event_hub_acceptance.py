"""FW-RT6-2b Control D aggregate realtime event-hub acceptance check.

This check is repository-safe and offline-safe. It validates the accepted
Control A/B/C commit chain, exact Control D docs/test-only surface, public
contract compatibility, event-hub/session source facts, aggregate documentation,
and the next-checkpoint boundary without provider/runtime execution.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "d12e562a0c0b0111386776d50286b1a4cbdf54d2"
EXPECTED_BASELINE_PARENT = "ee896aad3c9f6d38521c3da08505e77f0c60c1c0"
EXPECTED_BASELINE_SUBJECT = "fix/test: seal realtime events after close"

CONTROL_A = "cee3f68ec3254a8d99a7f4c0e1f911deb1f3496f"
CONTROL_A_PARENT = "89c0ba7ccf150658c5bace612e68bce876db4223"
CONTROL_A_SUBJECT = "feat/test: add realtime event hub primitives"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_event_hub.py",
    "scripts/smoke_v600_realtime_event_hub_primitives.py",
}

CONTROL_B = "ee896aad3c9f6d38521c3da08505e77f0c60c1c0"
CONTROL_B_PARENT = CONTROL_A
CONTROL_B_SUBJECT = "refactor/test: adopt realtime event hub"
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_event_hub_session_adoption.py",
}

CONTROL_C = EXPECTED_BASELINE
CONTROL_C_PARENT = CONTROL_B
CONTROL_C_SUBJECT = EXPECTED_BASELINE_SUBJECT
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v520_interrupt_output_control_public_contract_conformance_gate.py",
    "scripts/smoke_v520_realtime_public_contract_conformance_gate.py",
    "scripts/smoke_v600_realtime_event_hub_close_hardening.py",
}

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_event_hub_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
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


def _check_commit(
    *,
    commit: str,
    parent: str,
    subject: str,
    surface: set[str],
    label: str,
) -> None:
    _assert(_git("rev-parse", f"{commit}^") == parent, f"{label} parent drift")
    _assert(
        _git("show", "-s", "--format=%s", commit) == subject,
        f"{label} subject drift",
    )
    _assert(_commit_surface(commit) == surface, f"{label} surface drift")


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control D surface: {sorted(_changed_paths())}",
    )

    _check_commit(
        commit=CONTROL_A,
        parent=CONTROL_A_PARENT,
        subject=CONTROL_A_SUBJECT,
        surface=CONTROL_A_SURFACE,
        label="Control A",
    )
    _check_commit(
        commit=CONTROL_B,
        parent=CONTROL_B_PARENT,
        subject=CONTROL_B_SUBJECT,
        surface=CONTROL_B_SURFACE,
        label="Control B",
    )
    _check_commit(
        commit=CONTROL_C,
        parent=CONTROL_C_PARENT,
        subject=CONTROL_C_SUBJECT,
        surface=CONTROL_C_SURFACE,
        label="Control C",
    )

    print("[OK] accepted Control A/B/C commit chain and exact six-file Control D surface conform")


def check_runtime_source_contract() -> None:
    hub_path = PROJECT_ROOT / "framework" / "realtime_event_hub.py"
    session_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    hub_source = hub_path.read_text(encoding="utf-8")
    session_source = session_path.read_text(encoding="utf-8")
    ast.parse(hub_source, filename=str(hub_path))
    ast.parse(session_source, filename=str(session_path))

    for phrase in (
        "class EventSubscriptionToken(str):",
        "history_limit: int = 64",
        "callback_error_count",
        "slow_callback_count",
        "history_overflow_count",
        "def subscribe(",
        "def unsubscribe(",
        "def emit(",
        "def close(",
        "self._pending",
        "self._dispatching",
        "overflow_event_factory",
    ):
        _assert(phrase in hub_source, f"event-hub source missing: {phrase}")

    for phrase in (
        "self._event_hub = RealtimeEventHub[RealtimeEvent]()",
        "def event_history",
        "def event_diagnostics",
        "def on_event",
        "def on_legacy_event",
        "def off_event",
        "RealtimeEventType.EVENT_OVERFLOW",
        'code="event_history_overflow"',
        "self._operation_lock = RLock()",
        "def _serialized_operation",
        "def _close_now",
        "self._event_hub.close()",
    ):
        _assert(phrase in session_source, f"RealtimeSession source missing: {phrase}")

    _assert("self._callbacks: list" not in session_source, "legacy session callback list remains")
    _assert("self._next_event_sequence" not in session_source, "legacy session sequence allocator remains")
    print("[OK] accepted event-hub, session adoption, typed overflow, and close source facts conform")


def check_runtime_behavior() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")

    session = framework.create_realtime_session()
    events = []
    legacy_events = []

    def broken(_event) -> None:
        raise RuntimeError("subscriber failure must be isolated")

    broken_token = session.on_event(broken)
    canonical_token = session.on_event(events.append)
    legacy_token = session.on_legacy_event(legacy_events.append)

    _assert(type(broken_token) is str, "broken callback token is not plain str")
    _assert(type(canonical_token) is str, "canonical callback token is not plain str")
    _assert(type(legacy_token) is str, "legacy callback token is not plain str")

    for index in range(8):
        result = session.run_turn(input_text=f"aggregate-{index}")
        _assert(result.is_completed, f"turn failed at index {index}")

    _assert(
        [int(event.sequence) for event in events]
        == list(range(1, len(events) + 1)),
        "event sequence is not monotonic and gap-free",
    )
    _assert(
        any(event.type is framework.RealtimeEventType.EVENT_OVERFLOW for event in events),
        "typed overflow event was not emitted",
    )
    _assert(
        all(
            event.to_v5() is None
            for event in events
            if event.type is framework.RealtimeEventType.EVENT_OVERFLOW
        ),
        "overflow event unexpectedly projected to v5",
    )
    diagnostics = session.event_diagnostics
    _assert(diagnostics["history_limit"] == 64, "history limit drift")
    _assert(diagnostics["callback_error_count"] > 0, "callback errors were not isolated/accounted")
    _assert(diagnostics["history_overflow_count"] > 0, "overflow was silent")
    _assert(len(session.event_history) == 64, "bounded event history size drift")

    _assert(session.off_event(broken_token) is True, "broken token removal failed")
    session.close()
    session.close()

    _assert(
        sum(event.type is framework.RealtimeEventType.SESSION_CLOSED for event in events)
        == 1,
        "SESSION_CLOSED was not exactly once",
    )
    event_count = len(events)
    legacy_count = len(legacy_events)
    history_count = len(session.event_history)

    _assert(
        session.run_turn(input_text="after-close").outcome is framework.TurnOutcome.CLOSED,
        "closed turn result drift",
    )
    _assert(
        session.interrupt().outcome is framework.InterruptOutcome.ALREADY_CLOSED,
        "closed interrupt result drift",
    )
    _assert(
        session.flush_output().outcome is framework.OutputFlushOutcome.CLOSED,
        "closed flush result drift",
    )
    _assert(not session.decide_barge_in().accepted, "closed barge-in was accepted")
    _assert(len(events) == event_count, "post-close canonical event emitted")
    _assert(len(legacy_events) == legacy_count, "post-close legacy event emitted")
    _assert(len(session.event_history) == history_count, "post-close history changed")
    _assert(session.event_diagnostics["subscriber_count"] == 0, "close retained subscribers")
    _assert(session.off_event(canonical_token) is False, "cleared canonical token remained")
    _assert(session.off_event(legacy_token) is False, "cleared legacy token remained")

    print("[OK] monotonic sequence, callback isolation, bounded history, overflow, and post-close behavior conform")


def check_aggregate_docs() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(encoding="utf-8")
    gaps = (
        PROJECT_ROOT / "docs" / "v600_current_source_gap_inventory.md"
    ).read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_event_hub_contract.md"
    ).read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-2b-D-EVENT-HUB-ACCEPTANCE:BEGIN",
        "next checkpoint: FW-RT6-2c",
        "asynchronous subscriber queue: NOT CLAIMED",
    ):
        _assert(marker in readme, f"README aggregate phrase missing: {marker}")

    for item in (
        "per-session monotonic sequence generatorを追加する。",
        "callback registration/unregistration tokenを追加する。",
        "callback exceptionをruntime failureから隔離する。",
        "bounded event historyを追加する。",
        "slow subscriber policyを固定する。",
        "overflow event/diagnosticsを追加する。",
        "concurrent emission lockを追加する。",
        "close後event rejectionを実装する。",
    ):
        _assert(f"- [x] {item}" in tasklist, f"task not accepted: {item}")
        _assert(f"- [ ] {item}" not in tasklist, f"task remains open: {item}")

    for phrase in (
        "FW-RT6-2b-D-ACCEPTANCE-SYNC:BEGIN",
        "Control A event-hub primitives: ACCEPTED",
        "Control B RealtimeSession hub adoption: ACCEPTED",
        "Control C close/concurrent-operation hardening: ACCEPTED",
        "next checkpoint: FW-RT6-2c",
    ):
        _assert(phrase in tasklist, f"tasklist aggregate phrase missing: {phrase}")

    for phrase in (
        "FW-RT6-2b-D-GAP-RESOLUTION-SYNC:BEGIN",
        "G-03 session-local monotonic event sequencing: RESOLVED",
        "G-03 bounded canonical event history: RESOLVED / LIMIT 64",
        "G-03 non-silent typed overflow diagnostics: RESOLVED",
        "G-03 close-boundary event rejection: RESOLVED",
        "G-04 per-session terminal registry: UNRESOLVED / FW-RT6-2c",
        "G-05 generation stale-result rejection: UNRESOLVED / FW-RT6-2d",
    ):
        _assert(phrase in gaps, f"gap sync phrase missing: {phrase}")

    for marker in (
        "FW-RT6-2b Control A",
        "FW-RT6-2b Control B — RealtimeSession adoption",
        "FW-RT6-2b Control C — close and concurrent-operation boundary",
    ):
        _assert(marker in contract, f"event-hub contract marker missing: {marker}")

    print("[OK] README, tasklist, gap inventory, and event-hub contract aggregate truthfulness conform")


def check_updated_common_smokes() -> None:
    public_manifest = (
        PROJECT_ROOT / "scripts" / "smoke_v600_public_api_manifest.py"
    ).read_text(encoding="utf-8")
    version_metadata = (
        PROJECT_ROOT / "scripts" / "smoke_v600_version_metadata.py"
    ).read_text(encoding="utf-8")

    for source, label in (
        (public_manifest, "public API manifest"),
        (version_metadata, "version metadata"),
    ):
        for phrase in (
            "FW-RT6-2b-D-EVENT-HUB-ACCEPTANCE:BEGIN",
            "FW-RT6-2b-D-ACCEPTANCE-SYNC:BEGIN",
            "FW-RT6-2b-D-GAP-RESOLUTION-SYNC:BEGIN",
            "FW-RT6-2c",
        ):
            _assert(phrase in source, f"{label} smoke missing: {phrase}")

    print("[OK] common public API/version smokes advance the accepted checkpoint to FW-RT6-2c")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] aggregate acceptance check stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_runtime_source_contract()
    check_runtime_behavior()
    check_aggregate_docs()
    check_updated_common_smokes()
    check_import_safety()

    print("v600_rt6_2b_control_d_status: implemented-awaiting-review")
    print("v600_rt6_2b_control_d_exact_change_surface_count: 6")
    print("v600_rt6_2b_control_d_root_public_names: 121 / unchanged")
    print("v600_rt6_2b_control_a_status: accepted")
    print("v600_rt6_2b_control_b_status: accepted")
    print("v600_rt6_2b_control_c_status: accepted")
    print("v600_rt6_2b_sequence_monotonic: PASS")
    print("v600_rt6_2b_callback_exception_breaks_turn: False")
    print("v600_rt6_2b_bounded_event_history_limit: 64")
    print("v600_rt6_2b_silent_overflow: False")
    print("v600_rt6_2b_post_close_active_event: False")
    print("v600_rt6_2b_async_subscriber_queue_claimed: False")
    print("v600_rt6_2b_terminal_registry: deferred-FW-RT6-2c")
    print("v600_rt6_2b_generation_stale_guard: deferred-FW-RT6-2d")
    print("v600_rt6_2b_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2b_drc_repository_accessed_or_changed: False")
    print("v600_next_checkpoint: FW-RT6-2c")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-2b Control D aggregate realtime event-hub acceptance passed")


if __name__ == "__main__":
    main()
