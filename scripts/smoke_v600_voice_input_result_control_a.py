"""FW-RT6-7c Control A additive result-correlation acceptance gate."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import unittest
from dataclasses import fields
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "9e9390f297915f953eb36961798d25f6db1f445c"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/voice_input.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_voice_input_result_control_a.py",
    "tests/test_voice_input_result_compatibility_control_a.py",
    "tests/test_voice_input_stage_composition_control_a.py",
}
LEGACY_RESULT_FIELDS = (
    "outcome",
    "text",
    "language",
    "confidence",
    "duration_ms",
    "public_error_code",
    "safe_message",
    "retryable",
    "public_metadata",
)
CORRELATION_FIELDS = ("session_id", "turn_id", "generation_id")


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
    paths = _git("diff", "--name-only", "HEAD").splitlines()
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
        "Control A exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-7c Control A surface conform")


def check_accepted_7b_regression() -> None:
    accepted_7a = _load(
        "_fw_rt6_7c_control_a_accepted_7a",
        "scripts/check_v600_voice_input_acceptance.py",
    )
    stage_a = _load(
        "_fw_rt6_7c_control_a_stage_a",
        "scripts/smoke_v600_voice_input_stage_control_a.py",
    )
    stage_b = _load(
        "_fw_rt6_7c_control_a_stage_b",
        "scripts/smoke_v600_voice_input_stage_control_b.py",
    )
    accepted_7a.check_aggregate_contract()
    stage_a.check_event_contract()
    stage_a.check_focused_tests()
    stage_b.check_abort_and_generation_contract()
    stage_b.check_focused_tests()
    print("[OK] accepted FW-RT6-7a/7b runtime behavior regressions conform")


def check_additive_result_contract() -> None:
    import framework

    result_fields = tuple(item.name for item in fields(framework.VoiceInputResult))
    _require(result_fields[:9] == LEGACY_RESULT_FIELDS, "legacy result field order drift")
    _require(result_fields[9:] == CORRELATION_FIELDS, "additive correlation field order drift")
    legacy = framework.VoiceInputResult.completed("legacy")
    _require(
        legacy.session_id is None
        and legacy.turn_id is None
        and legacy.generation_id is None,
        "legacy factory call must remain uncorrelated",
    )
    context = {
        "session_id": framework.SessionId.new(),
        "turn_id": framework.TurnId.new(),
        "generation_id": framework.GenerationId.new(),
    }
    for result in (
        framework.VoiceInputResult.completed("completed", **context),
        framework.VoiceInputResult.no_input(**context),
        framework.VoiceInputResult.interrupted(**context),
        framework.VoiceInputResult.unavailable(**context),
        framework.VoiceInputResult.failed(**context),
        framework.VoiceInputResult.closed(**context),
    ):
        _require(result.session_id == context["session_id"], "factory session ID drift")
        _require(result.turn_id == context["turn_id"], "factory turn ID drift")
        _require(
            result.generation_id == context["generation_id"],
            "factory generation ID drift",
        )
    print("[OK] legacy field/factory compatibility and additive typed IDs conform")


def check_session_result_event_correlation() -> None:
    import framework

    source = framework.VoiceInputAudioSource.from_opaque_id(
        "result_control_a_gate",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=200),
        language="ja-JP",
    )
    session = framework.create_voice_input_session()
    events = []
    legacy_events = []
    session.on_realtime_event(events.append)
    session.on_event(legacy_events.append)
    result = session.transcribe_audio_result(source)
    _require(result.is_completed, "default fake transcription drift")
    _require(result.session_id == session.session_id, "result session ID drift")
    _require(
        all(event.turn_id == result.turn_id for event in events),
        "result/event turn correlation drift",
    )
    _require(
        all(event.generation_id == result.generation_id for event in events),
        "result/event generation correlation drift",
    )
    _require(legacy_events == [], "Control A changed legacy mapping callback flow")
    _require(len(framework.__all__) == 127, "framework root-public count drift")
    print("[OK] transcribe result and canonical event context match")


def check_v5_compatibility_gates() -> None:
    for relative in (
        "scripts/smoke_v520_voice_input_public_types.py",
        "scripts/smoke_v530_voice_input_session_adapter_wiring.py",
    ):
        _run([sys.executable, relative])
    print("[OK] accepted v5.2 public factory and v5.3 adapter gates pass")


def check_focused_tests() -> None:
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_voice_input_result_compatibility_control_a.py",
    )
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    _require(result.wasSuccessful(), "Control A focused tests failed")
    _require(result.testsRun == 8, "Control A focused test count must be 8")
    print("[OK] eight focused result-correlation compatibility tests pass")


def check_docs_and_control_b_bridge() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7c — Voice input result compatibility")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [ ]") == 5 and section.count("- [x]") == 0,
        "Control A must leave FW-RT6-7c aggregate 0 / 5 CLOSED",
    )
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-7c-A-RESULT-CORRELATION:BEGIN" in text,
            f"Control A docs marker missing: {relative}",
        )
        _require(
            "FW-RT6-7c-B-COMPATIBILITY-BRIDGE:BEGIN" in text,
            f"Control B compatibility marker missing: {relative}",
        )
    session = __import__("framework").create_voice_input_session()
    listen_result = session.listen_result()
    fallback_result = session.text_fallback_result("fallback")
    session.close()
    closed_results = (
        session.listen_result(),
        session.text_fallback_result("ignored"),
    )
    _require(
        listen_result.session_id == session.session_id
        and listen_result.turn_id is not None
        and listen_result.generation_id is not None,
        "Control B listen_result correlation bridge drift",
    )
    _require(
        fallback_result.session_id == session.session_id
        and fallback_result.turn_id is not None
        and fallback_result.generation_id is not None,
        "Control B text-fallback correlation bridge drift",
    )
    _require(
        all(
            result.session_id == session.session_id
            and result.turn_id is None
            and result.generation_id is None
            for result in closed_results
        ),
        "Control B unified post-close rejection drift",
    )
    print("[OK] accepted Control A correlation remains compatible with Control B bridge")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_7b_regression()
    check_additive_result_contract()
    check_session_result_event_correlation()
    check_v5_compatibility_gates()
    check_focused_tests()
    check_docs_and_control_b_bridge()
    print("v600_rt6_7c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7c_control_a_exact_surface: 7 files")
    print("v600_rt6_7c_result_fields: legacy-9 + additive-3 / PASS")
    print("v600_rt6_7c_factory_compatibility: PASS")
    print("v600_rt6_7c_transcribe_result_event_correlation: PASS")
    print("v600_rt6_7c_adapter_correlation_authority: session-owned / PASS")
    print("v600_rt6_7c_legacy_mapping_callback_bridge: ADOPTED_BY_CONTROL_B / PASS")
    print("v600_rt6_7c_listen_text_fallback_correlation: ADOPTED_BY_CONTROL_B / PASS")
    print("v600_rt6_7c_close_rejection: ADOPTED_BY_CONTROL_B / PASS")
    print("v600_rt6_7c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_7c_task_count: 0 / 5 CLOSED")
    print("v600_rt6_7c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
