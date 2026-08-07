"""FW-RT6-4a Control B RealtimeSession construction-adoption gate.

Offline/provider-safe: verifies config normalization, additive factory/constructor
surface, session-scoped ownership, exactly-once stage preflight, immutable
capability aggregation, snapshot-derived info, typed internal construction
results, accepted mock behavior, and deferred real orchestration without provider,
network, microphone, playback, real VTube Studio, DRC, or root-draft access.
"""

from __future__ import annotations

import argparse
import ast
import inspect
from pathlib import Path
import subprocess
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "0192f941e3a2009d203535ec0c97a6ceb69050ed"
EXPECTED_COMBINED_SURFACE = {
    "docs/v600_realtime_session_construction_contract.md",
    "framework/__init__.py",
    "framework/capabilities.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_session.py",
    "framework/realtime_session_config.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_session_construction_adoption.py",
    "scripts/smoke_v600_realtime_session_construction_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_session_construction.py",
    "tests/test_realtime_session_construction_adoption.py",
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
FORBIDDEN_IMPORT_ROOTS = {
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
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


def check_repository_contract(*, source_only: bool) -> None:
    if source_only:
        print("[OK] source-only mode skips Git metadata while preserving source checks")
        return
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected FW HEAD")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(_git("branch", "--show-current") == "main", "branch must be main")
    _assert(
        _changed_paths() == EXPECTED_COMBINED_SURFACE,
        f"unexpected combined Control A+B surface: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact fourteen-file combined Control A+B surface conform")


def check_source_and_import_safety() -> None:
    session_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    capability_path = PROJECT_ROOT / "framework" / "capabilities.py"
    session_source = session_path.read_text(encoding="utf-8")
    capability_source = capability_path.read_text(encoding="utf-8")
    for path, source in ((session_path, session_source), (capability_path, capability_source)):
        tree = ast.parse(source, filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        for forbidden in FORBIDDEN_IMPORT_ROOTS:
            _assert(
                all(not name.startswith(forbidden) for name in imported),
                f"provider import leaked into {path.name}: {forbidden}",
            )

    for phrase in (
        "def _normalize_realtime_session_config(",
        "def _preflight_injected_stages(",
        "def _construction_result_for_config(",
        "config: RealtimeSessionConfig | None = None",
        "stage_capabilities=self._stage_capabilities",
        "failed_stage_kinds=self._stage_preflight_failed_kinds",
    ):
        _assert(phrase in session_source, f"session adoption source marker missing: {phrase}")
    for phrase in (
        "def _unavailable_runtime_state(",
        "def _session_realtime_snapshot(",
        "stage_capabilities: Mapping[str, object] | None = None",
        "if not real_runtime_requested:",
        '"snapshot_source": "realtime_session_stage_preflight"',
    ):
        _assert(phrase in capability_source, f"snapshot source marker missing: {phrase}")

    code = r'''
import sys
import framework
assert len(framework.__all__) == 124
assert "framework.realtime_stage" not in sys.modules
session = framework.create_realtime_session()
assert "framework.realtime_stage" not in sys.modules
assert session.capabilities.snapshot_generation == 1
session.close()
for name in (
    "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "speech_recognition", "google.genai", "xai_sdk",
):
    assert name not in sys.modules
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(
        completed.returncode == 0,
        f"root import safety failed:\n{completed.stdout}{completed.stderr}",
    )
    print("[OK] config adoption remains provider-, environment-, and execution-safe")


def check_factory_and_config_contract() -> None:
    import framework
    from framework.realtime_session import RealtimeSession
    from framework.realtime_session_config import RealtimeSessionConfig

    for callable_object, label in (
        (framework.create_realtime_session, "factory"),
        (RealtimeSession, "constructor"),
    ):
        signature = inspect.signature(callable_object)
        _assert(
            tuple(signature.parameters) == EXPECTED_FACTORY_PARAMETERS,
            f"{label} parameter drift",
        )
        _assert(
            all(
                parameter.kind is inspect.Parameter.KEYWORD_ONLY
                for parameter in signature.parameters.values()
            ),
            f"{label} parameter is not keyword-only",
        )
        _assert(signature.parameters["config"].default is None, "config default drift")

    config = RealtimeSessionConfig()
    for action in (
        lambda: framework.create_realtime_session(config=object()),
        lambda: framework.create_realtime_session(
            config=config,
            real_runtime_enabled=False,
        ),
    ):
        try:
            action()
        except TypeError as error:
            _assert("credential" not in str(error).lower(), "private detail leaked")
        else:
            raise AssertionError("invalid config composition was accepted")
    print("[OK] additive eight-parameter config normalization contract conforms")


def check_construction_behavior() -> None:
    import framework
    from framework.realtime_session_config import (
        RealtimeSessionConfig,
        RealtimeSessionConstructionStatus,
    )
    from tests.test_realtime_session_construction_adoption import (
        _FakeStage,
        _all_stages,
    )
    from framework.realtime_stage import RealtimeStageKind

    first = framework.create_realtime_session()
    second = framework.create_realtime_session()
    _assert(first.info.session_id != second.info.session_id, "session IDs are not unique")
    _assert(first.capabilities.session_id == first.info.session_id, "snapshot ID mismatch")
    _assert(first.capabilities is first.capabilities, "snapshot is not stable")
    _assert(first.info.supports_motion is False, "default mock motion overclaim")
    _assert(
        first._construction_result.status is RealtimeSessionConstructionStatus.MOCK_READY,
        "default internal construction result drift",
    )
    _assert(first._event_hub is not second._event_hub, "event hub ownership drift")
    _assert(
        first._terminal_registry is not second._terminal_registry,
        "terminal registry ownership drift",
    )
    _assert(first._generation_gate is not second._generation_gate, "gate ownership drift")
    first.close()
    second.close()

    mock_stages = _all_stages()
    mock_session = framework.create_realtime_session(
        config=RealtimeSessionConfig(
            voice_input_stage=mock_stages["voice_input"],
            text_generation_stage=mock_stages["text_generation"],
            voice_output_stage=mock_stages["voice_output"],
            motion_stage=mock_stages["motion"],
        )
    )
    _assert(
        all(stage.calls == ["preflight"] for stage in mock_stages.values()),
        "mock construction did not preflight each stage exactly once",
    )
    _assert(mock_session.capabilities.supports_motion is False, "mock snapshot changed")
    mock_result = mock_session.run_turn(input_text="control-b-mock")
    _assert(mock_result.outcome.value == "completed", "mock turn regression")
    _assert(
        all(stage.calls == ["preflight"] for stage in mock_stages.values()),
        "mock run_turn executed an injected stage",
    )
    mock_session.close()
    _assert(
        all(stage.calls == ["preflight", "close"] for stage in mock_stages.values()),
        "stage close/preflight count drift",
    )

    real_stages = _all_stages()
    real_session = framework.create_realtime_session(
        config=RealtimeSessionConfig(
            real_runtime_enabled=True,
            voice_input_stage=real_stages["voice_input"],
            text_generation_stage=real_stages["text_generation"],
            voice_output_stage=real_stages["voice_output"],
            motion_stage=real_stages["motion"],
        )
    )
    snapshot = real_session.capabilities
    info = real_session.info
    _assert(snapshot.supports_text_chat, "real text preflight not projected")
    _assert(snapshot.supports_voice_input, "real voice input preflight not projected")
    _assert(snapshot.supports_voice_output, "real voice output preflight not projected")
    _assert(snapshot.supports_motion, "real motion preflight not projected")
    _assert(snapshot.real_runtime_enabled is False, "real orchestration overclaim")
    _assert(info.supports_motion == snapshot.supports_motion, "info/snapshot drift")
    _assert(
        real_session._construction_result.status
        is RealtimeSessionConstructionStatus.REAL_CONFIGURATION_READY,
        "real configuration status drift",
    )
    _assert(
        real_session._construction_result.runtime_executable is False,
        "Control B overclaims runtime execution",
    )
    _assert(
        all(stage.calls == ["preflight"] for stage in real_stages.values()),
        "real construction executed a non-preflight stage method",
    )
    real_session.close()

    missing = framework.create_realtime_session(
        config=RealtimeSessionConfig(real_runtime_enabled=True)
    )
    _assert(
        missing._construction_result.status
        is RealtimeSessionConstructionStatus.CONFIGURATION_INCOMPLETE,
        "missing text stage was not typed",
    )
    _assert(
        missing._construction_result.missing_stage_kinds == ("text_generation",),
        "missing stage kind drift",
    )
    missing.close()

    failing_stage = _FakeStage(
        RealtimeStageKind.TEXT_GENERATION,
        preflight_error=RuntimeError(r"credential=C:\private\provider-token"),
    )
    failed = framework.create_realtime_session(
        config=RealtimeSessionConfig(
            real_runtime_enabled=True,
            text_generation_stage=failing_stage,
        )
    )
    _assert(
        failed._construction_result.status
        is RealtimeSessionConstructionStatus.PREFLIGHT_FAILED,
        "preflight failure was not typed",
    )
    public_repr = repr(failed._construction_result).lower()
    _assert("credential" not in public_repr and "private" not in public_repr, "raw error leaked")
    failed.close()
    print("[OK] ownership, preflight, snapshot aggregation, and typed internal results conform")


def _run_command(command: list[str], *, label: str) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"{label} failed:\n{output}")
    return output


def check_tests_and_public_regressions() -> None:
    focused = _run_command(
        [
            sys.executable,
            "-m",
            "unittest",
            "-v",
            "tests.test_realtime_session_construction",
            "tests.test_realtime_session_construction_adoption",
        ],
        label="focused construction tests",
    )
    _assert("Ran 25 tests" in focused and "OK" in focused, "focused test count drift")

    full = _run_command(
        [sys.executable, "scripts/run_v600_unit_tests.py"],
        label="full v6 unit suite",
    )
    _assert("v600_unit_test_count: 70" in full, "full unit count drift")
    _assert("v600_unit_test_result: PASS" in full, "full unit suite did not pass")

    for relative in (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_public_facade.py",
        "scripts/smoke_app_sdk.py",
    ):
        _run_command([sys.executable, relative], label=relative)
    print("[OK] focused 25 tests, full 70 tests, and canonical public regressions pass")


def check_docs() -> None:
    text = (
        PROJECT_ROOT / "docs" / "v600_realtime_session_construction_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "FW-RT6-4a-B-CONSTRUCTION-ADOPTION:BEGIN",
        "Control A: ACCEPTED",
        "Control B exact delta: 5 files",
        "combined uncommitted Control A+B surface: 14 files",
        "stage preflight: exactly once per injected stage",
        "real provider execution at construction: False",
        "Control C: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _assert(phrase in text, f"construction contract missing: {phrase}")
    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(encoding="utf-8")
    _assert(
        "## FW-RT6-4a — RealtimeSession construction and config" in tasklist,
        "tasklist checkpoint missing",
    )
    _assert(
        "- [ ] provider-neutral `RealtimeSessionConfig`" in tasklist,
        "aggregate tasklist was completed before acceptance",
    )
    print("[OK] Control B contract is truthful and aggregate tasklist remains deferred")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    check_repository_contract(source_only=args.source_only)
    check_source_and_import_safety()
    check_factory_and_config_contract()
    check_construction_behavior()
    check_tests_and_public_regressions()
    check_docs()

    print("v600_rt6_4a_control_b_status: implemented-awaiting-review")
    print("v600_rt6_4a_control_b_exact_delta: 5 files")
    print("v600_rt6_4a_combined_control_a_b_surface: 14 files")
    print("v600_rt6_4a_factory_constructor_parameters: 8 / keyword-only")
    print("v600_rt6_4a_config_legacy_mixing_rejected: True")
    print("v600_rt6_4a_stage_preflight_per_injected_stage: 1")
    print("v600_rt6_4a_stage_capability_start_cancel_at_construction: 0")
    print("v600_rt6_4a_snapshot_generation: 1 / stable")
    print("v600_rt6_4a_snapshot_session_id_correlation: PASS")
    print("v600_rt6_4a_info_snapshot_summary_consistency: PASS")
    print("v600_rt6_4a_configuration_missing_internal_typed_result: PASS")
    print("v600_rt6_4a_preflight_failure_internal_typed_result: PASS")
    print("v600_rt6_4a_focused_unit_tests: 25 / PASS")
    print("v600_rt6_4a_full_unit_tests: 70 / PASS")
    print("v600_rt6_4a_real_runtime_enabled: False")
    print("v600_rt6_4a_provider_execution: False")
    print("v600_rt6_4a_network_execution: False")
    print("v600_rt6_4a_microphone_access: False")
    print("v600_rt6_4a_playback_execution: False")
    print("v600_rt6_4a_real_vts_execution: False")
    print("v600_rt6_4a_drc_accessed_or_changed: False")
    print("v600_rt6_4a_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_4a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_4a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
