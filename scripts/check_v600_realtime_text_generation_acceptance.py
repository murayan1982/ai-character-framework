from __future__ import annotations

import argparse
import inspect
import subprocess
import sys
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
    "scripts/check_v600_realtime_text_generation_acceptance.py",
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
    "tests/test_realtime_text_generation_stage_protocol.py",
    "tests/test_realtime_text_generation_stream.py",
    "tests/test_realtime_turn_lifecycle_acceptance.py",
    "tests/test_realtime_turn_start_adoption.py",
    "tests/test_realtime_turn_start_models.py",
}

CONTROL_B_EXPORT_PREFIX = (
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

LEGACY_STAGE_EXPORTS = (
    "RealtimeStageKind",
    "RealtimeStageContext",
    "RealtimeStageResultEnvelope",
    "VoiceInputStage",
    "TextGenerationStage",
    "VoiceOutputStage",
    "MotionStage",
)


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
        "command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
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
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_COMBINED_SURFACE,
        "Control C combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact 34-file FW-RT6-5a Control A+B+C surface conform")


def check_source_contract() -> None:
    source = (PROJECT_ROOT / "framework/realtime_text_generation.py").read_text(encoding="utf-8")
    for phrase in (
        "class CancelableTextGenerationStage(Protocol):",
        "def open_stream(",
        "cancellation_token: TextGenerationCancellationToken",
        ") -> TextGenerationStream:",
        "class TextGenerationStream(Protocol):",
        "class ProviderNeutralTextGenerationStream:",
    ):
        _assert(phrase in source, f"Control C source missing: {phrase}")

    stage_source = (PROJECT_ROOT / "framework/realtime_stage.py").read_text(encoding="utf-8")
    _assert(
        "class CancelableTextGenerationStage" not in stage_source,
        "legacy realtime_stage package was mutated by Control C",
    )
    for phrase in (
        "class TextGenerationStage(Protocol):",
        "def start(",
        "def cancel(self, *, context: RealtimeStageContext) -> bool:",
    ):
        _assert(phrase in stage_source, f"legacy text-generation stage drift: {phrase}")

    lowered_lines = [line.strip().lower() for line in source.splitlines()]
    for phrase in (
        "import openai",
        "from openai",
        "import google.generativeai",
        "from google.generativeai",
        "from google import genai",
        "import requests",
        "import httpx",
    ):
        _assert(
            not any(line.startswith(phrase) for line in lowered_lines),
            "Control C imported forbidden provider/network dependency: " + phrase,
        )
    print("[OK] additive cancel-aware stage source and legacy stage non-mutation conform")


def check_runtime_contract() -> None:
    import framework
    import framework.realtime_stage as legacy_stage_module
    import framework.realtime_text_generation as module
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime import RealtimeTurn
    from framework.realtime_capabilities import TextGenerationCapability
    from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind, TextGenerationStage
    from framework.realtime_text_generation import (
        CancelableTextGenerationStage,
        ProviderNeutralTextGenerationStream,
        TextGenerationCancelReason,
        TextGenerationCancellationToken,
        TextGenerationStream,
    )

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(
        tuple(module.__all__[:9]) == CONTROL_B_EXPORT_PREFIX,
        "accepted Control B export prefix drift",
    )
    _assert(
        tuple(module.__all__[:10]) == CONTROL_B_EXPORT_PREFIX + ("CancelableTextGenerationStage",),
        "accepted Control C 10-name export prefix drift",
    )
    _assert(
        tuple(legacy_stage_module.__all__) == LEGACY_STAGE_EXPORTS,
        "legacy realtime_stage export drift",
    )
    _assert(
        "CancelableTextGenerationStage" not in framework.__all__,
        "Control C leaked low-level stage protocol to root-public surface",
    )

    class LegacyStage:
        @property
        def stage_kind(self):
            return RealtimeStageKind.TEXT_GENERATION

        def preflight(self):
            return TextGenerationCapability()

        def capability(self):
            return TextGenerationCapability()

        def start(self, *, context, request):
            raise NotImplementedError

        def cancel(self, *, context):
            return True

        def close(self):
            return None

    _assert(isinstance(LegacyStage(), TextGenerationStage), "legacy stage compatibility drift")
    _assert(
        not isinstance(LegacyStage(), CancelableTextGenerationStage),
        "legacy stage was implicitly required to adopt open_stream",
    )

    context = RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )
    turn = RealtimeTurn(
        turn_id=context.turn_id,
        session_id=context.session_id,
        input_text="hidden input",
    )
    capability = TextGenerationCapability(
        streaming_supported=True,
        cooperative_cancel_supported=True,
        provider_hard_cancel_supported=False,
    )

    class Stage:
        @property
        def stage_kind(self):
            return RealtimeStageKind.TEXT_GENERATION

        def preflight(self):
            return capability

        def capability(self):
            return capability

        def open_stream(self, *, context, request, cancellation_token):
            return ProviderNeutralTextGenerationStream(
                context=context,
                capability=capability,
                source=iter((("one", ()), ("two", ()))),
                user_input=request.input_text,
                cancellation_token=cancellation_token,
            )

        def close(self):
            return None

    stage = Stage()
    _assert(isinstance(stage, CancelableTextGenerationStage), "new stage protocol mismatch")
    token = TextGenerationCancellationToken()
    stream = stage.open_stream(context=context, request=turn, cancellation_token=token)
    _assert(isinstance(stream, TextGenerationStream), "stage returned non-stream handle")
    _assert(stream.capability is capability, "stage/stream capability coupling drift")
    _assert(next(stream).text == "one", "first stage delta drift")
    _assert(token.request_cancel(TextGenerationCancelReason.INTERRUPT), "cancel not accepted")
    _assert(list(stream) == [], "future delta delivered after cancel")
    _assert(
        not stream.capability.provider_hard_cancel_supported,
        "cooperative cancellation overclaimed provider hard cancel",
    )

    signature = inspect.signature(CancelableTextGenerationStage.open_stream)
    for name in ("context", "request", "cancellation_token"):
        _assert(
            signature.parameters[name].kind is inspect.Parameter.KEYWORD_ONLY,
            f"open_stream parameter is not keyword-only: {name}",
        )
    print("[OK] additive stage protocol, legacy compatibility, and capability coupling conform")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
    ):
        _run(command)
    print("[OK] canonical root-public/version/app SDK regressions remain 127-name compatible")


