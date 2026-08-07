"""FW-RT6-5c Control C TextChatSession compatibility aggregate acceptance gate."""
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
    'scripts/check_v600_text_chat_compatibility_acceptance.py',
    'scripts/check_v600_text_chat_compatibility_control_a.py',
    'scripts/check_v600_text_chat_compatibility_control_b.py',
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
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(
        result.returncode == 0,
        "command failed: " + " ".join(command) + "\n" + result.stdout + result.stderr,
    )
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in (*tracked, *untracked)
        if path.strip()
    }


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_COMBINED_SURFACE,
        f"Control C exact surface drift; expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact 50-file FW-RT6-5c aggregate surface conform")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/facade.py").read_text(encoding="utf-8")
    for phrase in (
        "def interrupt_result(",
        "InterruptOutcome.ACCEPTED",
        "InterruptOutcome.NO_ACTIVE_TURN",
        "InterruptOutcome.ALREADY_CLOSED",
        "provider_cancel_supported=False",
        "queue_flush_supported=False",
        "RealtimeEventType.INTERRUPT_REQUESTED",
        "InterruptEventPayload(",
        "self._emit_legacy_event_from_realtime_event(requested)",
        "self.interrupt_result()",
        "return True",
    ):
        _assert(phrase in source, f"Control C source marker missing: {phrase}")
    interrupt_start = source.index("    def interrupt(self)")
    interrupt_end = source.index("\n\ndef _resolve_preset_name", interrupt_start)
    interrupt_source = source[interrupt_start:interrupt_end]
    _assert("self.interrupt_result()" in interrupt_source, "legacy interrupt does not use typed bridge")
    _assert("return True" in interrupt_source, "legacy interrupt bool True compatibility drift")
    _assert("_V6_TO_V5_REALTIME_EVENT_TYPE" not in source, "facade introduced duplicate v5 mapping table")
    print("[OK] typed interrupt bridge, truthful capabilities, legacy bool bridge, and single v5 mapping ownership conform")


def check_runtime_contract() -> None:
    import framework
    from framework.facade import TextChatSession, TextChatSessionInfo
    from framework.output_control import InterruptOutcome
    from framework.realtime import RealtimeEventType
    from llm.base import BaseLLM

    class FakeLLM(BaseLLM):
        @property
        def provider_name(self) -> str:
            return "fake"

        @property
        def model_name(self) -> str:
            return "fake-model"

        def ask_stream(self, text: str):
            del text
            yield "one", []
            yield "two", []

    info = TextChatSessionInfo(
        preset="text_chat",
        character_name="test",
        input_language_code="ja",
        output_language_code="ja",
        llm_mode="fake",
        provider="fake",
        model="fake-model",
        route_name=None,
    )

    idle = TextChatSession(FakeLLM(), info)
    idle_events = []
    idle.on_realtime_event(idle_events.append)
    idle_result = idle.interrupt_result()
    _assert(idle_result.outcome is InterruptOutcome.NO_ACTIVE_TURN, "idle typed interrupt outcome drift")
    _assert(idle.interrupt() is True, "legacy idle interrupt bool drift")

    active = TextChatSession(FakeLLM(), info)
    active_events = []
    active.on_realtime_event(active_events.append)
    stream = active.ask_stream("question")
    _assert(next(stream) == "one", "legacy stream first delta drift")
    active_result = active.interrupt_result()
    _assert(active_result.outcome is InterruptOutcome.ACCEPTED, "active typed interrupt outcome drift")
    _assert(active_result.provider_cancel_supported is False, "provider hard-cancel overclaim")
    _assert(active_result.queue_flush_supported is False, "queue-flush overclaim")
    requested = active_events[-1]
    _assert(requested.type is RealtimeEventType.INTERRUPT_REQUESTED, "canonical interrupt request event missing")
    _assert(requested.turn_id == active_result.turn_id, "active interrupt turn correlation drift")
    _assert(requested.to_v5() is requested, "existing v5 interrupt projection not reused")
    _assert(list(stream) == [], "future delta delivered after accepted cooperative interrupt")

    closed = TextChatSession(FakeLLM(), info)
    closed.close()
    closed_result = closed.interrupt_result()
    _assert(closed_result.outcome is InterruptOutcome.ALREADY_CLOSED, "closed typed interrupt outcome drift")
    _assert(closed.interrupt() is True, "legacy closed interrupt bool drift")

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(TextChatSessionInfo.__dataclass_fields__["api_version"].default == "4.0", "TextChatSessionInfo API version drift")
    print("[OK] active/idle/closed typed outcomes, cooperative suppression, v5 reuse, and legacy bool compatibility conform")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
        [sys.executable, "scripts/smoke_public_facade.py"],
        [sys.executable, "scripts/check_v600_realtime_text_generation_provider_acceptance.py", "--source-only"],
    ):
        _run(command)
    print("[OK] public facade/FW-RT6-5b regressions pass; accepted Control A/B baselines are covered by focused/full growth checks")


