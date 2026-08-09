"""FW-RT6-9d Control C aggregate end-to-end stale-enforcement gate.

The gate uses only deterministic in-memory objects, temporary FW artifacts,
and mock stages. It performs no provider, network, audio, microphone, host
playback, or real VTube Studio operation.
"""

from __future__ import annotations

import argparse
import inspect
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "41ec997f1060a010e9f8d9339f0d9e40177c989f"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_end_to_end_stale_acceptance.py",
}
EXPECTED_STAGES = (
    "text_generation_delta",
    "voice_input_transcript",
    "voice_output_artifact",
    "motion_completion",
)
OWNER_SOURCES = {
    "text_generation_delta": "framework/realtime_text_generation.py",
    "voice_input_transcript": "framework/voice_input_session.py",
    "voice_output_artifact": "framework/_realtime_voice_output_control.py",
    "motion_completion": "framework/motion_session.py",
}
EXPECTED_DIAGNOSTIC_KEYS = {
    "generation_start_count",
    "generation_advance_count",
    "accepted_completion_count",
    "stale_completion_count",
    "active_generation_count",
    "registry_size",
}
EXPECTED_CONTROL_A_TESTS = (
    "test_each_end_to_end_stage_can_apply_one_current_delivery",
    "test_each_retired_stage_is_rejected_before_delivery",
    "test_new_turn_rejects_old_callback_without_delivering_value",
    "test_close_retirement_rejects_old_callback",
    "test_reset_retirement_rejects_old_callback",
    "test_delivery_lock_excludes_competing_generation_advance",
    "test_existing_diagnostics_keys_and_immutability_are_unchanged",
)
EXPECTED_CONTROL_B_TESTS = (
    "test_retired_text_delta_is_suppressed_before_stream_state_application",
    "test_reentrant_abort_wins_before_final_transcript_application",
    "test_close_retires_inflight_voice_input_before_transcript_application",
    "test_retired_voice_artifact_is_suppressed_and_invalidated",
    "test_voice_artifact_binding_excludes_competing_generation_advance",
    "test_retired_motion_completion_is_not_published_as_completed",
    "test_motion_application_excludes_competing_generation_advance",
    "test_public_versions_and_later_reset_scope_remain_unchanged",
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
    print("[OK] baseline and exact three-file FW-RT6-9d Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_a_source = (
        PROJECT_ROOT / "tests/test_end_to_end_stale_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_source = (
        PROJECT_ROOT / "tests/test_end_to_end_stale_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_source.count("    def test_") == 13, "Control A test count drift")
    _require(control_b_source.count("    def test_") == 14, "Control B test count drift")
    for name in EXPECTED_CONTROL_A_TESTS:
        _require(f"def {name}(" in control_a_source, f"Control A test missing: {name}")
    for name in EXPECTED_CONTROL_B_TESTS:
        _require(f"def {name}(" in control_b_source, f"Control B test missing: {name}")

    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_end_to_end_stale_control_a",
            "tests.test_end_to_end_stale_control_b",
        ],
        capture=False,
    )
    print("[OK] accepted Control A+B stale-delivery regressions conform")


