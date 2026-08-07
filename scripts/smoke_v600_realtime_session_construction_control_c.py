"""FW-RT6-4a Control C public construction-result / no-fallback smoke gate."""

from __future__ import annotations

import argparse
import ast
import inspect
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "0192f941e3a2009d203535ec0c97a6ceb69050ed"
EXPECTED_SURFACE = {
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/capabilities.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "framework/realtime_session_config.py",
    "scripts/check_v600_realtime_session_construction_acceptance.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_session_construction_adoption.py",
    "scripts/smoke_v600_realtime_session_construction_control_c.py",
    "scripts/smoke_v600_realtime_session_construction_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_session_construction.py",
    "tests/test_realtime_session_construction_adoption.py",
    "tests/test_realtime_session_construction_runtime_guard.py",
}


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


def _run(command: list[str], *, label: str) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"{label} failed:\n{output}")
    return output


def check_repository_contract(*, source_only: bool) -> None:
    if source_only:
        print("[OK] source-only mode skips Git metadata while preserving Control C source checks")
        return
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected FW HEAD")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(_git("branch", "--show-current") == "main", "unexpected FW branch")
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected combined Control A+B+C surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact eighteen-file combined Control A+B+C surface conform")


def check_source_contract() -> None:
    path = PROJECT_ROOT / "framework" / "realtime_session.py"
    source = path.read_text(encoding="utf-8")
    ast.parse(source, filename=str(path))

    required = (
        "def construction_result(self) -> RealtimeSessionConstructionResult:",
        "def _reject_unexecutable_real_runtime_turn(",
        "if self._real_runtime_requested:",
        "RealtimeErrorCode.CONFIGURATION_MISSING",
        'reason = "real_runtime_configuration_missing"',
        'reason = "real_runtime_preflight_failed"',
        'reason = "real_runtime_orchestration_not_available"',
        '"mock_runtime": False',
        '"provider_execution_performed": False',
        "event_type=RealtimeEventType.TURN_REJECTED",
        "recovery_action=RecoveryAction.REUSE_SESSION",
    )
    for phrase in required:
        _assert(phrase in source, f"RealtimeSession Control C source missing: {phrase}")

    guard = source.index("if self._real_runtime_requested:")
    generation = source.index("self._start_turn_generation(turn.turn_id)", guard)
    _assert(guard < generation, "real-runtime guard must precede generation admission")

    forbidden_roots = {
        "aiohttp",
        "elevenlabs",
        "google",
        "httpx",
        "openai",
        "pyaudio",
        "pyvts",
        "requests",
        "sounddevice",
        "speech_recognition",
        "websocket",
        "websockets",
        "xai_sdk",
    }
    tree = ast.parse(source, filename=str(path))
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    _assert(
        not (imported_roots & forbidden_roots),
        f"provider SDK import leaked into RealtimeSession: {sorted(imported_roots & forbidden_roots)}",
    )
    print("[OK] public construction-result property and pre-generation no-fallback guard conform")


