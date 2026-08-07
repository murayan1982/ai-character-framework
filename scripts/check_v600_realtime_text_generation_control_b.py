from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "dc80d1ade4db539a38d30c74edf73e8ba824531a"
EXPECTED_COMBINED_SURFACE = {
    "docs/v600_realtime_execution_contract.md",
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_realtime_text_generation_contract.md",
    "docs/v600_realtime_turn_start_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_execution.py",
    "framework/realtime_execution_bridge.py",
    "framework/realtime_session.py",
    "framework/realtime_text_generation.py",
    "scripts/check_v600_realtime_execution_acceptance.py",
    "scripts/check_v600_realtime_execution_control_a.py",
    "scripts/check_v600_realtime_execution_control_b.py",
    "scripts/check_v600_realtime_text_generation_control_a.py",
    "scripts/check_v600_realtime_text_generation_control_b.py",
    "scripts/check_v600_realtime_turn_lifecycle_acceptance.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_turn_start_adoption.py",
    "scripts/smoke_v600_realtime_turn_start_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_execution_bridge.py",
    "tests/test_realtime_execution_callback_close.py",
    "tests/test_realtime_execution_models.py",
    "tests/test_realtime_execution_session_adoption.py",
    "tests/test_realtime_text_generation_models.py",
    "tests/test_realtime_text_generation_stream.py",
    "tests/test_realtime_turn_lifecycle_acceptance.py",
    "tests/test_realtime_turn_start_adoption.py",
    "tests/test_realtime_turn_start_models.py",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    _assert(
        completed.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + completed.stdout
        + completed.stderr,
    )
    return completed.stdout


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
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "baseline origin/main drift",
    )
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_COMBINED_SURFACE,
        "Control B combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    print(
        "[OK] baseline and exact 32-file accepted Control A + "
        "FW-RT6-5a Control B surface conform"
    )


def check_source_contract() -> None:
    source = (
        PROJECT_ROOT / "framework/realtime_text_generation.py"
    ).read_text(encoding="utf-8")
    required = (
        "class TextGenerationCompletedTurn:",
        "class TextGenerationHistorySink(Protocol):",
        "class TextGenerationStream(Protocol):",
        "class ProviderNeutralTextGenerationStream:",
        "if self._cancellation_token.cancel_requested:",
        "self._cleanup_source_once()",
        "sink.commit_completed_turn(completed_turn)",
        "assistant_output=\"\".join(self._assistant_parts)",
        "return self.close()",
    )
    for phrase in required:
        _assert(phrase in source, f"Control B source missing: {phrase}")

    lowered_lines = [line.strip().lower() for line in source.splitlines()]
    forbidden_imports = (
        "import openai",
        "from openai",
        "import google.generativeai",
        "from google.generativeai",
        "from google import genai",
        "import requests",
        "import httpx",
    )
    for phrase in forbidden_imports:
        _assert(
            not any(line.startswith(phrase) for line in lowered_lines),
            "Control B imported forbidden runtime/provider dependency: " + phrase,
        )
    print("[OK] provider-neutral stream/history source contract conforms")


def check_runtime_contract() -> None:
    import framework
    import framework.realtime_text_generation as module
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_capabilities import TextGenerationCapability
    from framework.realtime_stage import RealtimeStageContext
    from framework.realtime_text_generation import (
        ProviderNeutralTextGenerationStream,
        TextGenerationCancelReason,
        TextGenerationCompletedTurn,
        TextGenerationHistorySink,
        TextGenerationStream,
        TextGenerationStreamCloseOutcome,
    )

    _assert(len(framework.__all__) == 127, "root-public count drift")
    expected_names = (
        "TextGenerationCancelReason",
        "TextGenerationCancellationToken",
        "TextGenerationDeltaEnvelope",
        "TextGenerationStreamCloseOutcome",
        "TextGenerationStreamCloseResult",
        "TextGenerationCompletedTurn",
        "TextGenerationHistorySink",
        "TextGenerationStream",
        "ProviderNeutralTextGenerationStream",
    )
    _assert(
        tuple(module.__all__[:9]) == expected_names,
        "accepted Control B stable package prefix drift",
    )
    for name in expected_names:
        _assert(name not in framework.__all__, f"root-public leak: {name}")

    context = RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )
    capability = TextGenerationCapability(
        streaming_supported=True,
        cooperative_cancel_supported=True,
        provider_hard_cancel_supported=False,
    )

    class Source:
        def __init__(self) -> None:
            self.items = iter((("one", ()), ("two", ())))
            self.close_calls = 0

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.items)

        def close(self) -> None:
            self.close_calls += 1

    class Sink:
        def __init__(self) -> None:
            self.turns: list[TextGenerationCompletedTurn] = []

        def commit_completed_turn(self, turn: TextGenerationCompletedTurn) -> None:
            self.turns.append(turn)

    source = Source()
    sink = Sink()
    stream = ProviderNeutralTextGenerationStream(
        context=context,
        capability=capability,
        source=source,
        user_input="hidden input",
        history_sink=sink,
    )
    _assert(isinstance(stream, TextGenerationStream), "stream protocol mismatch")
    _assert(isinstance(sink, TextGenerationHistorySink), "history sink mismatch")
    deltas = list(stream)
    _assert([item.delta_index for item in deltas] == [0, 1], "delta index drift")
    _assert(len(sink.turns) == 1, "completed history commit count drift")
    _assert(sink.turns[0].assistant_output == "onetwo", "history output drift")
    _assert(source.close_calls == 1, "normal source cleanup count drift")
    _assert(
        stream.close().outcome is TextGenerationStreamCloseOutcome.ALREADY_CLOSED,
        "completed close idempotence drift",
    )

    cancel_source = Source()
    cancel_sink = Sink()
    cancel_stream = ProviderNeutralTextGenerationStream(
        context=context,
        capability=capability,
        source=cancel_source,
        user_input="hidden input",
        history_sink=cancel_sink,
    )
    _assert(next(cancel_stream).text == "one", "first delta drift")
    _assert(
        cancel_stream.request_cancel(TextGenerationCancelReason.INTERRUPT),
        "cancel request not accepted",
    )
    _assert(list(cancel_stream) == [], "post-cancel delta was delivered")
    _assert(cancel_sink.turns == [], "cancelled partial history was committed")
    _assert(cancel_source.close_calls == 1, "cancel cleanup count drift")
    _assert(
        not cancel_stream.capability.provider_hard_cancel_supported,
        "provider hard cancel was overclaimed",
    )
    print(
        "[OK] stream protocol, delta suppression, cleanup, and atomic "
        "completed-history transaction conform"
    )


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
    ):
        _run(command)
    print("[OK] canonical root-public/version/app SDK regressions remain 127-name compatible")