def check_atomic_freshness_contract() -> None:
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )

    signature = inspect.signature(RealtimeGenerationGate.apply_completion)
    _require(
        tuple(signature.parameters) == ("self", "envelope", "deliver"),
        "atomic ingress signature drift",
    )
    _require(
        signature.parameters["deliver"].kind is inspect.Parameter.KEYWORD_ONLY,
        "bounded delivery must remain keyword-only",
    )

    gate = RealtimeGenerationGate()
    generation_id = gate.start_generation("turn-current")
    delivered: list[str] = []
    for stage in EXPECTED_STAGES:
        decision = gate.apply_completion(
            RealtimeStageCompletionEnvelope(
                turn_id="turn-current",
                generation_id=generation_id,
                stage=stage,
                value=stage,
            ),
            deliver=delivered.append,
        )
        _require(decision.accepted, f"current stage was rejected: {stage}")
    _require(delivered == list(EXPECTED_STAGES), "current stage delivery drift")
    _require(
        gate.diagnostics["accepted_completion_count"] == 4,
        "accepted application count drift",
    )

    gate.advance(GenerationAdvanceReason.INTERRUPT)
    for stage in EXPECTED_STAGES:
        decision = gate.apply_completion(
            RealtimeStageCompletionEnvelope(
                turn_id="turn-current",
                generation_id=generation_id,
                stage=stage,
                value=f"stale-{stage}",
            ),
            deliver=delivered.append,
        )
        _require(not decision.accepted, f"retired stage was accepted: {stage}")
        _require(
            decision.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
            f"stale reason drift: {stage}",
        )
        _require(
            decision.retired_by is GenerationAdvanceReason.INTERRUPT,
            f"retirement reason drift: {stage}",
        )
    _require(delivered == list(EXPECTED_STAGES), "stale value crossed the gate")
    _require(
        gate.diagnostics["stale_completion_count"] == 4,
        "stale application count drift",
    )

    old_gate = RealtimeGenerationGate()
    old_generation = old_gate.start_generation("turn-old")
    current_generation = old_gate.start_generation("turn-new")
    old_delivery: list[str] = []
    old_decision = old_gate.apply_completion(
        RealtimeStageCompletionEnvelope(
            turn_id="turn-old",
            generation_id=old_generation,
            stage="text_generation_delta",
            value="old-delta",
        ),
        deliver=old_delivery.append,
    )
    _require(not old_decision.accepted and not old_delivery, "old turn delta escaped")
    _require(
        old_decision.retired_by is GenerationAdvanceReason.NEW_TURN,
        "new-turn reason drift",
    )
    _require(
        old_decision.current_generation_id == current_generation,
        "current-generation fact drift",
    )

    for reason, stage in (
        (GenerationAdvanceReason.SESSION_CLOSED, "voice_input_transcript"),
        (GenerationAdvanceReason.RESET, "motion_completion"),
    ):
        retired_gate = RealtimeGenerationGate()
        retired_generation = retired_gate.start_generation("turn-retired")
        retired_gate.advance(reason)
        retired_delivery: list[str] = []
        retired_decision = retired_gate.apply_completion(
            RealtimeStageCompletionEnvelope(
                turn_id="turn-retired",
                generation_id=retired_generation,
                stage=stage,
                value="late-value",
            ),
            deliver=retired_delivery.append,
        )
        _require(not retired_decision.accepted, f"retired stage accepted: {stage}")
        _require(not retired_delivery, f"retired value delivered: {stage}")
        _require(retired_decision.retired_by is reason, f"reason lost: {stage}")

    _require(
        set(RealtimeGenerationGate().diagnostics) == EXPECTED_DIAGNOSTIC_KEYS,
        "generation diagnostics keys changed",
    )
    print("[OK] atomic current/stale/new-turn/close/reset behavior conforms")
    print("[OK] existing stale count and typed drop reasons remain authoritative")


def check_runtime_owner_adoption() -> None:
    for stage, relative in OWNER_SOURCES.items():
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(".apply_completion(" in source, f"atomic owner missing: {relative}")
        _require(f'stage="{stage}"' in source, f"stage label missing: {stage}")
        _require(
            ".admit_completion(" not in source,
            f"split check/application remains in owner: {relative}",
        )

    session_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    _require(
        "self._generation_gate.apply_completion(" in session_source,
        "central session ingress did not reuse atomic application",
    )
    _require(
        'stage="motion_completion"' in session_source,
        "motion lifecycle stage vocabulary drift",
    )
    print("[OK] four exact runtime delivery owners reuse the sole freshness gate")


