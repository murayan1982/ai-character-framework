"""FW-RT6-10b Control C aggregate close/dispose acceptance gate.

The gate uses only deterministic in-memory sessions, fake stages, and fake
provider compositions.  It performs no provider, network, audio, microphone,
playback, or real VTube Studio operation.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "b7ae54f7a948704456ddd446f9ddc631b0d3d4ad"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_session_close_acceptance.py",
}
EXPECTED_EXPLICIT_EXPORTS = (
    "SessionCleanupTarget",
    "SessionCleanupOutcome",
    "SessionCloseOutcome",
    "SessionClosePlan",
    "SessionCleanupResult",
    "SessionCloseResult",
    "build_session_close_plan",
)
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
EXPECTED_TASKS = (
    "全public session close semanticsを統一する。",
    "closeをidempotentにする。",
    "active turn closeをterminalへ収束させる。",
    "stage cleanup timeoutを実装する。",
    "callback/event hubをcloseする。",
    "provider/client/bridge cleanup resultをdiagnosticsへ記録する。",
    "close後operationをtyped rejectionにする。",
)
EXPECTED_CONTROL_A_TESTS = (
    "test_explicit_package_exports_are_exact_and_root_surface_is_unchanged",
    "test_plan_records_exact_required_targets_in_close_order",
    "test_plan_timeouts_are_finite_positive_and_boolean_fields_are_exact",
    "test_cleanup_timeout_is_truthful_and_does_not_reopen_session",
    "test_repeated_close_is_side_effect_free_and_attempts_no_cleanup",
)
EXPECTED_CONTROL_B_TESTS = (
    "test_all_five_public_sessions_publish_first_and_duplicate_results",
    "test_realtime_close_commits_active_turn_and_one_correlated_final_event",
    "test_realtime_stage_closes_run_in_parallel_under_one_deadline",
    "test_realtime_bridge_reports_confirmed_shutdown",
    "test_text_close_terminalizes_active_context_and_suppresses_late_chunks",
    "test_voice_input_close_uses_active_context_and_clears_callbacks",
    "test_voice_output_has_no_persistent_provider_cleanup_target",
    "test_motion_maps_composition_and_bridge_cleanup_and_clears_callbacks",
)


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
    print("[OK] baseline and exact three-file FW-RT6-10b Control C surface conform")


def check_lazy_root_and_accepted_controls() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.session_close' not in sys.modules; "
        "assert not hasattr(framework, 'SessionCloseResult'); "
        "assert len(framework.__all__) == 127"
    )
    _run([sys.executable, "-c", code])

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-10b-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10b-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-10b-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-10b-B-ACCEPTANCE-SYNC:END",
    ):
        _require(tasklist.count(marker) == 1, f"accepted sync marker drift: {marker}")
    for phrase in (
        "Control A implementation: d0e977193faafbcc60e17436f4c2b5bb5547683a",
        "Control A acceptance sync: 6153661b3960fbfa1130b2caef39e48717ad8e80",
        "Control B implementation: 98c6455640be1eed737478c195616b2ff12840bb",
        "Control B acceptance sync: b7ae54f7a948704456ddd446f9ddc631b0d3d4ad",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted Control A/B fact missing: {phrase}")

    control_a_source = (
        PROJECT_ROOT / "tests/test_session_close_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_source = (
        PROJECT_ROOT / "tests/test_session_close_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_source.count("    def test_") == 12, "Control A test count drift")
    _require(control_b_source.count("    def test_") == 13, "Control B test count drift")
    for name in EXPECTED_CONTROL_A_TESTS:
        _require(f"def {name}(" in control_a_source, f"Control A test missing: {name}")
    for name in EXPECTED_CONTROL_B_TESTS:
        _require(f"def {name}(" in control_b_source, f"Control B test missing: {name}")

    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_session_close_control_a",
            "tests.test_session_close_control_b",
        ],
        capture=False,
    )
    print("[OK] root import stays lazy and session-close names remain explicit-only")
    print("[OK] accepted Control A+B close/dispose regressions conform")


def _cleanup_outcome(result: object, target: object) -> object:
    return next(
        item.outcome
        for item in result.cleanup_results  # type: ignore[attr-defined]
        if item.target is target
    )


def check_planning_and_result_contract() -> None:
    import framework.session_close as session_close
    from framework.session_close import (
        SessionCleanupOutcome,
        SessionCleanupResult,
        SessionCleanupTarget,
        SessionCloseOutcome,
        SessionCloseResult,
        build_session_close_plan,
    )

    _require(tuple(session_close.__all__) == EXPECTED_EXPLICIT_EXPORTS, "explicit exports drift")
    plan = build_session_close_plan(
        active_turn_terminal_required=True,
        stage_cleanup_required=True,
        provider_client_cleanup_required=True,
        callback_hub_close_required=True,
        execution_bridge_shutdown_required=True,
        stage_cleanup_timeout_seconds=0.5,
        provider_cleanup_timeout_seconds=0.75,
        bridge_shutdown_timeout_seconds=1.0,
    )
    _require(
        plan.required_targets == tuple(SessionCleanupTarget),
        "canonical cleanup target order drift",
    )
    _require(plan.side_effect_free and not plan.decision_is_execution, "plan gained effects")
    results = tuple(
        SessionCleanupResult.completed(target) for target in SessionCleanupTarget
    )
    closed = SessionCloseResult.from_cleanup(
        plan,
        cleanup_results=results,
        active_turn_terminalized=True,
    )
    _require(closed.outcome is SessionCloseOutcome.CLOSED, "successful close drift")
    _require(closed.session_closed, "successful result reopened session")
    _require(
        dict(closed.diagnostics)
        == {
            "cleanup_required_count": 5,
            "cleanup_attempted_count": 5,
            "cleanup_completed_count": 5,
            "cleanup_timeout_count": 0,
            "cleanup_failure_count": 0,
            "active_turn_terminalized_count": 1,
        },
        "count-only cleanup diagnostics drift",
    )

    timeout_plan = build_session_close_plan(stage_cleanup_required=True)
    timeout_results = tuple(
        (
            SessionCleanupResult.timed_out_result(
                target,
                safe_message="Stage cleanup timed out.",
            )
            if target is SessionCleanupTarget.STAGE
            else SessionCleanupResult.not_required(target)
        )
        for target in SessionCleanupTarget
    )
    timed_out = SessionCloseResult.from_cleanup(
        timeout_plan,
        cleanup_results=timeout_results,
        active_turn_terminalized=False,
    )
    _require(
        timed_out.outcome is SessionCloseOutcome.CLOSED_WITH_CLEANUP_FAILURES,
        "timeout aggregate result drift",
    )
    _require(timed_out.session_closed, "timeout reopened session")
    _require(
        _cleanup_outcome(timed_out, SessionCleanupTarget.STAGE)
        is SessionCleanupOutcome.TIMED_OUT,
        "typed timeout observation drift",
    )

    repeated = SessionCloseResult.already_closed()
    _require(repeated.outcome is SessionCloseOutcome.ALREADY_CLOSED, "repeat outcome drift")
    _require(repeated.diagnostics["cleanup_attempted_count"] == 0, "repeat attempted cleanup")
    _require("private" not in repr(closed).lower(), "private value escaped result")
    print("[OK] canonical plans, results, deadlines, and count-only diagnostics conform")


def _build_public_sessions() -> tuple[object, ...]:
    from framework.audio.voice_output import VoiceOutputSession
    from framework.facade import TextChatSession, TextChatSessionInfo
    from framework.motion_session import MotionSession
    from framework.realtime_session import RealtimeSession
    from framework.voice_input_session import VoiceInputSession
    from llm.base import BaseLLM

    class AggregateLLM(BaseLLM):
        @property
        def provider_name(self) -> str:
            return "fake"

        @property
        def model_name(self) -> str:
            return "aggregate-fake"

        def ask_stream(self, text: str):
            del text
            yield "first", []
            yield "late", []

    info = TextChatSessionInfo(
        preset="text_chat",
        character_name="aggregate",
        input_language_code="ja",
        output_language_code="ja",
        llm_mode="fake",
        provider="fake",
        model="aggregate-fake",
        route_name=None,
    )
    return (
        RealtimeSession(),
        TextChatSession(AggregateLLM(), info),
        VoiceInputSession(),
        VoiceOutputSession(),
        MotionSession(),
    )


def check_public_session_adoption_and_idempotence() -> None:
    from framework.audio.voice_output import VoiceOutputSession
    from framework.facade import TextChatSession
    from framework.motion_session import MotionSession
    from framework.realtime_session import RealtimeSession
    from framework.session_close import SessionCloseOutcome
    from framework.voice_input_session import VoiceInputSession

    public_types = (
        RealtimeSession,
        TextChatSession,
        VoiceInputSession,
        VoiceOutputSession,
        MotionSession,
    )
    for session_type in public_types:
        descriptor = inspect.getattr_static(session_type, "last_close_result")
        _require(isinstance(descriptor, property), f"last_close_result drift: {session_type.__name__}")
        _require(descriptor.fset is None, f"last_close_result became writable: {session_type.__name__}")
        _require(not hasattr(session_type, "close_result"), f"ambiguous result added: {session_type.__name__}")
        for method_name in ("close", "dispose"):
            signature = inspect.signature(getattr(session_type, method_name))
            _require(
                signature.return_annotation in {None, "None"},
                f"{method_name} return changed: {session_type.__name__}",
            )

    for session in _build_public_sessions():
        _require(session.last_close_result is None, f"pre-close result drift: {type(session).__name__}")
        _require(session.close() is None, f"close return drift: {type(session).__name__}")
        first = session.last_close_result
        _require(first.outcome is SessionCloseOutcome.CLOSED, f"first close drift: {type(session).__name__}")
        _require(session.is_closed, f"session reopened: {type(session).__name__}")
        _require(session.dispose() is None, f"dispose return drift: {type(session).__name__}")
        repeated = session.last_close_result
        _require(repeated.outcome is SessionCloseOutcome.ALREADY_CLOSED, f"repeat drift: {type(session).__name__}")
        _require(repeated.diagnostics["cleanup_attempted_count"] == 0, f"repeat cleanup: {type(session).__name__}")
        _require(first is not repeated, f"repeat observation not published: {type(session).__name__}")
    print("[OK] all five public sessions publish read-only typed close results")
    print("[OK] first and duplicate close semantics remain compatible and idempotent")


def check_realtime_terminal_event_and_callbacks() -> None:
    from framework.lifecycle import TurnOutcome
    from framework.realtime import RealtimeEventType
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
    )
    from framework.realtime_session import RealtimeSession
    from framework.session_close import SessionCloseOutcome

    session = RealtimeSession()
    events = []
    session.on_event(events.append)
    started = session.start_turn(input_text="aggregate-close")
    _require(started.accepted, "active realtime turn was not admitted")
    session.close()

    terminal = session.terminal_results[-1]
    _require(terminal.outcome is TurnOutcome.CLOSED, "active turn was orphaned")
    _require(terminal.turn_id == started.turn_id, "terminal turn context drift")
    _require(terminal.generation_id == started.generation_id, "terminal generation drift")
    closed_events = [event for event in events if event.type is RealtimeEventType.SESSION_CLOSED]
    _require(len(closed_events) == 1, "SESSION_CLOSED count drift")
    _require(closed_events[0].turn_id == started.turn_id, "close event turn drift")
    _require(closed_events[0].generation_id == started.generation_id, "close event generation drift")
    _require(session.event_diagnostics["subscriber_count"] == 0, "event hub retained subscriber")
    _require(session.last_close_result.active_turn_terminalized, "terminal fact missing")
    retired = session._generation_gate.admit_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=started.turn_id,
            generation_id=started.generation_id,
            stage="aggregate-close-probe",
            value=None,
        )
    )
    _require(not retired.accepted, "closed generation still accepted completion")
    _require(
        retired.retired_by is GenerationAdvanceReason.SESSION_CLOSED,
        "retirement owner/reason drift",
    )

    before_count = len(events)
    session.close()
    _require(len(events) == before_count, "duplicate close emitted another event")
    _require(session.last_close_result.outcome is SessionCloseOutcome.ALREADY_CLOSED, "duplicate close drift")
    print("[OK] active turn terminal, generation retirement, and final event ordering conform")
    print("[OK] event hub seals after one correlated SESSION_CLOSED delivery")


class _SlowCloseStage:
    def __init__(self, *, delay: float) -> None:
        self.delay = delay
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1
        time.sleep(self.delay)


def check_bounded_cleanup_and_bridge() -> None:
    from framework.realtime_execution_bridge import _RealtimeExecutionBridge
    from framework.realtime_session import RealtimeSession
    from framework.session_close import SessionCleanupOutcome, SessionCleanupTarget

    fast = _SlowCloseStage(delay=0.0)
    slow = _SlowCloseStage(delay=0.20)
    session = RealtimeSession()
    session._injected_stages = {"fast": fast, "slow": slow}
    started = time.monotonic()
    with patch("framework.realtime_session._SESSION_CLOSE_TIMEOUT_SECONDS", 0.03):
        session.close()
    elapsed = time.monotonic() - started
    _require(elapsed < 0.15, "stage cleanup exceeded the finite common deadline")
    published = session.last_close_result
    _require(
        _cleanup_outcome(published, SessionCleanupTarget.STAGE)
        is SessionCleanupOutcome.TIMED_OUT,
        "slow stage was not typed timed_out",
    )
    _require(session.is_closed, "stage timeout reopened session")
    cleanup_threads = [
        thread
        for thread in threading.enumerate()
        if thread.name.startswith("framework-session-close-")
    ]
    _require(all(thread.daemon for thread in cleanup_threads), "non-daemon cleanup worker escaped")
    time.sleep(0.22)
    _require(session.last_close_result is published, "late stage mutated published result")
    _require(fast.close_count == 1 and slow.close_count == 1, "stage cleanup count drift")
    _require(
        not any(
            thread.is_alive() and thread.name.startswith("framework-session-close-")
            for thread in threading.enumerate()
        ),
        "bounded cleanup worker persisted after external return",
    )

    bridge = _RealtimeExecutionBridge(thread_name="fw-rt6-10b-control-c-bridge")
    _require(bridge.run(asyncio.sleep(0, result=7)) == 7, "bridge execution drift")
    _require(bridge.shutdown(timeout_seconds=1.0), "bridge stop was not confirmed")
    _require(not bridge.thread_alive, "bridge thread leaked")
    _require(bridge.shutdown(timeout_seconds=0.01), "duplicate bridge shutdown drift")
    print("[OK] parallel stage cleanup shares one finite deadline and daemon isolation")
    print("[OK] late cleanup cannot mutate the result and confirmed bridge stop conforms")


def check_provider_mapping_and_post_close_rejection() -> None:
    import framework
    from framework.audio.voice_output import VoiceOutputSession
    from framework.facade import TextChatSession, TextChatSessionInfo
    from framework.motion import MotionErrorCode, MotionOutcome, MotionRequest
    from framework.motion_session import MotionSession
    from framework.realtime import RealtimeErrorCode
    from framework.realtime_session import RealtimeSession
    from framework.session_close import SessionCleanupOutcome, SessionCleanupTarget
    from framework.voice_input_session import VoiceInputSession
    from llm.base import BaseLLM

    class OneChunkLLM(BaseLLM):
        @property
        def provider_name(self) -> str:
            return "fake"

        @property
        def model_name(self) -> str:
            return "fake"

        def ask_stream(self, text: str):
            del text
            yield "chunk", []

    info = TextChatSessionInfo(
        preset="text_chat",
        character_name="aggregate",
        input_language_code="ja",
        output_language_code="ja",
        llm_mode="fake",
        provider="fake",
        model="fake",
        route_name=None,
    )

    realtime = RealtimeSession()
    realtime.close()
    before_events = realtime.event_history
    realtime_result = realtime.start_turn(input_text="closed")
    _require(not realtime_result.accepted, "closed realtime admitted work")
    _require(
        realtime_result.terminal_result.public_error_code is RealtimeErrorCode.SESSION_CLOSED,
        "realtime post-close rejection drift",
    )
    _require(realtime.event_history == before_events, "post-close realtime event escaped")

    text = TextChatSession(OneChunkLLM(), info)
    text.close()
    text_result = text.ask_result("closed")
    _require(text_result.public_error_code == "session_closed", "text post-close rejection drift")

    voice_input = VoiceInputSession()
    voice_input.close()
    voice_input_result = voice_input.text_fallback_result("closed")
    _require(voice_input_result.outcome.value == "closed", "voice-input outcome drift")
    _require(voice_input_result.public_error_code.value == "session_closed", "voice-input code drift")

    voice_output = VoiceOutputSession()
    voice_output.close()
    voice_output_result = voice_output.create_output("closed")
    _require(not voice_output_result.audio_ready, "closed voice-output produced audio")
    _require(
        voice_output_result.public_metadata.get("public_error_code") == "session_closed",
        "voice-output post-close rejection drift",
    )
    _require(
        _cleanup_outcome(voice_output.last_close_result, SessionCleanupTarget.PROVIDER_CLIENT)
        is SessionCleanupOutcome.NOT_REQUIRED,
        "voice-output invented a persistent provider target",
    )

    motion = MotionSession()
    motion.close()
    motion_result = motion.apply_motion(MotionRequest.expression_change("smile"))
    _require(motion_result.outcome is MotionOutcome.CLOSED, "motion post-close outcome drift")
    _require(
        motion_result.public_error_code is MotionErrorCode.SESSION_CLOSED,
        "motion post-close rejection drift",
    )

    _require(len(framework.__all__) == 127, "root-public surface changed")
    _require(framework.RealtimeSessionInfo().api_version == "5.2.0", "realtime API changed")
    _require(framework.MotionSessionInfo().api_version == "5.5.0", "motion API changed")
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "realtime factory signature drift",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"provider/runtime module escaped: {module_name}")
    print("[OK] provider/client/bridge mapping and voice-output not_required conform")
    print("[OK] all five public sessions retain operation-specific typed rejection")
    print("[OK] root-public, factory, version, and provider-isolation boundaries conform")


def check_docs_and_task_closure() -> None:
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-10b-C-SESSION-CLOSE-ACCEPTANCE:BEGIN",
        "FW-RT6-10b-C-SESSION-CLOSE-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public contract marker drift: {marker}")
    for marker in (
        "FW-RT6-10b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-10b-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")

    for phrase in (
        "exact Control C surface: 3 files",
        "public session adoption: 5 / 5 PASS",
        "active turn orphan after close: False",
        "stage cleanup: PARALLEL / ONE FINITE COMMON DEADLINE",
        "Framework persistent non-daemon cleanup thread added: False",
        "post-close typed rejection: RETAINED",
        "runtime source changed by Control C: False",
        "existing tests changed by Control C: False",
        "FW-RT6-10b tasks: 7 / 7 ACCEPTED-CANDIDATE",
        "FW-RT6-10b final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-10c implementation: NOT_AUTHORIZED",
        "Control C commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in facade or phrase in tasklist, f"aggregate phrase missing: {phrase}")

    section = tasklist.split("## FW-RT6-10b — Close/dispose lifecycle", 1)[1].split(
        "## FW-RT6-10c — Public diagnostics", 1
    )[0]
    _require(section.count("- [x]") == 7, "FW-RT6-10b accepted-candidate count drift")
    _require(section.count("- [ ]") == 0, "FW-RT6-10b task remains open")
    for task in EXPECTED_TASKS:
        _require(task in section, f"FW-RT6-10b task missing: {task}")
    print("[OK] Control C introduces no runtime, existing-test, or FW-RT6-10c change")
    print("[OK] seven FW-RT6-10b tasks close as aggregate acceptance-candidates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_lazy_root_and_accepted_controls()
    check_planning_and_result_contract()
    check_public_session_adoption_and_idempotence()
    check_realtime_terminal_event_and_callbacks()
    check_bounded_cleanup_and_bridge()
    check_provider_mapping_and_post_close_rejection()
    check_docs_and_task_closure()

    print("v600_rt6_10b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_10b_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_10b_control_c_exact_surface: 3 files")
    print("v600_rt6_10b_runtime_changed_by_control_c: False")
    print("v600_rt6_10b_existing_tests_changed_by_control_c: False")
    print("v600_rt6_10b_public_session_adoption: 5 / 5 PASS")
    print("v600_rt6_10b_active_turn_orphan: False / PASS")
    print("v600_rt6_10b_stage_common_deadline: ENFORCED / PASS")
    print("v600_rt6_10b_persistent_non_daemon_cleanup_thread: False / PASS")
    print("v600_rt6_10b_bridge_stopped_before_complete: True / PASS")
    print("v600_rt6_10b_duplicate_close_cleanup_count: 0 / PASS")
    print("v600_rt6_10b_post_close_rejection: TYPED / PASS")
    print("v600_rt6_10b_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_10b_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_10c: NOT_AUTHORIZED")
    print("v600_rt6_10b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-10b Control C aggregate close/dispose gate passed")


if __name__ == "__main__":
    main()