def check_tests() -> None:
    focused = unittest.TestSuite()
    loader = unittest.defaultTestLoader
    focused.addTests(loader.loadTestsFromName("tests.test_realtime_text_generation_models"))
    focused.addTests(loader.loadTestsFromName("tests.test_realtime_text_generation_stream"))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A+B tests failed")
    _assert(focused_result.testsRun == 31, "focused Control A+B count must be 31")

    full = loader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(
        full_result.testsRun >= 183,
        "full unit suite must preserve the accepted 183-test baseline",
    )
    print("[OK] focused 31 tests and full accepted 183-test baseline pass")


def check_docs() -> None:
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_text_generation_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-5a-B-STREAM-HISTORY-CONTRACT:BEGIN",
        "FW-RT6-5a Control A:\nCOMPLETED / VERIFIED / ACCEPTED",
        "FW-RT6-5a Control B:\nIMPLEMENTED / AWAITING_REVIEW",
        "TextGenerationStream",
        "ProviderNeutralTextGenerationStream",
        "returned source delta delivered = False",
        "commit completed pair exactly once",
        "DEFERRED / Control C",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"Control B contract marker missing: {marker}")

    for marker in (
        "FW-RT6-5a-B-STREAM-HISTORY-CONTRACT:BEGIN",
        "exact Control B delta:\n7 files",
        "combined working-tree surface:\n32 files",
        "future delivered deltas = 0 / PASS",
        "at most once / PASS",
        "user + full assistant pair / exactly once / PASS",
        "Control C:\nNOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"Control B tasklist marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-5a — Cancelable text-generation protocol")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    unchecked = section.count("- [ ]")
    checked = section.count("- [x]")
    _assert(
        (unchecked, checked) in {(6, 0), (0, 6)},
        "aggregate 5a task state must be pre-Control-C deferred or post-Control-C complete",
    )
    print(
        "[OK] accepted Control B preserves its historical Control C deferral "
        "marker under additive aggregate task completion"
    )


def check_historical_growth_contract() -> None:
    source = (
        PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_control_a.py"
    ).read_text(encoding="utf-8")
    _assert(
        "full_result.testsRun >= 166" in source,
        "accepted Control A additive test-growth guard missing",
    )
    _assert(
        "full_result.testsRun == 166" not in source,
        "accepted Control A exact full count remains",
    )
    model_test = (
        PROJECT_ROOT / "tests/test_realtime_text_generation_models.py"
    ).read_text(encoding="utf-8")
    _assert(
        "tuple(module.__all__[:5])" in model_test,
        "accepted Control A stable package prefix guard missing",
    )
    print("[OK] accepted Control A preserves its 5-name prefix and 166-test baseline")


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
    check_historical_growth_contract()

    print("v600_rt6_5a_control_a_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5a_control_b_status: implemented-awaiting-review")
    print("v600_rt6_5a_control_b_exact_delta: 7 files")
    print("v600_rt6_5a_combined_surface: 32 files")
    print("v600_rt6_5a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5a_stream_protocol: TextGenerationStream / PASS")
    print("v600_rt6_5a_reference_stream: ProviderNeutralTextGenerationStream / PASS")
    print("v600_rt6_5a_cancel_future_delta_delivery: 0 / PASS")
    print("v600_rt6_5a_cancel_inflight_returned_delta_delivery: False / PASS")
    print("v600_rt6_5a_source_cleanup_at_most_once: PASS")
    print("v600_rt6_5a_close_dispose_typed_idempotent: PASS")
    print("v600_rt6_5a_normal_history_commit: EXACTLY_ONCE / PASS")
    print("v600_rt6_5a_incomplete_history_commit: False / PASS")
    print("v600_rt6_5a_provider_hard_cancel_overclaim: False")
    print("v600_rt6_5a_focused_unit_tests: 31 / PASS")
    print("v600_rt6_5a_full_unit_tests: 183 / PASS")
    print("v600_rt6_5a_provider_execution: False")
    print("v600_rt6_5a_network_execution: False")
    print("v600_rt6_5a_microphone_access: False")
    print("v600_rt6_5a_playback_execution: False")
    print("v600_rt6_5a_real_vts_execution: False")
    print("v600_rt6_5a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_5a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