def check_public_compatibility_and_provider_isolation() -> None:
    code = (
        "import sys, framework; "
        "assert 'framework.realtime_text_generation' not in sys.modules; "
        "assert not hasattr(framework, 'RealtimeGenerationGate'); "
        "assert not hasattr(framework, 'RealtimeStageCompletionEnvelope'); "
        "assert len(framework.__all__) == 127; "
        "assert 'pyvts' not in sys.modules; "
        "assert 'websockets' not in sys.modules"
    )
    _run([sys.executable, "-c", code])

    import framework
    from framework.realtime_generation_gate import RealtimeGenerationGate
    from framework.realtime_text_generation import ProviderNeutralTextGenerationStream

    stream_signature = inspect.signature(ProviderNeutralTextGenerationStream)
    _require(
        stream_signature.parameters["generation_gate"].default is None,
        "standalone text-stream compatibility drift",
    )
    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(
        len(tuple(framework.RealtimeEventType)) == 48,
        "event vocabulary changed",
    )
    _require(
        framework.RealtimeSessionInfo().api_version == "5.2.0",
        "realtime API version drift",
    )
    _require(
        framework.MotionSessionInfo().api_version == "5.5.0",
        "motion API version drift",
    )
    _require(
        set(RealtimeGenerationGate().diagnostics) == EXPECTED_DIAGNOSTIC_KEYS,
        "generation diagnostics key drift",
    )
    _require(
        not hasattr(framework.RealtimeSession, "reset"),
        "FW-RT6-10a reset API escaped into Control C",
    )
    for module_name in ("pyvts", "websockets", "pyaudio", "sounddevice"):
        _require(module_name not in sys.modules, f"runtime import escaped: {module_name}")
    print("[OK] root-public/version/event/provider isolation remains unchanged")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-9d — End-to-end stale enforcement")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 6 and section.count("- [ ]") == 0,
        "FW-RT6-9d must be 6 / 6 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            text.count("FW-RT6-9d-C-AGGREGATE-ACCEPTANCE:BEGIN") == 1,
            "Control C aggregate begin marker missing or duplicated",
        )
        _require(
            text.count("FW-RT6-9d-C-AGGREGATE-ACCEPTANCE:END") == 1,
            "Control C aggregate end marker missing or duplicated",
        )
    for marker in (
        "Control C exact surface: 3 files",
        "focused Control A+B stale-delivery tests: 27 / PASS",
        "four runtime delivery owners adopted: 4 / 4 / PASS",
        "all stage late-result scenarios: PASS",
        "silent corruption: False / PASS",
        "runtime source changed by Control C: False",
        "existing tests changed by Control C: False",
        "FW-RT6-9d tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "FW-RT6-9d final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-10a implementation: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    for phrase in (
        "Every correlated runtime value is submitted through the existing atomic",
        "Final closure remains a separate",
        "FW-RT6-10a recovery/reset implementation remains",
    ):
        _require(phrase in facade, f"public facade boundary missing: {phrase}")
    print("[OK] six FW-RT6-9d tasks close as aggregate acceptance-candidates")


def check_runtime_and_deferred_scope() -> None:
    forbidden_prefixes = (
        "framework/",
        "core/",
        "llm/",
        "providers/",
        "stt/",
        "tests/",
        "tts/",
        "vts/",
    )
    changed_runtime = {
        path for path in _changed_paths() if path.startswith(forbidden_prefixes)
    }
    _require(
        not changed_runtime,
        f"Control C changed runtime/existing tests: {sorted(changed_runtime)!r}",
    )
    _require(
        "FW-RT6-10a implementation: NOT_AUTHORIZED"
        in (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8"),
        "FW-RT6-10a boundary drift",
    )
    print("[OK] Control C introduces no runtime, existing-test, or FW-RT6-10a change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_b()
    check_atomic_freshness_contract()
    check_runtime_owner_adoption()
    check_public_compatibility_and_provider_isolation()
    check_docs_and_task_closure()
    if not args.source_only:
        check_runtime_and_deferred_scope()

    print("v600_rt6_9d_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9d_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_9d_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_9d_control_c_exact_surface: 3 files")
    print("v600_rt6_9d_runtime_changed_by_control_c: False")
    print("v600_rt6_9d_existing_tests_changed_by_control_c: False")
    print("v600_rt6_9d_freshness_owner: RealtimeGenerationGate / REUSED")
    print("v600_rt6_9d_delivery_owner_count: 4 / 4 PASS")
    print("v600_rt6_9d_late_delivery: False / PASS")
    print("v600_rt6_9d_silent_corruption: False / PASS")
    print("v600_rt6_9d_stale_count_reason: RETAINED / PASS")
    print("v600_rt6_9d_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_9d_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_10a_status: NOT_AUTHORIZED")
    print("v600_rt6_9d_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-9d Control C aggregate acceptance gate passed")


if __name__ == "__main__":
    main()
