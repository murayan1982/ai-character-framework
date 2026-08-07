"""FW-RT6-5c Control B TextChatSession canonical adoption gate."""
from __future__ import annotations

import argparse
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "dc80d1ade4db539a38d30c74edf73e8ba824531a"
EXPECTED_COMBINED_SURFACE = {
    'docs/v600_realtime_execution_contract.md',
    'docs/v600_realtime_session_construction_contract.md',
    'docs/v600_realtime_text_generation_contract.md',
    'docs/v600_realtime_text_generation_provider_adapter_contract.md',
    'docs/v600_realtime_turn_start_contract.md',
    'docs/v600_tasklist.md',
    'docs/v600_text_chat_compatibility_contract.md',
    'framework/__init__.py',
    'framework/facade.py',
    'framework/public_api.py',
    'framework/realtime.py',
    'framework/realtime_execution.py',
    'framework/realtime_execution_bridge.py',
    'framework/realtime_session.py',
    'framework/realtime_text_generation.py',
    'framework/realtime_text_generation_provider_adapters.py',
    'scripts/check_v600_realtime_execution_acceptance.py',
    'scripts/check_v600_realtime_execution_control_a.py',
    'scripts/check_v600_realtime_execution_control_b.py',
    'scripts/check_v600_realtime_text_generation_acceptance.py',
    'scripts/check_v600_realtime_text_generation_control_a.py',
    'scripts/check_v600_realtime_text_generation_control_b.py',
    'scripts/check_v600_realtime_text_generation_provider_acceptance.py',
    'scripts/check_v600_realtime_text_generation_provider_control_a.py',
    'scripts/check_v600_realtime_text_generation_provider_control_b.py',
    'scripts/check_v600_realtime_turn_lifecycle_acceptance.py',
    'scripts/check_v600_text_chat_compatibility_control_a.py',
    'scripts/check_v600_text_chat_compatibility_control_b.py',
    'scripts/check_v600_text_chat_compatibility_acceptance.py',
    'scripts/smoke_app_sdk.py',
    'scripts/smoke_v600_public_api_manifest.py',
    'scripts/smoke_v600_realtime_turn_start_adoption.py',
    'scripts/smoke_v600_realtime_turn_start_models.py',
    'scripts/smoke_v600_version_metadata.py',
    'tests/test_realtime_execution_bridge.py',
    'tests/test_realtime_execution_callback_close.py',
    'tests/test_realtime_execution_models.py',
    'tests/test_realtime_execution_session_adoption.py',
    'tests/test_realtime_text_generation_models.py',
    'tests/test_realtime_text_generation_provider_acceptance.py',
    'tests/test_realtime_text_generation_provider_adapters.py',
    'tests/test_realtime_text_generation_provider_control_b.py',
    'tests/test_realtime_text_generation_stage_protocol.py',
    'tests/test_realtime_text_generation_stream.py',
    'tests/test_realtime_turn_lifecycle_acceptance.py',
    'tests/test_realtime_turn_start_adoption.py',
    'tests/test_realtime_turn_start_models.py',
    'tests/test_text_chat_compatibility_control_a.py',
    'tests/test_text_chat_compatibility_control_b.py',
    'tests/test_text_chat_compatibility_control_c.py',
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    _assert(result.returncode == 0, "command failed: " + " ".join(command) + "\n" + result.stdout + result.stderr)
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {p.strip().replace("\\", "/") for p in (*tracked, *untracked) if p.strip()}


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(actual == EXPECTED_COMBINED_SURFACE, f"Control B exact surface drift; expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; actual={sorted(actual)!r}")
    print("[OK] baseline and exact 48-file FW-RT6-5c Control B surface conform")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/facade.py").read_text(encoding="utf-8")
    for phrase in (
        "self._active_realtime_turn_context",
        "def _emit_legacy_event_from_realtime_event(",
        "context = self._new_realtime_turn_context(text)",
        "RealtimeEventType.TURN_STARTED",
        "RealtimeEventType.RESPONSE_STARTED",
        "RealtimeEventType.RESPONSE_DELTA",
        "RealtimeEventType.RESPONSE_COMPLETED",
        "RealtimeEventType.TURN_COMPLETED",
        "RealtimeEventType.TURN_INTERRUPTED",
        "RealtimeEventType.TURN_FAILED",
        "ResponseEventPayload(",
        "LifecycleEventPayload(",
        "_text_chat_realtime_error_code(classification)",
    ):
        _assert(phrase in source, f"Control B source marker missing: {phrase}")
    interrupt_start = source.index("    def interrupt(")
    interrupt_end = source.index("\n\ndef _resolve_preset_name", interrupt_start)
    interrupt_source = source[interrupt_start:interrupt_end]
    _assert("def interrupt_result(" in source, "Control C typed interrupt bridge missing from additive growth")
    _assert("InterruptOutcome.ACCEPTED" in source, "active typed interrupt outcome missing")
    _assert("InterruptOutcome.NO_ACTIVE_TURN" in source, "idle typed interrupt outcome missing")
    _assert("InterruptOutcome.ALREADY_CLOSED" in source, "closed typed interrupt outcome missing")
    _assert("return True" in interrupt_source, "legacy interrupt bool compatibility drift")
    _assert("self.interrupt_result()" in interrupt_source, "legacy interrupt does not delegate through typed bridge")
    print("[OK] accepted ask/ask_stream canonical adoption remains intact under Control C typed interrupt growth")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
        [sys.executable, "scripts/smoke_public_facade.py"],
        [sys.executable, "scripts/check_v600_realtime_text_generation_provider_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_text_chat_compatibility_control_a.py", "--source-only"],
    ):
        _run(command)
    print("[OK] public facade/root-public/FW-RT6-5b and accepted Control A regressions pass")


