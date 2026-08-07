"""FW-RT6-7b Control A voice-input lifecycle/privacy gate."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "35b61a455727469e4eab340c52326372c5b203d5"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/realtime.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_voice_input_stage_control_a.py",
    "tests/test_voice_input_stage_composition_control_a.py",
}


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    _require(result.returncode == 0, "command failed: " + " ".join(command) + "\n" + result.stdout + result.stderr)
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git("diff", "--name-only", "HEAD").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {path.strip().replace("\\", "/") for path in paths if path.strip()}


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
    _require(actual == EXPECTED_SURFACE, f"Control A exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}")
    print("[OK] baseline and exact six-file FW-RT6-7b Control A surface conform")


def check_accepted_7a_regression() -> None:
    control_a = _load("_fw_rt6_7a_control_a", "scripts/smoke_v600_voice_input_control_a.py")
    control_b = _load("_fw_rt6_7a_control_b", "scripts/smoke_v600_voice_input_control_b.py")
    accepted = _load("_fw_rt6_7a_accepted", "scripts/check_v600_voice_input_acceptance.py")
    control_a.check_capability_correction()
    control_a.check_session_identity_and_event_scaffold()
    control_a.check_default_fake_path_preserved()
    control_b.check_default_fake_and_explicit_adapter_precedence()
    control_b.check_real_request_never_silently_falls_back_to_fake()
    control_b.check_session_owned_real_composition_without_provider_specific_host_objects()
    control_b.check_internal_real_chain_and_public_surface()
    control_b.check_docs_and_control_boundaries()
    accepted.check_aggregate_contract()
    print("[OK] accepted FW-RT6-7a capability/composition regression conforms")


def check_event_contract() -> None:
    import framework
    from framework.realtime_event_payloads import LifecycleEventPayload, TranscriptEventPayload

    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT.value == "realtime.voice_input.preflight", "preflight event value drift")
    _require(framework.RealtimeEventType.VOICE_INPUT_FAILED.value == "realtime.voice_input.failed", "failed event value drift")

    source = framework.VoiceInputAudioSource.from_opaque_id(
        "control_a_gate_audio",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=200),
        language="ja-JP",
    )
    session = framework.create_voice_input_session()
    events = []
    session.on_realtime_event(events.append)
    result = session.transcribe_audio_result(source)
    _require(result.text == "fake transcript", "default fake result drift")
    _require([event.type for event in events] == [
        framework.RealtimeEventType.VOICE_INPUT_PREFLIGHT,
        framework.RealtimeEventType.LISTENING_STARTED,
        framework.RealtimeEventType.LISTENING_COMPLETED,
        framework.RealtimeEventType.TRANSCRIPT_FINAL,
    ], "completed event order drift")
    _require(all(isinstance(event.payload, LifecycleEventPayload) for event in events[:3]), "lifecycle payload typing drift")
    _require(isinstance(events[-1].payload, TranscriptEventPayload), "final transcript payload typing drift")
    _require(events[-1].payload.is_final is True, "final transcript marker drift")
    _require(len({event.turn_id for event in events}) == 1, "turn correlation drift")
    _require(len({event.generation_id for event in events}) == 1, "generation correlation drift")
    print("[OK] preflight/start/completed/final transcript event order and typing conform")


def check_privacy_and_deferred_scope() -> None:
    session_source = (PROJECT_ROOT / "framework/voice_input_session.py").read_text(encoding="utf-8")
    result_source = (PROJECT_ROOT / "framework/voice_input.py").read_text(encoding="utf-8")
    _require('"audio_id": audio_source.audio_id' in session_source, "opaque audio identity event marker missing")
    _require('"source_kind": audio_source.source_kind.value' in session_source, "source kind event marker missing")
    _require('"raw_audio_retained": False' in session_source, "raw-audio retention marker missing")
    _require('"audio_path_exposed": False' in session_source, "path exposure marker missing")
    _require("audio_source.ref.value" not in session_source, "audio source value leaked to session event code")
    _require("RealtimeGenerationGate" not in session_source, "Control A prematurely adopted generation gate")
    _require("def abort_input(" not in session_source, "Control A prematurely implemented input abort")
    _require("session_id:" not in result_source and "turn_id:" not in result_source and "generation_id:" not in result_source, "Control A prematurely changed VoiceInputResult correlation")
    print("[OK] raw audio/path privacy holds and Control B/7c scope remains deferred")


def check_focused_tests() -> None:
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_voice_input_stage_composition_control_a.py",
    )
    result = unittest.TextTestRunner(verbosity=0).run(suite)
    _require(result.wasSuccessful(), "Control A focused tests failed")
    _require(result.testsRun == 6, "Control A focused test count must be 6")
    print("[OK] six focused lifecycle/privacy tests pass")


def check_docs_and_tasklist() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7b — Voice input stage composition")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(section.count("- [ ]") == 7 and section.count("- [x]") == 0, "Control A must leave FW-RT6-7b 0 / 7 CLOSED")
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require("FW-RT6-7b-A-LIFECYCLE-PRIVACY:BEGIN" in text, f"Control A docs marker missing: {relative}")
        _require("Control B" in text and "FW-RT6-7c" in text, f"later scope deferral missing: {relative}")
    print("[OK] Control A docs conform while FW-RT6-7b aggregate remains 0 / 7")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_7a_regression()
    check_event_contract()
    check_privacy_and_deferred_scope()
    check_focused_tests()
    check_docs_and_tasklist()
    print("v600_rt6_7b_control_a_status: implemented-awaiting-review")
    print("v600_rt6_7b_control_a_exact_surface: 6 files")
    print("v600_rt6_7b_event_order: preflight/start/completed/transcript-final / PASS")
    print("v600_rt6_7b_typed_final_transcript: True / PASS")
    print("v600_rt6_7b_file_path_event_exposure: False / PASS")
    print("v600_rt6_7b_raw_audio_retained: False / PASS")
    print("v600_rt6_7b_input_abort: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_7b_generation_gate: DEFERRED_TO_CONTROL_B")
    print("v600_rt6_7c_result_correlation: NOT_ADOPTED")
    print("v600_rt6_7b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_7b_task_count: 0 / 7 CLOSED")
    print("v600_rt6_7b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
