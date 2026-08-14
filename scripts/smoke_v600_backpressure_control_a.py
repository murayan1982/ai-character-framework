"""FW-RT6-12b Control A provider-neutral backpressure contract gate."""

from __future__ import annotations

import argparse
import ast
import importlib
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "3153efd68213575e39802f0857d05aee693df255"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_backpressure_flow_control.md",
    "framework/backpressure.py",
    "scripts/smoke_v600_backpressure_control_a.py",
    "tests/test_backpressure_control_a.py",
}
EXPECTED_ACCEPTANCE_SURFACE = EXPECTED_SURFACE | {"docs/v600_tasklist.md"}
EXPECTED_EXPORTS = (
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
        "Control A exact surface drift; "
        f"implementation={sorted(EXPECTED_SURFACE)!r}; "
        f"acceptance={sorted(EXPECTED_ACCEPTANCE_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    label = "seven-file acceptance" if actual == EXPECTED_ACCEPTANCE_SURFACE else "six-file implementation"
    print(f"[OK] baseline and exact {label} FW-RT6-12b Control A surface conform")


def check_namespace_and_import_safety() -> None:
    namespace = importlib.import_module("framework.backpressure")
    _require(namespace.__all__ == EXPECTED_EXPORTS, "namespace exports drift")
    _require(namespace.BACKPRESSURE_API_VERSION == "6.0", "API version drift")
    _require(len(set(namespace.__all__)) == 12, "namespace exports are not unique")

    tree = ast.parse(
        (PROJECT_ROOT / "framework/backpressure.py").read_text(encoding="utf-8")
    )
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    _require(
        imports
        == {
            "__future__",
            "dataclasses",
            "enum",
            "types",
            "typing",
            "public_safety",
        },
        f"backpressure module import drift: {sorted(imports)!r}",
    )

    probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.backpressure as backpressure
assert len(backpressure.__all__) == 12
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
    _run([sys.executable, "-I", "-c", probe])
    print("[OK] explicit 12-name namespace is provider, network, and device safe")


def _snapshot(
    boundary: str,
    *,
    state: str = "accepting",
    pending: int = 0,
    in_flight: int = 0,
    overflow: int = 0,
):
    from framework.backpressure import BackpressureSnapshot

    return BackpressureSnapshot(
        boundary=boundary,
        state=state,
        pending_count=pending,
        in_flight_count=in_flight,
        maximum_pending_count=2,
        maximum_in_flight_count=1,
        overflow_count=overflow,
    )


def check_contract_models() -> None:
    from framework.backpressure import (
        BackpressureAdmission,
        BackpressureAdmissionResult,
        BackpressureBoundary,
        BackpressureCapability,
        BackpressureControlResult,
        BackpressureOverflowEvent,
    )

    _require(
        tuple(item.value for item in BackpressureBoundary) == EXPECTED_BOUNDARIES,
        "backpressure boundary vocabulary drift",
    )
    for boundary in EXPECTED_BOUNDARIES:
        unavailable = BackpressureCapability(boundary=boundary)
        _require(not unavailable.supported, "default support overclaim")
        _require(
            unavailable.maximum_pending_count is None
            and unavailable.maximum_in_flight_count is None,
            "default capacity overclaim",
        )
        supported = BackpressureCapability(
            boundary=boundary,
            supported=True,
            maximum_pending_count=2,
            maximum_in_flight_count=1,
            pause_resume_supported=True,
            retryable_rejection_supported=True,
            overflow_event_supported=True,
        )
        _require(supported.overflow_policy.value == "reject_newest", "policy drift")
        _require(not supported.silent_drop, "silent drop capability appeared")

        admission = BackpressureAdmission(
            boundary=boundary,
            item_id=f"{boundary}_item_1",
            public_metadata={"source": "offline-gate"},
        )
        full = _snapshot(boundary, pending=2, overflow=1)
        rejected = BackpressureAdmissionResult(
            accepted=False,
            admission=admission,
            snapshot=full,
            rejection_code="capacity_reached",
            safe_message="Capacity reached.",
            retryable=True,
        )
        overflow_event = BackpressureOverflowEvent(
            admission=admission,
            snapshot=full,
        )
        _require(rejected.retryable, "capacity rejection is not retryable")
        _require(not rejected.dropped, "capacity rejection claimed a drop")
        _require(not overflow_event.dropped, "overflow event claimed a drop")
        _require(
            rejected.admission.item_id == admission.item_id,
            "rejection did not preserve caller-owned item identity",
        )

    paused = BackpressureControlResult(
        kind="pause",
        boundary="audio_input",
        accepted=True,
        previous_state="accepting",
        current_state="paused",
        snapshot=_snapshot("audio_input", state="paused", pending=1),
    )
    resumed = BackpressureControlResult(
        kind="resume",
        boundary="audio_input",
        accepted=True,
        previous_state="paused",
        current_state="accepting",
        snapshot=_snapshot("audio_input", pending=1),
    )
    _require(paused.cancelled_count == 0, "pause claimed cancellation")
    _require(not paused.dropped and not resumed.dropped, "control claimed a drop")
    print("[OK] four-boundary capability, admission, rejection, and overflow conform")
    print("[OK] pause/resume preserve accepted work and silent drop is prohibited")


def check_public_safety_and_root_boundary() -> None:
    import framework
    from framework.backpressure import BackpressureAdmission
    from framework.public_safety import REDACTED_BINARY, REDACTED_VALUE

    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in EXPECTED_EXPORTS:
        _require(name not in framework.__all__, f"explicit name leaked root: {name}")
    admission = BackpressureAdmission(
        boundary="audio_input",
        item_id="chunk_1",
        public_metadata={"payload": b"private", "api_key": "private"},
    )
    projection = admission.as_dict()
    _require(projection["public_metadata"]["payload"] == REDACTED_BINARY, "bytes leak")
    _require(projection["public_metadata"]["api_key"] == REDACTED_VALUE, "secret leak")
    _require(not hasattr(admission, "payload"), "raw payload field appeared")
    _require("private" not in repr(admission), "private value leaked through repr")
    print("[OK] public projections are payload-free and root remains 127 names")


def check_docs_and_task_boundary() -> bool:
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs/v600_backpressure_flow_control.md").read_text(
        encoding="utf-8"
    )
    for source, markers in (
        (
            app,
            (
                "FW-RT6-12b-A-APP-BACKPRESSURE:BEGIN",
                "FW-RT6-12b-A-APP-BACKPRESSURE:END",
            ),
        ),
        (
            facade,
            (
                "FW-RT6-12b-A-PUBLIC-BACKPRESSURE:BEGIN",
                "FW-RT6-12b-A-PUBLIC-BACKPRESSURE:END",
            ),
        ),
    ):
        for marker in markers:
            _require(source.count(marker) == 1, f"documentation marker drift: {marker}")
    combined = "\n".join((app, facade, guide))
    for phrase in (
        "framework.backpressure",
        "audio_input",
        "response_delta",
        "voice_output",
        "event_subscriber",
        "maximum_pending_count",
        "maximum_in_flight_count",
        "reject_newest",
        "capacity_reached",
        "retryable",
        "silent drop",
        "Control B",
        "0 / 6 CLOSED",
    ):
        _require(phrase in combined, f"contract documentation missing: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-12b — P1 backpressure", 1)[1].split(
        "## FW-RT6-12c", 1
    )[0]
    _require(section.count("- [ ]") == 6, "FW-RT6-12b open task count drift")
    _require(section.count("- [x]") == 0, "FW-RT6-12b task closed in Control A")
    _require(
        "FW-RT6-12a-FINAL-ACCEPTANCE-SYNC:BEGIN" in tasklist,
        "accepted FW-RT6-12a history missing",
    )
    acceptance_marker_count = tasklist.count(
        "FW-RT6-12b-A-ACCEPTANCE-SYNC:BEGIN"
    )
    _require(
        acceptance_marker_count <= 1,
        "Control A acceptance-sync marker duplicated",
    )
    if acceptance_marker_count:
        _require(
            tasklist.count("FW-RT6-12b-A-ACCEPTANCE-SYNC:END") == 1,
            "Control A acceptance-sync end marker drift",
        )
        _require(
            "Control A: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH"
            in tasklist,
            "Control A accepted status missing",
        )
    print("[OK] public/app/guide contracts conform and tasks remain 0 / 6 closed")
    return bool(acceptance_marker_count)