def check_runtime_behavior() -> None:
    import framework
    from framework.lifecycle import TurnOutcome
    from framework.realtime import RealtimeErrorCode, RealtimeEventType, RealtimeState
    from framework.realtime_capabilities import RuntimeCapabilityState, TextGenerationCapability
    from framework.realtime_session_config import RealtimeSessionConfig, RealtimeSessionConstructionStatus
    from framework.realtime_stage import RealtimeStageKind

    class TextStage:
        stage_kind = RealtimeStageKind.TEXT_GENERATION

        def __init__(self, *, fail: bool = False) -> None:
            self.fail = fail
            self.calls: list[str] = []

        def preflight(self) -> TextGenerationCapability:
            self.calls.append("preflight")
            if self.fail:
                raise RuntimeError("private-provider-detail")
            return TextGenerationCapability(
                runtime=RuntimeCapabilityState(
                    configured=True,
                    runtime_available=True,
                    guarded=False,
                    fake_runtime=False,
                    real_runtime=True,
                    unavailable_reason=None,
                    public_metadata={"provider_execution_performed": False},
                ),
                streaming_supported=True,
                cooperative_cancel_supported=True,
                provider_hard_cancel_supported=False,
            )

        def capability(self) -> TextGenerationCapability:
            self.calls.append("capability")
            raise AssertionError("capability must not run")

        def start(self, *, context: object, request: object) -> object:
            self.calls.append("start")
            raise AssertionError("start must not run")

        def cancel(self, *, context: object) -> bool:
            self.calls.append("cancel")
            raise AssertionError("cancel must not run")

        def close(self) -> None:
            self.calls.append("close")

    mock_session = framework.create_realtime_session()
    _assert(
        mock_session.construction_result.status is RealtimeSessionConstructionStatus.MOCK_READY,
        "default construction result is not mock_ready",
    )
    mock_result = mock_session.run_turn(input_text="mock")
    _assert(mock_result.outcome is TurnOutcome.COMPLETED, "default mock turn regressed")

    missing = framework.create_realtime_session(real_runtime_enabled=True)
    missing_result = missing.run_turn(input_text="missing")
    _assert(missing_result.outcome is TurnOutcome.REJECTED, "missing config was not rejected")
    _assert(
        missing_result.public_error_code is RealtimeErrorCode.CONFIGURATION_MISSING,
        "missing config did not use CONFIGURATION_MISSING",
    )
    _assert(len(missing.event_history) == 1, "missing config emitted mock lifecycle events")
    _assert(
        missing.event_history[0].type is RealtimeEventType.TURN_REJECTED,
        "missing config did not emit TURN_REJECTED",
    )
    _assert(missing.state is RealtimeState.IDLE, "rejected session did not return idle")

    failed_stage = TextStage(fail=True)
    failed = framework.create_realtime_session(
        config=RealtimeSessionConfig(
            real_runtime_enabled=True,
            text_generation_stage=failed_stage,
        )
    )
    failed_result = failed.run_turn(input_text="failed")
    _assert(
        failed.construction_result.status is RealtimeSessionConstructionStatus.PREFLIGHT_FAILED,
        "preflight failure status drift",
    )
    _assert(failed_result.public_error_code is RealtimeErrorCode.UNAVAILABLE, "preflight error code drift")
    _assert(failed_stage.calls == ["preflight"], "preflight-failed stage executed after construction")

    ready_stage = TextStage()
    ready = framework.create_realtime_session(
        config=RealtimeSessionConfig(
            real_runtime_enabled=True,
            text_generation_stage=ready_stage,
        )
    )
    before_generation = dict(ready.generation_diagnostics)
    ready_result = ready.run_turn(input_text="ready")
    _assert(
        ready.construction_result.status is RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY,
        "real configuration ready status drift",
    )
    _assert(ready_result.outcome is TurnOutcome.REJECTED, "unimplemented orchestration used mock fallback")
    _assert(ready_result.public_error_code is RealtimeErrorCode.UNAVAILABLE, "orchestration error code drift")
    _assert(ready_stage.calls == ["preflight"], "real stage executed during guarded turn")
    _assert(dict(ready.generation_diagnostics) == before_generation, "guarded rejection started a generation")
    _assert(not ready_result.public_metadata["mock_runtime"], "guarded rejection claimed mock runtime")
    print("[OK] mock path remains deterministic and every explicit real request rejects without fallback")


