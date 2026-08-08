"""FW-RT6-7b Control B input-abort/stale-completion acceptance gate."""

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

EXPECTED_HEAD = "1578a5bac8d6b58c66248bf58d9ed9e246218d1b"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_voice_input_stage_control_b.py",
    "tests/test_voice_input_stage_composition_control_b.py",
}


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
        "Control B exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact five-file FW-RT6-7b Control B surface conform")


def check_accepted_foundation_regression() -> None:
    accepted_7a = _load(
        "_fw_rt6_7b_control_b_accepted_7a",
        "scripts/check_v600_voice_input_acceptance.py",
    )
    control_a = _load(
        "_fw_rt6_7b_control_a",
        "scripts/smoke_v600_voice_input_stage_control_a.py",
    )
    accepted_7a.check_aggregate_contract()
    control_a.check_event_contract()
    control_a.check_focused_tests()
    print("[OK] accepted FW-RT6-7a and Control A lifecycle regressions conform")


def check_abort_and_generation_contract() -> None:
    import framework
    from framework.realtime_event_payloads import DiagnosticEventPayload
    from framework.realtime_generation_gate import RealtimeGenerationGate

    session = framework.create_voice_input_session()
    _require(callable(session.abort_input), "abort_input public method missing")
    _require(session.abort_input() is False, "idle abort must return False")
    _require(
        framework.RealtimeEventType.STALE_RESULT_DROPPED.value
        == "realtime.stale_result.dropped",
        "canonical stale-result event drift",
    )
    _require(
        DiagnosticEventPayload(code="voice_input_gate").code
        == "voice_input_gate",
        "typed diagnostic payload unavailable",
    )
    source = (PROJECT_ROOT / "framework/voice_input_session.py").read_text(
        encoding="utf-8"
    )
    _require("RealtimeGenerationGate" in source, "generation gate adoption missing")
    _require("GenerationAdvanceReason.CANCEL" in source, "abort invalidation missing")
    _require(
        "GenerationAdvanceReason.TURN_TERMINAL" in source,
        "normal terminal retirement missing",
    )
    _require(
        'RealtimeEventType.STALE_RESULT_DROPPED' in source,
        "stale diagnostic emission missing",
    )
    _require(
        '"provider_hard_cancel_claimed": False' in source,
        "provider hard-cancel non-claim marker missing",
    )
    _require(
        isinstance(session._generation_gate, RealtimeGenerationGate),
        "session-owned generation gate missing",
    )
    print("[OK] cooperative abort and session-owned completion gate conform")


def check_privacy_and_deferred_scope() -> None:
    import framework

    session_source = (PROJECT_ROOT / "framework/voice_input_session.py").read_text(
        encoding="utf-8"
    )
    result_fields = {item.name for item in fields(framework.VoiceInputResult)}
    _require(
        "audio_source.ref.value" not in session_source,
        "host audio source value leaked to public event code",
    )
    _require(
        '"raw_audio_retained": False' in session_source,
        "raw-audio retention marker missing",
    )
    _require(
        '"audio_path_exposed": False' in session_source,
        "path exposure marker missing",
    )
    _require(
        not {"session_id", "turn_id", "generation_id"} & result_fields,
        "Control B prematurely changed VoiceInputResult correlation",
    )
    _require(
        len(framework.__all__) == 127,
        "Control B must not change the framework root-public names",
    )
    print("[OK] audio privacy, public result shape, and 7c deferral conform")


def check_focused_tests() -> None:
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_voice_input_stage_composition_control_b.py",
    )
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    _require(result.wasSuccessful(), "Control B focused tests failed")
    _require(result.testsRun == 7, "Control B focused test count must be 7")
    print("[OK] seven focused abort/stale/privacy tests pass")


def check_docs_and_tasklist() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7b — Voice input stage composition")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [ ]") == 7 and section.count("- [x]") == 0,
        "Control B must leave FW-RT6-7b aggregate 0 / 7 CLOSED",
    )
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-7b-B-ABORT-STALE-GATE:BEGIN" in text,
            f"Control B docs marker missing: {relative}",
        )
        _require(
            "provider hard" in text.lower()
            and "FW-RT6-7c" in text
            and "P1" in text,
            f"Control B boundary deferral missing: {relative}",
        )
    print("[OK] Control B docs conform while FW-RT6-7b aggregate remains 0 / 7")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_foundation_regression()
    check_abort_and_generation_contract()
    check_privacy_and_deferred_scope()
    check_focused_tests()
    check_docs_and_tasklist()
    print("v600_rt6_7b_control_b_status: implemented-awaiting-review")
    print("v600_rt6_7b_control_b_exact_surface: 5 files")
    print("v600_rt6_7b_abort_active_once: True / PASS")
    print("v600_rt6_7b_abort_idle_or_duplicate: False / PASS")
    print("v600_rt6_7b_provider_hard_cancel_claimed: False / PASS")
    print("v600_rt6_7b_late_transcript_delivered: False / PASS")
    print("v600_rt6_7b_stale_diagnostic: exactly-once typed / PASS")
    print("v600_rt6_7b_file_path_event_exposure: False / PASS")
    print("v600_rt6_7b_raw_audio_retained: False / PASS")
    print("v600_rt6_7c_result_correlation_and_close: NOT_ADOPTED")
    print("v600_rt6_7b_partial_streaming: DEFERRED_TO_P1")
    print("v600_rt6_7b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_7b_task_count: 0 / 7 CLOSED")
    print("v600_rt6_7b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