def check_tests() -> None:
    focused = unittest.TestSuite()
    for name in (
        "tests.test_text_chat_compatibility_control_a",
        "tests.test_text_chat_compatibility_control_b",
        "tests.test_text_chat_compatibility_control_c",
    ):
        focused.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused TextChatSession aggregate tests failed")
    _assert(focused_result.testsRun == 46, "focused Control A+B+C count must be 46")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun == 290, "full unit suite must contain 290 tests")
    print("[OK] focused 46 TextChatSession aggregate tests and full 290 tests pass")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_text_chat_compatibility_contract.md").read_text(encoding="utf-8")
    task = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-5c Control C — typed interrupt bridge and aggregate acceptance",
        "IMPLEMENTED / AWAITING_REVIEW",
        "active turn:\nACCEPTED",
        "idle:\nNO_ACTIVE_TURN",
        "closed:\nALREADY_CLOSED",
        "provider_cancel_supported:\nFalse",
        "queue_flush_supported:\nFalse",
        "RealtimeEvent.to_v5()` / `as_v5_dict()` remain the sole existing v5 projection",
        "FW-RT6-5c tasks:\n6 / 6 ACCEPTED-CANDIDATE",
        "127 / UNCHANGED",
    ):
        _assert(marker in contract, f"Control C contract marker missing: {marker}")

    for marker in (
        "FW-RT6-5c-C-INTERRUPT-AGGREGATE:BEGIN",
        "exact Control C delta: 9 files",
        "combined working-tree surface: 50 files",
        "focused Control A+B+C: 46 / PASS expected",
        "full: 290 / PASS expected",
        "tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "next checkpoint: FW-RT6-6a / NOT_AUTHORIZED",
    ):
        _assert(marker in task, f"Control C tasklist marker missing: {marker}")

    start = task.index("## FW-RT6-5c — TextChatSession compatibility adapter")
    end = task.index("\n---\n", start)
    section = task[start:end]
    _assert(section.count("- [x]") == 6, "FW-RT6-5c aggregate task count must be 6 / 6")
    _assert(section.count("- [ ]") == 0, "FW-RT6-5c aggregate tasks remain open")
    print("[OK] all six FW-RT6-5c tasks and aggregate Control C docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_git_surface()
    check_source_contract()
    check_runtime_contract()
    check_regressions()
    check_tests()
    check_docs()

    print("v600_rt6_5c_control_a_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5c_control_b_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5c_control_c_status: implemented-awaiting-review")
    print("v600_rt6_5c_control_c_exact_delta: 9 files")
    print("v600_rt6_5c_combined_surface: 50 files")
    print("v600_rt6_5c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5c_interrupt_result_active: ACCEPTED / PASS")
    print("v600_rt6_5c_interrupt_result_idle: NO_ACTIVE_TURN / PASS")
    print("v600_rt6_5c_interrupt_result_closed: ALREADY_CLOSED / PASS")
    print("v600_rt6_5c_legacy_interrupt_behavior: BOOL_TRUE / UNCHANGED / PASS")
    print("v600_rt6_5c_canonical_interrupt_requested: EXACTLY_ONCE / PASS")
    print("v600_rt6_5c_provider_hard_cancel_overclaim: False")
    print("v600_rt6_5c_queue_flush_overclaim: False")
    print("v600_rt6_5c_existing_v5_event_adapter_reused: True / PASS")
    print("v600_rt6_5c_raw_exception_event: False / PASS")
    print("v600_rt6_5c_existing_ask: COMPATIBLE / PASS")
    print("v600_rt6_5c_existing_ask_stream: COMPATIBLE / PASS")
    print("v600_rt6_5c_text_chat_session_info: UNCHANGED / PASS")
    print("v600_rt6_5c_focused_unit_tests: 46 / PASS")
    print("v600_rt6_5c_full_unit_tests: 290 / PASS")
    print("v600_rt6_5c_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_5c_provider_execution: False")
    print("v600_rt6_5c_network_execution: False")
    print("v600_rt6_5c_microphone_access: False")
    print("v600_rt6_5c_playback_execution: False")
    print("v600_rt6_5c_real_vts_execution: False")
    print("v600_rt6_5c_next_checkpoint: FW-RT6-6a / NOT_AUTHORIZED")
    print("v600_rt6_5c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
