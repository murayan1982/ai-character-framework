"""FW-RT6-5b Control C aggregate provider-adapter acceptance gate."""

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
    'framework/__init__.py',
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
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_COMBINED_SURFACE,
        "Control C combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact 42-file FW-RT6-5b aggregate surface conform")


def check_source_contract() -> None:
    source = (
        PROJECT_ROOT / "framework/realtime_text_generation_provider_adapters.py"
    ).read_text(encoding="utf-8")
    for phrase in (
        "class OpenAITextGenerationAdapter",
        "class XAITextGenerationAdapter",
        "class GeminiTextGenerationAdapter",
        "class FallbackTextGenerationAdapter",
        "class RouterTextGenerationAdapter",
        "provider_hard_cancel_supported=False",
        "self._delivered_delta_count == 0",
        "self._route_selector(request)",
    ):
        _assert(phrase in source, f"provider aggregate source marker missing: {phrase}")

    lowered = [line.strip().lower() for line in source.splitlines()]
    for phrase in (
        "import openai",
        "from openai",
        "import google",
        "from google",
        "os.getenv",
        "os.environ",
        "import requests",
        "import httpx",
    ):
        _assert(
            not any(line.startswith(phrase) or phrase in line for line in lowered),
            "provider aggregate source imported/read forbidden runtime material: " + phrase,
        )
    _assert("client.chats.create" not in source, "Gemini mutable chat dependency adopted")
    print("[OK] provider adapter source remains injected/provider-safe and hard-cancel truthful")


def check_runtime_contract() -> None:
    import framework
    from framework.realtime_text_generation import TextGenerationProviderError
    import framework.realtime_text_generation_provider_adapters as adapters

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert("TextGenerationProviderError" not in framework.__all__, "provider error leaked to root")
    _assert(
        tuple(adapters.__all__)
        == (
            "OpenAITextGenerationAdapter",
            "XAITextGenerationAdapter",
            "GeminiTextGenerationAdapter",
            "FallbackTextGenerationAdapter",
            "RouterTextGenerationAdapter",
        ),
        "provider adapter export surface drift",
    )
    _assert(
        issubclass(TextGenerationProviderError, Exception),
        "provider error type contract drift",
    )
    print("[OK] 127-name root surface and exact five-adapter explicit package conform")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
    ):
        _run(command)
    print("[OK] canonical root-public/version/app SDK regressions remain 127-name compatible")


def check_tests() -> None:
    control_a = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_text_generation_provider_adapters"
    )
    control_b = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_text_generation_provider_control_b"
    )
    control_c = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_text_generation_provider_acceptance"
    )
    focused = unittest.TestSuite((control_a, control_b, control_c))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused provider aggregate tests failed")
    _assert(focused_result.testsRun == 51, "focused Control A+B+C count must be 51")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 244, "full unit suite must preserve the accepted 244-test baseline")
    print(f"[OK] focused 51 provider aggregate tests and full {full_result.testsRun} tests pass (accepted baseline >=244)")


def check_docs() -> None:
    provider_contract = (
        PROJECT_ROOT / "docs/v600_realtime_text_generation_provider_adapter_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-5b-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-5b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-5b Control C aggregate acceptance candidate",
        "raw provider exception public:\nFalse",
        "provider hard-cancel overclaim:\nFalse",
        "FW-RT6-5c / NOT_AUTHORIZED",
    ):
        _assert(marker in provider_contract, f"provider aggregate contract marker missing: {marker}")

    for marker in (
        "FW-RT6-5b-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-5b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "exact Control C delta:\n6 files",
        "combined working-tree surface:\n42 files",
        "task",
    ):
        _assert(marker in tasklist, f"tasklist aggregate marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-5b — LLM provider adapters")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    _assert(section.count("- [x]") == 7, "FW-RT6-5b all seven tasks must be accepted-candidate")
    _assert(section.count("- [ ]") == 0, "FW-RT6-5b unchecked task remains")
    print("[OK] all seven FW-RT6-5b tasks and aggregate Control C docs conform")


def check_prior_gate_growth() -> None:
    control_a = (
        PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_provider_control_a.py"
    ).read_text(encoding="utf-8")
    control_b = (
        PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_provider_control_b.py"
    ).read_text(encoding="utf-8")
    accepted_5a = (
        PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_acceptance.py"
    ).read_text(encoding="utf-8")

    _assert("full_result.testsRun >= 213" in control_a, "Control A growth guard missing")
    _assert("full_result.testsRun >= 234" in control_b, "Control B growth guard missing")
    _assert("full_result.testsRun >= 193" in accepted_5a, "FW-RT6-5a growth guard missing")
    _assert("(unchecked, checked) in ((7, 0), (0, 7))" in control_a, "Control A task growth guard missing")
    _assert("(unchecked, checked) in ((7, 0), (0, 7))" in control_b, "Control B task growth guard missing")
    print("[OK] accepted FW-RT6-5a and Control A/B baselines remain additive-growth compatible")


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
    check_prior_gate_growth()

    print("v600_rt6_5b_control_c_status: implemented-awaiting-review")
    print("v600_rt6_5b_control_c_exact_delta: 6 files")
    print("v600_rt6_5b_combined_surface: 42 files")
    print("v600_rt6_5b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5b_openai_fake_stream: PASS")
    print("v600_rt6_5b_gemini_fake_stream: PASS")
    print("v600_rt6_5b_xai_fake_stream: PASS")
    print("v600_rt6_5b_direct_provider_cancel_future_delta_delivery: 0 / PASS")
    print("v600_rt6_5b_fallback_pre_delta_failure: FALLBACK / PASS")
    print("v600_rt6_5b_fallback_post_delta_failure: NO_FALLBACK / PASS")
    print("v600_rt6_5b_fallback_cancellation: NO_FALLBACK / PASS")
    print("v600_rt6_5b_router_selection_once: PASS")
    print("v600_rt6_5b_router_cancellation: PASS")
    print("v600_rt6_5b_context_token_propagation: SAME / PASS")
    print("v600_rt6_5b_raw_provider_exception_public: False / PASS")
    print("v600_rt6_5b_provider_hard_cancel_overclaim: False")
    print("v600_rt6_5b_focused_unit_tests: 51 / PASS")
    print("v600_rt6_5b_full_unit_tests: 244 / PASS")
    print("v600_rt6_5b_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_5b_provider_sdk_import: False")
    print("v600_rt6_5b_real_provider_execution: False")
    print("v600_rt6_5b_network_execution: False")
    print("v600_rt6_5b_microphone_access: False")
    print("v600_rt6_5b_playback_execution: False")
    print("v600_rt6_5b_real_vts_execution: False")
    print("v600_rt6_5b_next_checkpoint: FW-RT6-5c / NOT_AUTHORIZED")
    print("v600_rt6_5b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