def check_runtime_non_adoption() -> None:
    import framework
    from framework.backpressure import BackpressureCapability
    from framework.voice_input_streaming import VoiceInputStreamingCapability

    _require(
        not framework.get_capabilities()
        .realtime_snapshot.voice_input.backpressure_supported,
        "realtime voice-input capability adopted backpressure",
    )
    _require(
        not VoiceInputStreamingCapability().audio_chunk_input_supported,
        "default audio streaming capability changed",
    )
    for boundary in EXPECTED_BOUNDARIES:
        _require(
            not BackpressureCapability(boundary=boundary).supported,
            f"default boundary capability overclaim: {boundary}",
        )
    runtime_source = (
        PROJECT_ROOT / "framework/voice_input_stream_runtime.py"
    ).read_text(encoding="utf-8")
    _require(
        "without adding a backpressure queue" in runtime_source,
        "accepted audio-stream runtime boundary drift",
    )
    print("[OK] Control A remains data-only; runtime adoption is deferred to Control B")


def check_focused_tests() -> None:
    source = (PROJECT_ROOT / "tests/test_backpressure_control_a.py").read_text(
        encoding="utf-8"
    )
    _require(source.count("    def test_") == 19, "Control A test count drift")
    _run([sys.executable, "-m", "unittest", "tests.test_backpressure_control_a"])
    print("[OK] 19 focused FW-RT6-12b Control A tests passed")


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
    check_namespace_and_import_safety()
    check_contract_models()
    check_public_safety_and_root_boundary()
    acceptance_synced = check_docs_and_task_boundary()
    check_runtime_non_adoption()
    check_focused_tests()

    status = (
        "COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH"
        if acceptance_synced
        else "IMPLEMENTED / AWAITING_REVIEW"
    )
    sync_status = "IMPLEMENTED / AWAITING_REVIEW" if acceptance_synced else "NOT_AUTHORIZED"
    print(f"v600_rt6_12b_control_a_status: {status}")
    print("v600_rt6_12b_control_a_exact_surface: 6 files")
    print("v600_rt6_12b_namespace_exports: 12 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12b_boundaries: 4 / EXACT")
    print("v600_rt6_12b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12b_runtime_adoption: False / CONTROL_B")
    print("v600_rt6_12b_task_count: 0 / 6 CLOSED")
    print("v600_rt6_12b_provider_network_device_execution: False")
    print(f"v600_rt6_12b_control_a_acceptance_sync: {sync_status}")
    print("v600_rt6_12b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_12b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12b Control A backpressure contract gate passed")


if __name__ == "__main__":
    main()
