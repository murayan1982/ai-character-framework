"""FW-RT6-8a Control C aggregate motion correlation acceptance gate.

The gate uses only mock and injected in-memory motion paths. It does not import
pyvts/websocket providers or execute network, audio, microphone, or real motion.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import subprocess
import sys
from dataclasses import fields
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "38405956b1646e33a82b366256c5e95b819d7dc8"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_motion_correlation_acceptance.py",
}
LEGACY_REQUEST_FIELDS = (
    "intent",
    "request_id",
    "expression",
    "emotion",
    "gesture",
    "speaking",
    "intensity",
    "duration_ms",
    "character_id",
    "model_id",
    "public_metadata",
)
LEGACY_RESULT_FIELDS = (
    "outcome",
    "state",
    "adapter_status",
    "public_error_code",
    "safe_message",
    "retryable",
    "request_id",
    "session_id",
    "public_metadata",
)
CORRELATION_FIELDS = ("turn_id", "generation_id")


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + result.stdout
        + result.stderr,
    )
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git("-c", "core.safecrlf=false", "diff", "--name-only", "HEAD").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    _require(spec is not None and spec.loader is not None, f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact three-file FW-RT6-8a Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_b = _load(
        "_fw_rt6_8a_control_b_for_aggregate",
        "scripts/smoke_v600_motion_correlation_control_b.py",
    )
    control_b.check_runtime_contract()
    control_b.check_source_contract()
    control_b.check_docs()
    print("[OK] accepted Control A+B motion correlation regressions conform")


def check_aggregate_contract() -> None:
    import framework
    from framework.identity import TurnId
    from framework.lifecycle import RealtimePhase
    from framework.motion import MotionEventType, MotionOutcome, MotionRequest, MotionResult
    from framework.realtime import RealtimeEvent, RealtimeEventType, RealtimeState
    from framework.realtime_event_hub import RealtimeEventHub
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
    )
    from framework.version import MOTION_API_VERSION

    request_fields = tuple(item.name for item in fields(MotionRequest))
    result_fields = tuple(item.name for item in fields(MotionResult))
    _require(
        request_fields == LEGACY_REQUEST_FIELDS + CORRELATION_FIELDS,
        "aggregate MotionRequest field contract drift",
    )
    _require(
        result_fields == LEGACY_RESULT_FIELDS + CORRELATION_FIELDS,
        "aggregate MotionResult field contract drift",
    )
    legacy_request = MotionRequest.expression_change("legacy")
    _require(
        legacy_request.turn_id is None and legacy_request.generation_id is None,
        "legacy request factory correlation drift",
    )

    hub = RealtimeEventHub[RealtimeEvent]()
    gate = RealtimeGenerationGate()
    turn_id = TurnId.new()
    generation_id = gate.start_generation(turn_id)
    session = framework.create_motion_session()
    canonical = []
    legacy = []
    session.on_realtime_event(canonical.append)
    session.on_event(legacy.append)
    session._bind_realtime_coordination(event_hub=hub, generation_gate=gate)

    hub.emit(
        lambda sequence: RealtimeEvent(
            type=RealtimeEventType.SESSION_CREATED,
            state=RealtimeState.IDLE,
            session_id=framework.SessionId.new(),
            sequence=sequence,
            phase=RealtimePhase.IDLE,
        )
    )
    result = session.apply_motion(
        MotionRequest.expression_change(
            "aggregate-smile",
            turn_id=turn_id,
            generation_id=generation_id,
        )
    )
    _require(result.outcome is MotionOutcome.COMPLETED, "current result not completed")
    _require(
        result.session_id == session.info.session_id,
        "motion session correlation drift",
    )
    _require(result.turn_id == turn_id, "motion turn correlation drift")
    _require(result.generation_id == generation_id, "motion generation drift")
    _require(
        [event.type for event in canonical]
        == [
            RealtimeEventType.MOTION_REQUESTED,
            RealtimeEventType.MOTION_STARTED,
            RealtimeEventType.MOTION_COMPLETED,
        ],
        "canonical motion event order drift",
    )
    _require(
        [int(event.sequence) for event in canonical] == [2, 3, 4],
        "shared canonical sequence drift",
    )
    _require(
        all(isinstance(event.payload, framework.MotionEventPayload) for event in canonical),
        "typed canonical motion payload drift",
    )
    _require(
        [event["type"] for event in legacy]
        == ["motion.requested", "motion.started", "motion.completed"],
        "legacy motion event order drift",
    )
    _require(
        all("sequence" not in event for event in legacy),
        "legacy mapping gained a sequence field",
    )
    _require(
        gate.diagnostics["accepted_completion_count"] == 1,
        "current completion did not pass common gate",
    )
    session.close()

    stale_hub = RealtimeEventHub[RealtimeEvent]()
    stale_gate = RealtimeGenerationGate()
    stale_turn = TurnId.new()
    stale_generation = stale_gate.start_generation(stale_turn)
    stale_session = framework.create_motion_session()
    stale_canonical = []
    stale_legacy = []

    def retire_on_started(event: RealtimeEvent) -> None:
        stale_canonical.append(event)
        if event.type is RealtimeEventType.MOTION_STARTED:
            stale_gate.advance(GenerationAdvanceReason.INTERRUPT)

    stale_session.on_realtime_event(retire_on_started)
    stale_session.on_event(stale_legacy.append)
    stale_session._bind_realtime_coordination(
        event_hub=stale_hub,
        generation_gate=stale_gate,
    )
    stale_result = stale_session.apply_motion(
        MotionRequest.expression_change(
            "aggregate-stale",
            turn_id=stale_turn,
            generation_id=stale_generation,
        )
    )
    _require(stale_result.outcome is MotionOutcome.INTERRUPTED, "stale result delivered")
    _require(
        stale_result.public_metadata["late_motion_completion_delivered"] is False,
        "stale delivery metadata drift",
    )
    _require(
        stale_canonical[-1].type is RealtimeEventType.STALE_RESULT_DROPPED,
        "stale canonical diagnostic missing",
    )
    _require(
        RealtimeEventType.MOTION_COMPLETED not in [event.type for event in stale_canonical],
        "late canonical completion emitted",
    )
    _require(
        stale_legacy[-1]["type"] == MotionEventType.INTERRUPTED.value,
        "stale legacy projection drift",
    )
    _require(
        "motion.completed" not in [event["type"] for event in stale_legacy],
        "late legacy completion emitted",
    )
    _require(
        stale_gate.diagnostics["stale_completion_count"] == 1,
        "stale completion was not counted by common gate",
    )
    stale_session.close()

    signature = inspect.signature(framework.create_motion_session)
    _require("realtime_event_hub" not in signature.parameters, "event owner leaked publicly")
    _require("generation_gate" not in signature.parameters, "freshness owner leaked publicly")
    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(MOTION_API_VERSION == "5.5.0", "motion API version drift")
    _require(
        framework.MotionSessionInfo().api_version == MOTION_API_VERSION,
        "motion session info version connection drift",
    )
    print("[OK] aggregate correlation, ordering, stale gate, version, and public surface conform")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-8a — Motion correlation context")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 5 and section.count("- [ ]") == 0,
        "FW-RT6-8a must be 5 / 5 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-8a-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
    for marker in (
        "FW-RT6-8a tasks: 5 / 5 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "FW-RT6-8a final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-8b lifecycle extension hook: NOT_AUTHORIZED",
        "FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    _require("Control C changes no runtime source" in facade, "runtime boundary missing")
    _require(
        "An unbound standalone session still" in facade,
        "standalone compatibility boundary missing",
    )
    print("[OK] five FW-RT6-8a tasks close as aggregate acceptance-candidates")


def check_runtime_and_deferred_scope() -> None:
    runtime_prefixes = (
        "framework/",
        "core/",
        "llm/",
        "providers/",
        "stt/",
        "tts/",
        "vts/",
    )
    runtime = {path for path in _changed_paths() if path.startswith(runtime_prefixes)}
    _require(not runtime, f"Control C changed runtime sources: {sorted(runtime)!r}")
    print("[OK] Control C introduces no runtime source or FW-RT6-8b/8c change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_b()
    check_aggregate_contract()
    check_docs_and_task_closure()
    if not args.source_only:
        check_runtime_and_deferred_scope()
    print("v600_rt6_8a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8a_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8a_control_c_status: implemented-awaiting-review")
    print("v600_rt6_8a_control_c_exact_surface: 3 files")
    print("v600_rt6_8a_runtime_changed_by_control_c: False")
    print("v600_rt6_8a_task_count: 5 / 5 ACCEPTED-CANDIDATE")
    print("v600_rt6_8a_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_8b_status: NOT_AUTHORIZED")
    print("v600_rt6_8c_status: NOT_AUTHORIZED")
    print("v600_rt6_8a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
