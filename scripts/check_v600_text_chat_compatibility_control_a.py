"""FW-RT6-5c accepted Control A TextChatSession identity/event scaffold gate."""
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
        f"accepted Control A growth surface drift; expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] accepted Control A scaffold is present inside exact 48-file Control B growth surface")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/facade.py").read_text(encoding="utf-8")
    for phrase in (
        "class _TextChatRealtimeTurnContext",
        "self._session_id = SessionId.new()",
        "def session_id(self) -> SessionId",
        "def on_realtime_event(",
        "def _new_realtime_turn_context(",
        "turn_id=TurnId.new()",
        "generation_id=GenerationId.new()",
        "self._next_realtime_event_sequence = EventSequence.first()",
        "def _emit_realtime_event(",
        'boundary="text_chat"',
    ):
        _assert(phrase in source, f"accepted Control A source marker missing: {phrase}")
    _assert("def interrupt_result(" in source, "Control C typed interrupt bridge missing from additive growth")
    _assert("RealtimeEventType.INTERRUPT_REQUESTED" in source, "Control C canonical interrupt request bridge missing")
    print("[OK] accepted identity/event scaffold remains intact after additive Control B/C adoption")


def check_runtime_contract() -> None:
    import framework
    from framework.facade import TextChatSession, TextChatSessionInfo
    from framework.identity import SessionId
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
            yield "ok", []

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
    session = TextChatSession(FakeLLM(), info)
    canonical = []
    session.on_realtime_event(canonical.append)
    _assert(list(session.ask_stream("question")) == ["ok"], "legacy stream response drift")
    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(isinstance(session.session_id, SessionId), "TextChatSession session_id type drift")
    _assert(session.session_id == session.session_id, "TextChatSession session_id stability drift")
    _assert(TextChatSessionInfo.__dataclass_fields__["api_version"].default == "4.0", "TextChatSessionInfo API version drift")
    _assert(canonical[0].type is RealtimeEventType.TURN_STARTED, "Control B growth did not preserve scaffold adoption")
    _assert(session.interrupt() is True, "legacy interrupt bool compatibility drift")
    _assert(canonical[-1].type is RealtimeEventType.INTERRUPT_REQUESTED, "Control C interrupt event growth missing")
    print("[OK] stable SessionId/canonical callback scaffold remains compatible with Control B/C growth")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
        [sys.executable, "scripts/smoke_public_facade.py"],
        [sys.executable, "scripts/check_v600_realtime_text_generation_provider_acceptance.py", "--source-only"],
    ):
        _run(command)
    print("[OK] root-public/version/app SDK/public facade and accepted FW-RT6-5b regressions pass")


def check_tests() -> None:
    focused = unittest.defaultTestLoader.loadTestsFromName("tests.test_text_chat_compatibility_control_a")
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused accepted Control A tests failed")
    _assert(focused_result.testsRun == 14, "accepted Control A focused baseline must remain 14")
    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"), pattern="test_*.py", top_level_dir=str(PROJECT_ROOT)
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 258, "accepted Control A 258-test baseline regressed")
    print(f"[OK] accepted Control A 14-test baseline and >=258 full-test baseline pass ({full_result.testsRun} actual)")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_text_chat_compatibility_contract.md").read_text(encoding="utf-8")
    task = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-5c Control A — identity/event scaffold",
        "COMPLETED / VERIFIED / ACCEPTED",
        "FW-RT6-5c-B-CANONICAL-ADOPTION:BEGIN",
        "FW-RT6-5c-C-INTERRUPT-AGGREGATE:BEGIN",
        "typed active interrupt:\nACCEPTED",
        "root-public names:\n127 / UNCHANGED",
    ):
        _assert(marker in contract, f"accepted Control A/current Control B contract marker missing: {marker}")
    for marker in (
        "FW-RT6-5c-A-IDENTITY-EVENT-SCAFFOLD:BEGIN",
        "status: COMPLETED / VERIFIED / ACCEPTED",
        "FW-RT6-5c-B-CANONICAL-ADOPTION:BEGIN",
        "FW-RT6-5c-C-INTERRUPT-AGGREGATE:BEGIN",
    ):
        _assert(marker in task, f"accepted Control A task marker missing: {marker}")
    print("[OK] accepted Control A docs remain synchronized under Control B growth")


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
    print("v600_rt6_5c_control_a_focused_baseline: 14 / PASS")
    print("v600_rt6_5c_control_a_full_baseline: >=258 / PASS")
    print("v600_rt6_5c_control_b_c_additive_growth_compatible: True")
    print("v600_rt6_5c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5c_interrupt_typed_bridge: True / CONTROL_C")


if __name__ == "__main__":
    main()