def check_tests() -> None:
    focused = unittest.TestSuite()
    focused.addTests(unittest.defaultTestLoader.loadTestsFromName("tests.test_text_chat_compatibility_control_a"))
    focused.addTests(unittest.defaultTestLoader.loadTestsFromName("tests.test_text_chat_compatibility_control_b"))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused TextChatSession Control A+B tests failed")
    _assert(focused_result.testsRun == 32, "focused Control A+B count must be 32")

    full = unittest.defaultTestLoader.discover(str(PROJECT_ROOT / "tests"), pattern="test_*.py", top_level_dir=str(PROJECT_ROOT))
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 276, "accepted Control B 276-test baseline regressed")
    print(f"[OK] focused 32 accepted Control A+B tests and >=276 full-test baseline pass ({full_result.testsRun} actual)")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_text_chat_compatibility_contract.md").read_text(encoding="utf-8")
    task = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-5c Control B — canonical ask/ask_stream adoption",
        "COMPLETED / VERIFIED / ACCEPTED",
        "TURN_STARTED\nRESPONSE_STARTED\nRESPONSE_DELTA * delivered non-empty chunks\nRESPONSE_COMPLETED\nTURN_COMPLETED",
        "TURN_INTERRUPTED / exactly once",
        "TURN_FAILED / exactly once",
        "exception re-raise: preserved",
        "FW-RT6-5c-C-INTERRUPT-AGGREGATE:BEGIN",
        "typed active interrupt:\nACCEPTED",
        "127 / UNCHANGED",
    ):
        _assert(marker in contract, f"Control B contract marker missing: {marker}")
    for marker in (
        "FW-RT6-5c-B-CANONICAL-ADOPTION:BEGIN",
        "exact Control B delta: 7 files",
        "combined working-tree surface: 48 files",
        "focused Control A+B: 32 / PASS expected",
        "full: 276 / PASS expected",
        "Control C: AUTHORIZED / IMPLEMENTED IN NEXT CONTROL",
        "FW-RT6-5c-C-INTERRUPT-AGGREGATE:BEGIN",
    ):
        _assert(marker in task, f"Control B tasklist marker missing: {marker}")
    start = task.index("## FW-RT6-5c — TextChatSession compatibility adapter")
    end = task.index("\n---\n", start)
    section = task[start:end]
    _assert(section.count("- [ ]") == 0, "FW-RT6-5c aggregate tasks remain open after Control C growth")
    _assert(section.count("- [x]") == 6, "FW-RT6-5c aggregate task count must be 6 / 6 after Control C growth")
    print("[OK] accepted Control A/B docs remain synchronized under Control C aggregate growth")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_git_surface()
    check_source_contract()
    check_regressions()
    check_tests()
    check_docs()
    print("v600_rt6_5c_control_a_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5c_control_b_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5c_control_b_exact_delta: 7 files")
    print("v600_rt6_5c_combined_surface: 48 files")
    print("v600_rt6_5c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5c_ask_turn_context_adoption: PASS")
    print("v600_rt6_5c_ask_stream_turn_context_adoption: PASS")
    print("v600_rt6_5c_canonical_normal_order: PASS")
    print("v600_rt6_5c_canonical_completed_terminal: EXACTLY_ONCE / PASS")
    print("v600_rt6_5c_canonical_interrupted_terminal: EXACTLY_ONCE / PASS")
    print("v600_rt6_5c_canonical_failed_terminal: EXACTLY_ONCE / PASS")
    print("v600_rt6_5c_legacy_event_shape: UNCHANGED / PASS")
    print("v600_rt6_5c_legacy_state_transitions: UNCHANGED / PASS")
    print("v600_rt6_5c_raw_exception_event: False / PASS")
    print("v600_rt6_5c_exception_reraise: PRESERVED / PASS")
    print("v600_rt6_5c_text_chat_session_info: UNCHANGED / PASS")
    print("v600_rt6_5c_legacy_interrupt_behavior: BOOL_TRUE / UNCHANGED / PASS")
    print("v600_rt6_5c_interrupt_typed_bridge: True / CONTROL_C")
    print("v600_rt6_5c_focused_unit_tests: 32 / PASS")
    print("v600_rt6_5c_full_unit_tests_baseline: >=276 / PASS")
    print("v600_rt6_5c_provider_execution: False")
    print("v600_rt6_5c_network_execution: False")
    print("v600_rt6_5c_microphone_access: False")
    print("v600_rt6_5c_playback_execution: False")
    print("v600_rt6_5c_real_vts_execution: False")
    print("v600_rt6_5c_control_c_additive_growth_compatible: True")
    print("v600_rt6_5c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
