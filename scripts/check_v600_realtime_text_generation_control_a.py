"""FW-RT6-5a Control A cancel-aware text-generation model/token gate."""

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
        check=False,
        capture_output=True,
        text=True,
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
        "Control A combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    print(
        "[OK] baseline and exact 30-file accepted 4c + "
        "FW-RT6-5a Control A surface conform"
    )


def check_source_contract() -> None:
    source = (
        PROJECT_ROOT / "framework/realtime_text_generation.py"
    ).read_text(encoding="utf-8")
    required = (
        "class TextGenerationCancelReason(str, Enum):",
        "class TextGenerationCancellationToken:",
        "class TextGenerationDeltaEnvelope:",
        "class TextGenerationStreamCloseOutcome(str, Enum):",
        "class TextGenerationStreamCloseResult:",
        "self._lock = threading.Lock()",
        "if self._reason is not None:",
        "text: str = field(repr=False)",
        "public_mapping(self.public_metadata)",
    )
    for phrase in required:
        _assert(phrase in source, f"Control A source missing: {phrase}")

    lowered_lines = [line.strip().lower() for line in source.splitlines()]
    forbidden_imports = (
        "import openai",
        "from openai",
        "import google.generativeai",
        "from google.generativeai",
        "import requests",
        "import httpx",
    )
    for phrase in forbidden_imports:
        _assert(
            not any(line.startswith(phrase) for line in lowered_lines),
            "Control A imported forbidden runtime/provider dependency: " + phrase,
        )
    print("[OK] provider-neutral model/token source contract conforms")


def check_runtime_contract() -> None:
    import framework
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import RealtimeStageContext
    from framework.realtime_text_generation import (
        TextGenerationCancelReason,
        TextGenerationCancellationToken,
        TextGenerationDeltaEnvelope,
    )

    _assert(len(framework.__all__) == 127, "root-public count drift")
    for name in (
        "TextGenerationCancelReason",
        "TextGenerationCancellationToken",
        "TextGenerationDeltaEnvelope",
        "TextGenerationStreamCloseOutcome",
        "TextGenerationStreamCloseResult",
    ):
        _assert(
            name not in framework.__all__,
            f"Control A leaked root-public name: {name}",
        )

    token = TextGenerationCancellationToken()
    barrier = threading.Barrier(8)
    accepted: list[bool] = []
    lock = threading.Lock()

    def request_cancel() -> None:
        barrier.wait()
        result = token.request_cancel(TextGenerationCancelReason.INTERRUPT)
        with lock:
            accepted.append(result)

    threads = [threading.Thread(target=request_cancel) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2.0)
        _assert(not thread.is_alive(), "cancellation token thread did not terminate")

    _assert(
        accepted.count(True) == 1,
        "cancellation token accepted more than once",
    )
    _assert(
        token.reason is TextGenerationCancelReason.INTERRUPT,
        "first cancellation reason drift",
    )

    context = RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )
    delta = TextGenerationDeltaEnvelope(
        context=context,
        delta_index=0,
        text="private",
    )
    _assert(delta.session_id == context.session_id, "delta session identity drift")
    _assert(delta.turn_id == context.turn_id, "delta turn identity drift")
    _assert(
        delta.generation_id == context.generation_id,
        "delta generation identity drift",
    )
    _assert("private" not in repr(delta), "delta repr leaked text")
    print(
        "[OK] thread-safe first-reason-wins cancellation and correlated "
        "delta model conform"
    )


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
    ):
        _run(command)
    print(
        "[OK] canonical root-public/version/app SDK regressions remain "
        "127-name compatible"
    )


def check_tests() -> None:
    focused = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_text_generation_models"
    )
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A tests failed")
    _assert(focused_result.testsRun == 14, "focused Control A count must be 14")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 166, "full unit suite must preserve the accepted 166-test baseline")
    print("[OK] focused 14 tests and full accepted 166-test baseline pass")