def check_tests() -> None:
    loader = unittest.defaultTestLoader
    focused = unittest.TestSuite()
    for name in (
        "tests.test_realtime_text_generation_models",
        "tests.test_realtime_text_generation_stream",
        "tests.test_realtime_text_generation_stage_protocol",
    ):
        focused.addTests(loader.loadTestsFromName(name))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused FW-RT6-5a tests failed")
    _assert(focused_result.testsRun == 41, "focused FW-RT6-5a count must be 41")

    full = loader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 193, "full unit suite must preserve the accepted 193-test baseline")
    print("[OK] focused 41 tests and full accepted 193-test baseline pass")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_realtime_text_generation_contract.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-5a-C-STAGE-ACCEPTANCE:BEGIN",
        "FW-RT6-5a Control B:\nCOMPLETED / VERIFIED / ACCEPTED",
        "FW-RT6-5a Control C:\nIMPLEMENTED / AWAITING_REVIEW",
        "CancelableTextGenerationStage",
        "legacy TextGenerationStage implementations require open_stream:\nFalse",
        "duplicate hard-cancel field introduced:\nFalse",
        "FW-RT6-5b / NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"Control C contract marker missing: {marker}")

    for marker in (
        "FW-RT6-5a-C-STAGE-ACCEPTANCE:BEGIN",
        "exact Control C delta:\n7 files",
        "combined working-tree surface:\n34 files",
        "6 / 6 ACCEPTED-CANDIDATE",
        "TextGenerationCapability.provider_hard_cancel_supported / PASS",
        "FW-RT6-5b / NOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"Control C tasklist marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-5a — Cancelable text-generation protocol")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    _assert(section.count("- [x]") == 6, "FW-RT6-5a task count must be 6 accepted-candidate")
    _assert("- [ ]" not in section, "FW-RT6-5a contains an unchecked task")
    print("[OK] all six FW-RT6-5a tasks and aggregate Control C docs conform")


def check_historical_growth_contract() -> None:
    control_a = (PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_control_a.py").read_text(encoding="utf-8")
    control_b = (PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_control_b.py").read_text(encoding="utf-8")
    _assert("full_result.testsRun >= 166" in control_a, "Control A growth baseline drift")
    _assert("full_result.testsRun >= 183" in control_b, "Control B growth baseline drift")
    _assert("full_result.testsRun == 183" not in control_b, "Control B exact full count remains")
    _assert("tuple(module.__all__[:9])" in control_b, "Control B stable export prefix guard missing")
    print("[OK] accepted Control A/B baselines remain additive-growth compatible")


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

    print("v600_rt6_5a_control_c_status: implemented-awaiting-review")
    print("v600_rt6_5a_control_c_exact_delta: 7 files")
    print("v600_rt6_5a_combined_surface: 34 files")
    print("v600_rt6_5a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5a_cancelable_stage_protocol: PASS")
    print("v600_rt6_5a_existing_text_generation_stage_compatible: True / PASS")
    print("v600_rt6_5a_legacy_stage_exports: 7 / UNCHANGED")
    print("v600_rt6_5a_cancel_future_delta_delivery: 0 / PASS")
    print("v600_rt6_5a_source_cleanup_at_most_once: PASS")
    print("v600_rt6_5a_close_dispose_typed_idempotent: PASS")
    print("v600_rt6_5a_normal_history_commit: EXACTLY_ONCE / PASS")
    print("v600_rt6_5a_incomplete_history_commit: False / PASS")
    print("v600_rt6_5a_provider_hard_cancel_source: TextGenerationCapability.provider_hard_cancel_supported")
    print("v600_rt6_5a_provider_hard_cancel_overclaim: False")
    print("v600_rt6_5a_focused_unit_tests: 41 / PASS")
    print("v600_rt6_5a_full_unit_tests: 193 / PASS")
    print("v600_rt6_5a_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_5a_provider_execution: False")
    print("v600_rt6_5a_network_execution: False")
    print("v600_rt6_5a_microphone_access: False")
    print("v600_rt6_5a_playback_execution: False")
    print("v600_rt6_5a_real_vts_execution: False")
    print("v600_rt6_5a_next_checkpoint: FW-RT6-5b / NOT_AUTHORIZED")
    print("v600_rt6_5a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
