"""FW-RT6-8b Control C aggregate motion lifecycle acceptance gate.

The gate uses deterministic mock turns and injected in-memory motion stages. It
does not import provider SDKs or execute network, audio, microphone, VTube
Studio, or real motion work.
"""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "a67af1caa45cc3a4f98fb324ce84d5f23ee060c1"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_motion_lifecycle_acceptance.py",
}
EXPECTED_FACTORY_PARAMETERS = (
    "project_root",
    "public_metadata",
    "real_runtime_enabled",
    "voice_input_stage",
    "text_generation_stage",
    "voice_output_stage",
    "motion_stage",
    "config",
)
EXPECTED_EXPLICIT_EXPORTS = (
    "MotionLifecycleSignal",
    "MotionLifecycleNotification",
    "MotionLifecycleHookOutcome",
    "MotionLifecycleHookResult",
    "MotionLifecycleHook",
    "invoke_motion_lifecycle_hook",
)


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
    paths = _git(
        "-c", "core.safecrlf=false", "diff", "--name-only", "HEAD"
    ).splitlines()
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
    print("[OK] baseline and exact three-file FW-RT6-8b Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_b = _load(
        "_fw_rt6_8b_control_b_for_aggregate",
        "scripts/smoke_v600_motion_lifecycle_control_b.py",
    )
    control_b.check_runtime_contract()
    control_b.check_source_contract()
    control_b.check_docs()
    print("[OK] accepted Control A+B motion lifecycle regressions conform")


def _ready_motion_capability():
    from framework.realtime_capabilities import (
        RealtimeMotionCapability,
        RuntimeCapabilityState,
    )

    return RealtimeMotionCapability(
        runtime=RuntimeCapabilityState(
            configured=True,
            runtime_available=True,
            guarded=False,
            fake_runtime=False,
            real_runtime=True,
            unavailable_reason=None,
            public_metadata={"provider_execution_performed": False},
        ),
        request_cancel_supported=True,
        completion_event_supported=True,
        provider_neutral_intent_supported=True,
    )


class _AggregateMotionStage:
    def __init__(self, *, unsupported: bool = False) -> None:
        from framework.realtime_stage import RealtimeStageKind

        self.stage_kind = RealtimeStageKind.MOTION
        self.unsupported = unsupported
        self.preflight_count = 0
        self.start_calls = []
        self.close_count = 0

    def preflight(self):
        self.preflight_count += 1
        return _ready_motion_capability()

    def capability(self):
        raise AssertionError("aggregate path must reuse construction preflight")

    def start(self, *, context, request):
        from framework.motion import (
            MotionAdapterStatus,
            MotionErrorCode,
            MotionOutcome,
            MotionResult,
            MotionState,
        )
        from framework.realtime_stage import RealtimeStageResultEnvelope

        self.start_calls.append((context, request))
        if self.unsupported:
            result = MotionResult(
                outcome=MotionOutcome.UNSUPPORTED,
                state=MotionState.UNAVAILABLE,
                adapter_status=MotionAdapterStatus.UNSUPPORTED_ADAPTER,
                public_error_code=MotionErrorCode.UNSUPPORTED,
                safe_message="Motion intent is unsupported.",
                request_id=request.request_id,
                session_id=context.session_id,
                turn_id=request.turn_id,
                generation_id=request.generation_id,
            )
        else:
            result = MotionResult.completed(
                request=request,
                session_id=context.session_id,
            )
        return RealtimeStageResultEnvelope(
            stage_kind=self.stage_kind,
            context=context,
            result=result,
        )

    def cancel(self, *, context) -> bool:
        return False

    def close(self) -> None:
        self.close_count += 1


def _listening_only_hook(notification):
    from framework.motion import MotionRequest
    from framework.motion_lifecycle import MotionLifecycleSignal

    if notification.signal is MotionLifecycleSignal.LISTENING:
        return MotionRequest.speaking_state(True)
    return None