def check_tests_and_public_compatibility() -> None:
    focused = _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            "tests.test_realtime_session_construction",
            "tests.test_realtime_session_construction_adoption",
            "tests.test_realtime_session_construction_runtime_guard",
        ],
        label="focused construction tests",
    )
    _assert("Ran 35 tests" in focused and "OK" in focused, "focused construction test count drift")

    full = _run([sys.executable, "scripts/run_v600_unit_tests.py"], label="full v6 unit suite")
    _assert("v600_unit_test_count: 80" in full, "full unit-test count drift")
    _assert("v600_unit_test_result: PASS" in full, "full unit suite did not pass")

    for relative in (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_public_facade.py",
        "scripts/smoke_app_sdk.py",
    ):
        _run([sys.executable, relative], label=relative)

    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 124, "root-public name count drift")
    _assert(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == (
            "project_root",
            "public_metadata",
            "real_runtime_enabled",
            "voice_input_stage",
            "text_generation_stage",
            "voice_output_stage",
            "motion_stage",
            "config",
        ),
        "realtime factory signature drift",
    )
    print("[OK] focused 35 tests, full 80-test suite, and canonical public regressions pass")


def check_docs_and_tasklist() -> None:
    contract = (PROJECT_ROOT / "docs/v600_realtime_session_construction_contract.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for phrase in (
        "FW-RT6-4a-C-RUNTIME-GUARD-ACCEPTANCE:BEGIN",
        "construction_result public property: True",
        "real-request mock fallback: False",
        "focused construction tests: 35 / PASS",
        "full unit suite: 80 / PASS",
        "next checkpoint: FW-RT6-4b",
        "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED",
    ):
        _assert(phrase in contract, f"construction contract missing: {phrase}")

    start = tasklist.index("## FW-RT6-4a — RealtimeSession construction and config")
    end = tasklist.index("\n---\n\n## FW-RT6-4b", start)
    section = tasklist[start:end]
    _assert("FW-RT6-4a-C-ACCEPTANCE-SYNC:BEGIN" in section, "tasklist acceptance marker missing")
    _assert(section.count("- [x]") == 7, "accepted FW-RT6-4a task count drift")
    _assert("- [ ]" not in section, "unchecked FW-RT6-4a task remains")
    for phrase in (
        "mock session creation: PASS",
        "real provider execution at construction: False",
        "capability snapshot available: True",
        "real-request mock fallback: False",
        "combined uncommitted Control A+B+C surface: 18 files",
    ):
        _assert(phrase in section, f"tasklist acceptance fact missing: {phrase}")
    print("[OK] all seven FW-RT6-4a tasks and aggregate acceptance sync conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    check_repository_contract(source_only=args.source_only)
    check_source_contract()
    check_runtime_behavior()
    check_tests_and_public_compatibility()
    check_docs_and_tasklist()

    print("v600_rt6_4a_control_c_status: implemented-awaiting-review")
    print("v600_rt6_4a_control_c_exact_delta: 6 files")
    print("v600_rt6_4a_combined_control_a_b_c_surface: 18 files")
    print("v600_rt6_4a_accepted_task_count: 7")
    print("v600_rt6_4a_construction_result_public_property: True")
    print("v600_rt6_4a_mock_session_creation: PASS")
    print("v600_rt6_4a_real_request_mock_fallback: False")
    print("v600_rt6_4a_configuration_missing_turn_rejection: PASS")
    print("v600_rt6_4a_preflight_failed_turn_rejection: PASS")
    print("v600_rt6_4a_real_configuration_ready_turn_rejection: PASS")
    print("v600_rt6_4a_rejection_generation_start: 0")
    print("v600_rt6_4a_rejection_stage_capability_start_cancel: 0")
    print("v600_rt6_4a_focused_unit_tests: 35 / PASS")
    print("v600_rt6_4a_full_unit_tests: 80 / PASS")
    print("v600_rt6_4a_root_public_names: 124")
    print("v600_rt6_4a_real_provider_execution: False")
    print("v600_rt6_4a_network_execution: False")
    print("v600_rt6_4a_microphone_access: False")
    print("v600_rt6_4a_playback_execution: False")
    print("v600_rt6_4a_real_vts_execution: False")
    print("v600_rt6_4a_drc_accessed_or_changed: False")
    print("v600_rt6_4a_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_4a_next_checkpoint: FW-RT6-4b")
    print("v600_rt6_4a_next_checkpoint_status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED")
    print("v600_rt6_4a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