def check_docs() -> None:
    execution = (
        PROJECT_ROOT / "docs/v600_realtime_execution_contract.md"
    ).read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_text_generation_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(
        encoding="utf-8"
    )

    for marker in (
        "FW-RT6-4c-D-ACCEPTANCE-SYNC:BEGIN",
        "COMPLETED / VERIFIED / ACCEPTED",
        "FW-RT6-5a exact contract review completed / Control A authorized",
    ):
        _assert(
            marker in execution,
            f"4c acceptance sync missing from execution contract: {marker}",
        )
        _assert(
            marker in tasklist,
            f"4c acceptance sync missing from tasklist: {marker}",
        )

    for marker in (
        "FW-RT6-5a Control A",
        "framework.realtime_text_generation",
        "first reason wins:",
        "Conversation-history transaction rule",
        "TextGenerationCapability.provider_hard_cancel_supported",
        "127 / UNCHANGED",
        "DEFERRED / Control B",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"5a Control A contract marker missing: {marker}")

    for marker in (
        "FW-RT6-5a-A-MODEL-TOKEN-CONTRACT:BEGIN",
        "exact Control A delta:",
        "9 files",
        "combined working-tree surface:",
        "30 files",
        "THREAD-SAFE / IDEMPOTENT / FIRST-REASON-WINS",
        "Control B:",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"tasklist Control A marker missing: {marker}")

    section_start = tasklist.index(
        "## FW-RT6-5a — Cancelable text-generation protocol"
    )
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    unchecked = section.count("- [ ]")
    checked = section.count("- [x]")
    _assert(
        (unchecked, checked) in {(6, 0), (0, 6)},
        "aggregate FW-RT6-5a task state must be pre-Control-C deferred or post-Control-C complete",
    )
    print(
        "[OK] 4c acceptance sync and accepted 5a Control A contract remain "
        "compatible with additive aggregate task completion"
    )


def check_historical_gate_growth_contract() -> None:
    for relative in (
        "scripts/check_v600_realtime_execution_control_a.py",
        "scripts/check_v600_realtime_execution_control_b.py",
        "scripts/check_v600_realtime_execution_acceptance.py",
    ):
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "full_result.testsRun >= 152" in source,
            f"historical additive test growth guard missing: {relative}",
        )
        _assert(
            "full_result.testsRun == 152" not in source,
            f"historical exact full count remains: {relative}",
        )
    print(
        "[OK] accepted FW-RT6-4c gates preserve the 152-test baseline "
        "under additive future tests"
    )


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
    check_historical_gate_growth_contract()

    print("v600_rt6_4c_acceptance_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5a_control_a_status: implemented-awaiting-review")
    print("v600_rt6_5a_control_a_exact_delta: 9 files")
    print("v600_rt6_5a_combined_surface: 30 files")
    print("v600_rt6_5a_stable_package: framework.realtime_text_generation")
    print("v600_rt6_5a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5a_cancel_token_thread_safe: True")
    print("v600_rt6_5a_cancel_token_first_reason_wins: True")
    print(
        "v600_rt6_5a_delta_identity: "
        "session_id / turn_id / generation_id / delta_index"
    )
    print("v600_rt6_5a_typed_close_result_models: 2")
    print(
        "v600_rt6_5a_history_transaction_rule: "
        "FIXED / IMPLEMENTATION_DEFERRED"
    )
    print(
        "v600_rt6_5a_provider_hard_cancel_source: "
        "TextGenerationCapability.provider_hard_cancel_supported"
    )
    print("v600_rt6_5a_focused_unit_tests: 14 / PASS")
    print("v600_rt6_5a_full_unit_tests: 166 / PASS")
    print("v600_rt6_5a_provider_execution: False")
    print("v600_rt6_5a_network_execution: False")
    print("v600_rt6_5a_microphone_access: False")
    print("v600_rt6_5a_playback_execution: False")
    print("v600_rt6_5a_real_vts_execution: False")
    print("v600_rt6_5a_control_b: NOT_AUTHORIZED")
    print("v600_rt6_5a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
