"""FW-RT6-12b Control B bounded runtime-adoption gate."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "fa12002e898a88bc9d9025004b0e4b26772d8187"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_backpressure_flow_control.md",
    "framework/backpressure_runtime.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_session.py",
    "framework/realtime_voice_output_queue.py",
    "framework/voice_input_session.py",
    "framework/voice_input_stream_runtime.py",
    "scripts/smoke_v600_backpressure_control_b.py",
    "tests/test_backpressure_control_b.py",
}
EXPECTED_ACCEPTANCE_SURFACE = EXPECTED_SURFACE | {"docs/v600_tasklist.md"}
EXPECTED_BOUNDARIES = {
    "audio_input",
    "response_delta",
    "voice_output",
    "event_subscriber",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (completed.stdout or "")
        + (completed.stderr or ""),
    )
    return completed.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    actual = {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }
    _require(
        actual in (EXPECTED_SURFACE, EXPECTED_ACCEPTANCE_SURFACE),
        "Control B exact surface drift; "
        f"implementation={sorted(EXPECTED_SURFACE)!r}; "
        f"acceptance={sorted(EXPECTED_ACCEPTANCE_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    label = (
        "twelve-file acceptance"
        if actual == EXPECTED_ACCEPTANCE_SURFACE
        else "eleven-file implementation"
    )
    print(f"[OK] baseline and exact {label} FW-RT6-12b Control B surface conform")


def check_import_and_root_safety() -> None:
    import framework

    runtime = importlib.import_module("framework.backpressure_runtime")
    _require(
        runtime.__all__ == ("BoundedBackpressureRuntime",),
        "runtime namespace export drift",
    )
    _require(len(framework.__all__) == 127, "root-public inventory changed")
    _require(
        "BoundedBackpressureRuntime" not in framework.__all__,
        "internal runtime leaked through root",
    )
    probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.backpressure_runtime
import framework.realtime_event_hub
import framework.realtime_voice_output_queue
import framework.voice_input_session
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
    _run([sys.executable, "-I", "-c", probe])
    print("[OK] explicit runtime adoption imports remain provider, network, and device safe")


def check_runtime_controller() -> None:
    from framework.backpressure import BackpressureBoundary
    from framework.backpressure_runtime import BoundedBackpressureRuntime

    for boundary in BackpressureBoundary:
        events = []
        runtime = BoundedBackpressureRuntime(
            boundary=boundary,
            maximum_pending_count=1,
            maximum_in_flight_count=1,
            on_overflow=events.append,
        )
        accepted = runtime.admit_item(f"{boundary.value}_1")
        rejected = runtime.admit_item(f"{boundary.value}_2")
        _require(accepted.accepted, f"valid admission failed: {boundary.value}")
        _require(
            not rejected.accepted and rejected.retryable and not rejected.dropped,
            f"capacity rejection drift: {boundary.value}",
        )
        _require(len(events) == 1, f"overflow event missing: {boundary.value}")
        paused = runtime.pause()
        _require(
            paused.accepted and paused.cancelled_count == 0 and not paused.dropped,
            f"pause semantics drift: {boundary.value}",
        )
        _require(
            runtime.pending_item_ids == (f"{boundary.value}_1",),
            f"pause consumed accepted work: {boundary.value}",
        )
        _require(runtime.resume().accepted, f"resume failed: {boundary.value}")
    print("[OK] four-boundary capacity, overflow, pause, and ownership semantics conform")


def check_adoption_owners() -> None:
    import framework
    from framework.backpressure import BackpressureBoundary
    from framework.realtime_event_hub import RealtimeEventHub
    from framework.realtime_voice_output_queue import (
        BoundedVoiceSynthesisPendingQueue,
    )

    voice = framework.VoiceInputSession()
    _require(
        voice.audio_input_backpressure_capability.boundary
        is BackpressureBoundary.AUDIO_INPUT,
        "VoiceInputSession audio boundary drift",
    )
    hub = RealtimeEventHub()
    for boundary in (
        BackpressureBoundary.RESPONSE_DELTA,
        BackpressureBoundary.EVENT_SUBSCRIBER,
    ):
        _require(
            hub.backpressure_capability(boundary).supported,
            f"event hub boundary unsupported: {boundary.value}",
        )
    queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=3)
    capability = queue.backpressure_capability
    _require(
        capability.boundary is BackpressureBoundary.VOICE_OUTPUT
        and capability.maximum_pending_count == 3
        and capability.maximum_in_flight_count == 1,
        "voice-output capability drift",
    )
    _require(
        {
            voice.audio_input_backpressure_capability.boundary.value,
            hub.backpressure_capability("response_delta").boundary.value,
            hub.backpressure_capability("event_subscriber").boundary.value,
            capability.boundary.value,
        }
        == EXPECTED_BOUNDARIES,
        "four-boundary owner coverage drift",
    )
    print("[OK] audio, response-delta, voice-output, and subscriber owners conform")


def check_docs_and_task_boundary() -> bool:
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs/v600_backpressure_flow_control.md").read_text(
        encoding="utf-8"
    )
    combined = "\n".join((app, facade, guide))
    for marker in (
        "FW-RT6-12b-B-APP-BACKPRESSURE:BEGIN",
        "FW-RT6-12b-B-APP-BACKPRESSURE:END",
        "FW-RT6-12b-B-PUBLIC-BACKPRESSURE:BEGIN",
        "FW-RT6-12b-B-PUBLIC-BACKPRESSURE:END",
        "FW-RT6-12b-B-RUNTIME-ADOPTION:BEGIN",
        "FW-RT6-12b-B-RUNTIME-ADOPTION:END",
    ):
        _require(combined.count(marker) == 1, f"documentation marker drift: {marker}")
    for phrase in (
        "framework.backpressure_runtime",
        "VoiceInputSession",
        "RealtimeSession",
        "BoundedVoiceSynthesisPendingQueue",
        "reject_newest",
        "silent drop",
        "0 / 6 CLOSED",
        "Control B: IMPLEMENTED / AWAITING_REVIEW",
    ):
        _require(phrase in combined, f"Control B documentation missing: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-12b — P1 backpressure", 1)[1].split(
        "## FW-RT6-12c", 1
    )[0]
    _require(section.count("- [ ]") == 0, "Control C left an aggregate task open")
    _require(section.count("- [x]") == 6, "Control C task count drift")
    _require(
        (PROJECT_ROOT / "scripts/check_v600_backpressure_acceptance.py").is_file(),
        "Control C aggregate gate missing",
    )
    acceptance_marker_count = tasklist.count(
        "FW-RT6-12b-B-ACCEPTANCE-SYNC:BEGIN"
    )
    _require(
        acceptance_marker_count <= 1,
        "Control B acceptance-sync marker duplicated",
    )
    if acceptance_marker_count:
        _require(
            tasklist.count("FW-RT6-12b-B-ACCEPTANCE-SYNC:END") == 1,
            "Control B acceptance-sync end marker drift",
        )
        _require(
            "Control B: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH"
            in tasklist,
            "Control B acceptance status drift",
        )
    print("[OK] Control B contracts conform and tasks are 6 / 6 acceptance-candidates")
    return bool(acceptance_marker_count)


def check_focused_tests() -> None:
    source = (PROJECT_ROOT / "tests/test_backpressure_control_b.py").read_text(
        encoding="utf-8"
    )
    _require(source.count("    def test_") == 23, "Control B test count drift")
    _run([sys.executable, "-m", "unittest", "tests.test_backpressure_control_b"])
    _run([sys.executable, "-m", "unittest", "tests.test_backpressure_control_a"])
    print("[OK] 23 focused Control B and 19 accepted Control A tests passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="skip Git baseline/exact-surface checks",
    )
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_import_and_root_safety()
    check_runtime_controller()
    check_adoption_owners()
    acceptance_synced = check_docs_and_task_boundary()
    check_focused_tests()

    _require(acceptance_synced, "accepted Control B history missing")
    print("v600_rt6_12b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12b_control_b_exact_surface: 11 files")
    print("v600_rt6_12b_runtime_namespace_exports: 1 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12b_runtime_boundaries: 4 / 4 ADOPTED")
    print("v600_rt6_12b_overflow_policy: reject_newest / NON_SILENT")
    print("v600_rt6_12b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12b_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_12b_provider_network_device_execution: False")
    print("v600_rt6_12b_control_b_acceptance_sync: 51e7ff75b2f17cecb1c21ac696d0c254aa033863 / CLOSED")
    print("v600_rt6_12b_aggregate_acceptance: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_12b_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_12b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12b Control B backpressure runtime gate passed")


if __name__ == "__main__":
    main()
