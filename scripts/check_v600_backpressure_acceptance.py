"""FW-RT6-12b Control C aggregate backpressure acceptance gate.

The gate is offline-safe. It aggregates accepted Control A/B contracts and
tests without changing runtime, provider, application, or queue ownership.
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "54291405a817afddbef927b0e0a3173d8937772c"
EXPECTED_SURFACE = {
    "docs/v600_tasklist.md",
    "scripts/check_v600_backpressure_acceptance.py",
}
EXPECTED_TASKS = (
    "audio input queue backpressureを実装する。",
    "response delta subscriber backpressureを実装する。",
    "voice output queue backpressureを実装する。",
    "max in-flightをcapability化する。",
    "retryable rejectionを実装する。",
    "silent dropを禁止する。",
)
EXPECTED_CONTRACT_EXPORTS = (
    "BACKPRESSURE_API_VERSION",
    "BackpressureBoundary",
    "BackpressureState",
    "BackpressureOverflowPolicy",
    "BackpressureOperationKind",
    "BackpressureRejectionCode",
    "BackpressureCapability",
    "BackpressureSnapshot",
    "BackpressureAdmission",
    "BackpressureAdmissionResult",
    "BackpressureOverflowEvent",
    "BackpressureControlResult",
)
EXPECTED_BOUNDARIES = (
    "audio_input",
    "response_delta",
    "voice_output",
    "event_subscriber",
)
FORBIDDEN_RUNTIME_MODULES = {
    "openai",
    "elevenlabs",
    "pyvts",
    "pyaudio",
    "sounddevice",
    "websocket",
    "websockets",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], *, capture: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=capture,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (result.stdout or "")
        + (result.stderr or ""),
    )
    return result.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def _bounded_section(source: str, begin: str, end: str) -> str:
    _require(source.count(begin) == 1, f"section begin marker drift: {begin}")
    _require(source.count(end) == 1, f"section end marker drift: {end}")
    return source.split(begin, 1)[1].split(end, 1)[0]


def _squash(source: str) -> str:
    return " ".join(source.split())


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact two-file FW-RT6-12b Control C corrective-r2 surface conform")


def check_accepted_history_and_focused_gates() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-12b-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-12b-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-12b-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-12b-B-ACCEPTANCE-SYNC:END",
        "FW-RT6-12b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-12b-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")
    for phrase in (
        "Control A implementation and acceptance: fa12002e898a88bc9d9025004b0e4b26772d8187",
        "Control B implementation and acceptance: 51e7ff75b2f17cecb1c21ac696d0c254aa033863",
        "Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted history fact missing: {phrase}")

    historical_task_only = (
        (
            "FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:BEGIN",
            "FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:END",
            "FW-RT6-11c",
        ),
        (
            "FW-RT6-12a-C-AGGREGATE-ACCEPTANCE:BEGIN",
            "FW-RT6-12a-C-AGGREGATE-ACCEPTANCE:END",
            "FW-RT6-12a",
        ),
    )
    for begin, end, label in historical_task_only:
        section = _bounded_section(tasklist, begin, end)
        squashed = _squash(section)
        _require(
            "Control A/B gate/test semantic sync: 4 files / CONTROL_C TASK BOUNDARY ONLY"
            in section,
            f"{label} historical task-boundary label drift",
        )
        _require(
            "CONTROL_C AGGREGATE STATE ONLY" not in section,
            f"{label} historical aggregate-state contamination",
        )
        _require(
            "receive only the reviewed Control C task-boundary and status synchronization."
            in squashed,
            f"{label} historical task-boundary prose drift",
        )
        _require(
            "accepted runtime-state synchronization" not in squashed,
            f"{label} historical runtime-state contamination",
        )

    backpressure_section = _bounded_section(
        tasklist,
        "FW-RT6-12b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-12b-C-AGGREGATE-ACCEPTANCE:END",
    )
    backpressure_squashed = _squash(backpressure_section)
    for phrase in (
        "Control A/B gate/test semantic sync: 4 files / CONTROL_C AGGREGATE STATE ONLY",
        "Control C aggregate commit: 54291405a817afddbef927b0e0a3173d8937772c / PUSHED",
        "Control C corrective-r2: IMPLEMENTED / AWAITING_REVIEW",
        "corrective-r2 exact surface: 2 files",
    ):
        _require(phrase in backpressure_section, f"Control C corrective fact missing: {phrase}")
    _require(
        "receive only the reviewed Control C task-boundary, status, and accepted runtime-state synchronization."
        in backpressure_squashed,
        "FW-RT6-12b aggregate-state prose drift",
    )
    print("[OK] historical FW-RT6-11c/12a task-boundary records are unchanged")
    print("[OK] FW-RT6-12b aggregate-state scope is isolated and explicit")

    sources = {
        "Control A gate": PROJECT_ROOT / "scripts/smoke_v600_backpressure_control_a.py",
        "Control B gate": PROJECT_ROOT / "scripts/smoke_v600_backpressure_control_b.py",
        "Control A tests": PROJECT_ROOT / "tests/test_backpressure_control_a.py",
        "Control B tests": PROJECT_ROOT / "tests/test_backpressure_control_b.py",
    }
    _require(
        sources["Control A tests"].read_text(encoding="utf-8").count("    def test_")
        == 19,
        "Control A test count drift",
    )
    _require(
        sources["Control B tests"].read_text(encoding="utf-8").count("    def test_")
        == 23,
        "Control B test count drift",
    )
    for label, path in sources.items():
        source = path.read_text(encoding="utf-8")
        _require(
            "check_v600_backpressure_acceptance.py" in source,
            f"{label} Control C boundary sync missing",
        )

    _run(
        [
            sys.executable,
            "scripts/smoke_v600_backpressure_control_a.py",
            "--source-only",
        ],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "scripts/smoke_v600_backpressure_control_b.py",
            "--source-only",
        ],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_backpressure_control_a",
            "tests.test_backpressure_control_b",
        ],
        capture=False,
    )
    print("[OK] accepted Control A/B history and 42 focused tests conform")
    print("[OK] four gate/test files receive Control C aggregate-state-only sync")


def check_namespaces_root_and_import_safety() -> None:
    import framework

    contract = importlib.import_module("framework.backpressure")
    runtime = importlib.import_module("framework.backpressure_runtime")
    _require(contract.__all__ == EXPECTED_CONTRACT_EXPORTS, "contract exports drift")
    _require(
        runtime.__all__ == ("BoundedBackpressureRuntime",),
        "runtime exports drift",
    )
    _require(contract.BACKPRESSURE_API_VERSION == "6.0", "API version drift")
    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in EXPECTED_CONTRACT_EXPORTS + runtime.__all__:
        _require(name not in framework.__all__, f"explicit-only name leaked root: {name}")
    _require(
        tuple(item.value for item in contract.BackpressureBoundary)
        == EXPECTED_BOUNDARIES,
        "backpressure boundary inventory drift",
    )

    probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework
import framework.backpressure as contract
import framework.backpressure_runtime as runtime
assert len(framework.__all__) == 127
assert len(contract.__all__) == 12
assert runtime.__all__ == ("BoundedBackpressureRuntime",)
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
    _run([sys.executable, "-I", "-c", probe])
    print("[OK] exact namespaces, four boundaries, and root 127 conform")
    print("[OK] aggregate imports remain provider, network, device, and VTS safe")


def check_aggregate_runtime_truth() -> None:
    import framework
    from framework.backpressure import (
        BackpressureBoundary,
        BackpressureRejectionCode,
        BackpressureState,
    )
    from framework.backpressure_runtime import BoundedBackpressureRuntime
    from framework.realtime_voice_output_queue import BoundedVoiceSynthesisPendingQueue

    overflow_events = []
    runtime = BoundedBackpressureRuntime(
        boundary=BackpressureBoundary.AUDIO_INPUT,
        maximum_pending_count=1,
        maximum_in_flight_count=1,
        on_overflow=overflow_events.append,
    )
    accepted = runtime.admit_item("opaque_audio_1")
    rejected = runtime.admit_item("opaque_audio_2")
    _require(accepted.accepted, "first bounded admission rejected")
    _require(not rejected.accepted, "capacity overflow was accepted")
    _require(
        rejected.rejection_code is BackpressureRejectionCode.CAPACITY_REACHED,
        "capacity rejection code drift",
    )
    _require(rejected.retryable and not rejected.dropped, "retry/drop truth drift")
    _require(len(overflow_events) == 1, "overflow event was silent")
    paused = runtime.pause()
    _require(paused.accepted and paused.cancelled_count == 0, "pause truth drift")
    _require(runtime.pending_item_ids == ("opaque_audio_1",), "pause lost work")
    _require(runtime.resume().accepted, "resume rejected")
    _require(runtime.claim().item_id == "opaque_audio_1", "FIFO claim drift")
    _require(runtime.complete("opaque_audio_1"), "completion rejected")

    voice_input = framework.VoiceInputSession()
    audio_capability = voice_input.audio_input_backpressure_capability
    _require(audio_capability.supported, "audio-input adoption missing")
    _require(audio_capability.maximum_pending_count == 1, "audio pending limit drift")
    _require(audio_capability.maximum_in_flight_count == 1, "audio in-flight drift")
    _require(not audio_capability.silent_drop, "audio-input silent drop overclaim")

    realtime = framework.RealtimeSession()
    try:
        for boundary in (
            BackpressureBoundary.RESPONSE_DELTA,
            BackpressureBoundary.EVENT_SUBSCRIBER,
        ):
            capability = realtime.backpressure_capability(boundary)
            _require(capability.supported, f"session adoption missing: {boundary.value}")
            _require(not capability.silent_drop, f"silent drop drift: {boundary.value}")
        _require(
            realtime.pause_backpressure(BackpressureBoundary.RESPONSE_DELTA).accepted,
            "response-delta pause rejected",
        )
        _require(
            realtime.backpressure_snapshot(BackpressureBoundary.RESPONSE_DELTA).state
            is BackpressureState.PAUSED,
            "response-delta pause state drift",
        )
        _require(
            realtime.resume_backpressure(BackpressureBoundary.RESPONSE_DELTA).accepted,
            "response-delta resume rejected",
        )
    finally:
        realtime.close()

    voice_output = BoundedVoiceSynthesisPendingQueue(max_pending_depth=2)
    voice_capability = voice_output.backpressure_capability
    _require(voice_capability.supported, "voice-output adoption missing")
    _require(voice_capability.maximum_pending_count == 2, "voice pending limit drift")
    _require(voice_capability.maximum_in_flight_count == 1, "voice in-flight drift")
    _require(not voice_capability.silent_drop, "voice-output silent drop overclaim")
    print("[OK] four runtime owners, bounded capacity, and pause/resume conform")
    print("[OK] typed retry, non-silent overflow, and accepted-work safety conform")


def check_docs_tasks_and_unchanged_boundaries() -> None:
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    guide = (PROJECT_ROOT / "docs/v600_backpressure_flow_control.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "FW-RT6-12b-C-BACKPRESSURE-ACCEPTANCE:BEGIN",
        "FW-RT6-12b-C-BACKPRESSURE-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public facade marker drift: {marker}")
    section = tasklist.split("## FW-RT6-12b — P1 backpressure", 1)[1].split(
        "## FW-RT6-12c", 1
    )[0]
    _require(section.count("- [ ]") == 0, "Control C left an aggregate task open")
    _require(section.count("- [x]") == 6, "Control C aggregate task count drift")
    for task in EXPECTED_TASKS:
        _require(section.count(task) == 1, f"task text drift: {task}")
    for phrase in (
        "6 / 6 ACCEPTED-CANDIDATE",
        "framework.backpressure",
        "framework.backpressure_runtime",
        "4 / 4 ADOPTED",
        "reject_newest",
        "127 / UNCHANGED",
        "final acceptance sync: NOT_AUTHORIZED",
    ):
        _require(phrase in facade + "\n" + tasklist, f"aggregate phrase missing: {phrase}")
    for accepted_document, label in (
        (app, "application contract"),
        (guide, "backpressure guide"),
    ):
        _require("0 / 6 CLOSED" in accepted_document, f"historical {label} fact drift")
        _require("framework.backpressure_runtime" in accepted_document, f"{label} runtime fact drift")
    print("[OK] six tasks are aggregate acceptance-candidates")
    print("[OK] public docs and unchanged application/backpressure boundaries conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_history_and_focused_gates()
    check_namespaces_root_and_import_safety()
    check_aggregate_runtime_truth()
    check_docs_tasks_and_unchanged_boundaries()
    print("v600_rt6_12b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12b_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_12b_control_c_exact_surface: 7 files")
    print("v600_rt6_12b_control_c_corrective_r2: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_12b_control_c_corrective_r2_surface: 2 files")
    print("v600_rt6_12b_existing_gate_test_sync: 4 files / AGGREGATE STATE ONLY")
    print("v600_rt6_12b_contract_namespace_exports: 12 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12b_runtime_namespace_exports: 1 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12b_runtime_boundaries: 4 / 4 ADOPTED")
    print("v600_rt6_12b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12b_overflow_policy: reject_newest / NON_SILENT")
    print("v600_rt6_12b_provider_network_device_execution: False")
    print("v600_rt6_12b_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_12b_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_12c: NOT_AUTHORIZED")
    print("v600_rt6_12b_control_c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12b Control C aggregate backpressure gate passed")


if __name__ == "__main__":
    main()