def check_aggregate_contract() -> None:
    import framework
    import framework.motion_lifecycle as lifecycle
    from framework.lifecycle import TurnOutcome
    from framework.motion import MotionOutcome, MotionRequest
    from framework.motion_lifecycle import MotionLifecycleSignal
    from framework.realtime import RealtimeEventType, RealtimeState

    stage = _AggregateMotionStage()
    notifications = []
    session = framework.create_realtime_session(motion_stage=stage)

    def mapped_hook(notification):
        notifications.append(notification)
        return MotionRequest.speaking_state(
            notification.signal is MotionLifecycleSignal.SPEAKING
        )

    session.set_motion_lifecycle_hook(mapped_hook)
    result = session.run_turn(input_text="aggregate lifecycle")
    events = session.event_history

    _require(result.outcome is TurnOutcome.COMPLETED, "aggregate turn did not complete")
    _require(
        [notification.signal for notification in notifications]
        == [
            MotionLifecycleSignal.LISTENING,
            MotionLifecycleSignal.THINKING,
            MotionLifecycleSignal.SPEAKING,
            MotionLifecycleSignal.COMPLETED,
        ],
        "normal lifecycle signal order drift",
    )
    _require(len(stage.start_calls) == 4, "mapped lifecycle requests were not executed")
    for notification in notifications:
        source_index = next(
            index
            for index, event in enumerate(events)
            if event.sequence == notification.source_sequence
        )
        triplet = events[source_index + 1 : source_index + 4]
        _require(
            [event.type for event in triplet]
            == [
                RealtimeEventType.MOTION_REQUESTED,
                RealtimeEventType.MOTION_STARTED,
                RealtimeEventType.MOTION_COMPLETED,
            ],
            "source-to-motion canonical order drift",
        )
        _require(
            all(event.boundary == "motion" for event in triplet),
            "lifecycle motion event boundary drift",
        )
        _require(
            all(event.turn_id == notification.turn_id for event in triplet),
            "lifecycle motion turn correlation drift",
        )
        _require(
            all(
                event.generation_id == notification.generation_id
                for event in triplet
            ),
            "lifecycle motion generation correlation drift",
        )
    _require(
        [int(event.sequence) for event in events] == list(range(1, len(events) + 1)),
        "shared event sequence is not contiguous",
    )
    terminal_index = next(
        index
        for index, event in enumerate(events)
        if event.type is RealtimeEventType.TURN_COMPLETED
    )
    _require(
        [event.type for event in events[terminal_index + 1 :]]
        == [
            RealtimeEventType.MOTION_REQUESTED,
            RealtimeEventType.MOTION_STARTED,
            RealtimeEventType.MOTION_COMPLETED,
        ],
        "terminal motion is not a post-terminal side effect",
    )
    _require(
        session.terminal_diagnostics["terminal_commit_count"] == 1,
        "terminal motion changed terminal ownership",
    )
    _require(
        session.generation_diagnostics["generation_advance_count"] == 1,
        "terminal motion advanced generation ownership",
    )
    _require(
        session._generation_gate.current_generation_id is None,
        "terminal motion reopened retired generation",
    )
    _require(session.state is RealtimeState.IDLE, "aggregate session did not return idle")
    session.close()
    _require(stage.close_count == 1, "RealtimeSession did not own stage close exactly once")

    failure_stage = _AggregateMotionStage()
    failure_session = framework.create_realtime_session(motion_stage=failure_stage)

    def failing_hook(notification):
        raise RuntimeError("private hook failure")

    failure_session.set_motion_lifecycle_hook(failing_hook)
    failure_result = failure_session.run_turn(input_text="isolated failure")
    _require(
        failure_result.outcome is TurnOutcome.COMPLETED,
        "hook failure changed conversation terminal",
    )
    _require(not failure_stage.start_calls, "failed hook started MotionStage")
    _require(
        not any(event.boundary == "motion" for event in failure_session.event_history),
        "failed hook emitted motion events",
    )
    _require(
        failure_session.terminal_diagnostics["terminal_commit_count"] == 1,
        "hook failure duplicated terminal",
    )
    failure_session.close()

    unsupported_stage = _AggregateMotionStage(unsupported=True)
    unsupported_session = framework.create_realtime_session(
        motion_stage=unsupported_stage
    )
    unsupported_session.set_motion_lifecycle_hook(_listening_only_hook)
    unsupported_result = unsupported_session.run_turn(input_text="unsupported")
    unsupported_event = next(
        event
        for event in unsupported_session.event_history
        if event.type is RealtimeEventType.MOTION_FAILED
    )
    _require(
        unsupported_result.outcome is TurnOutcome.COMPLETED,
        "unsupported motion changed conversation terminal",
    )
    _require(
        unsupported_event.payload.outcome is MotionOutcome.UNSUPPORTED,
        "adapter unsupported outcome was reclassified",
    )
    unsupported_session.close()

    missing_session = framework.create_realtime_session()
    missing_session.set_motion_lifecycle_hook(_listening_only_hook)
    missing_result = missing_session.run_turn(input_text="missing stage")
    missing_event = next(
        event
        for event in missing_session.event_history
        if event.type is RealtimeEventType.MOTION_FAILED
    )
    _require(
        missing_result.outcome is TurnOutcome.COMPLETED,
        "missing stage changed conversation terminal",
    )
    _require(
        missing_event.payload.outcome is MotionOutcome.NOT_CONFIGURED,
        "missing stage did not remain typed not-configured",
    )
    missing_session.close()

    _require(tuple(lifecycle.__all__) == EXPECTED_EXPLICIT_EXPORTS, "hook exports drift")
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "create_realtime_session signature drift",
    )
    _require(
        "motion_lifecycle_hook"
        not in inspect.signature(framework.RealtimeSessionConfig).parameters,
        "hook leaked into RealtimeSessionConfig",
    )
    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API version drift",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version drift",
    )
    _require("pyvts" not in sys.modules, "actual pyvts was imported")
    _require("websockets" not in sys.modules, "websocket runtime was imported")
    print("[OK] aggregate mapping, ordering, isolation, and compatibility conform")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-8b — Motion lifecycle extension hook")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 6 and section.count("- [ ]") == 0,
        "FW-RT6-8b must be 6 / 6 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-8b-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
    for marker in (
        "FW-RT6-8b tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "FW-RT6-8b final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-8c motion cancel/clear: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    _require("Control C changes no runtime source" in facade, "runtime boundary missing")
    _require(
        "post-terminal side effect" in facade,
        "terminal side-effect boundary missing",
    )
    print("[OK] six FW-RT6-8b tasks close as aggregate acceptance-candidates")


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
    print("[OK] Control C introduces no runtime source or FW-RT6-8c change")


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
    print("v600_rt6_8b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_8b_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_8b_control_c_exact_surface: 3 files")
    print("v600_rt6_8b_runtime_changed_by_control_c: False")
    print("v600_rt6_8b_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_8b_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_8c_status: NOT_AUTHORIZED")
    print("v600_rt6_8b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-8b Control C aggregate acceptance gate passed")


if __name__ == "__main__":
    main()
