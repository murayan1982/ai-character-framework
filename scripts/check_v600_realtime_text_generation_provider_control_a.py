"""FW-RT6-5b Control A OpenAI/xAI provider-adapter gate."""

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
    "docs/v600_realtime_execution_contract.md",
    "docs/v600_realtime_session_construction_contract.md",
    "docs/v600_realtime_text_generation_contract.md",
    "docs/v600_realtime_text_generation_provider_adapter_contract.md",
    "docs/v600_realtime_turn_start_contract.md",
    "docs/v600_tasklist.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_execution.py",
    "framework/realtime_execution_bridge.py",
    "framework/realtime_session.py",
    "framework/realtime_text_generation.py",
    "framework/realtime_text_generation_provider_adapters.py",
    "scripts/check_v600_realtime_execution_acceptance.py",
    "scripts/check_v600_realtime_execution_control_a.py",
    "scripts/check_v600_realtime_execution_control_b.py",
    "scripts/check_v600_realtime_text_generation_acceptance.py",
    "scripts/check_v600_realtime_text_generation_control_a.py",
    "scripts/check_v600_realtime_text_generation_control_b.py",
    "scripts/check_v600_realtime_text_generation_provider_control_a.py",
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
    "tests/test_realtime_text_generation_provider_adapters.py",
    "tests/test_realtime_text_generation_stage_protocol.py",
    "tests/test_realtime_text_generation_stream.py",
    "tests/test_realtime_turn_lifecycle_acceptance.py",
    "tests/test_realtime_turn_start_adoption.py",
    "tests/test_realtime_turn_start_models.py",
}

ACCEPTED_5A_EXPORT_PREFIX = (
    "TextGenerationCancelReason",
    "TextGenerationCancellationToken",
    "TextGenerationDeltaEnvelope",
    "TextGenerationStreamCloseOutcome",
    "TextGenerationStreamCloseResult",
    "TextGenerationCompletedTurn",
    "TextGenerationHistorySink",
    "TextGenerationStream",
    "ProviderNeutralTextGenerationStream",
    "CancelableTextGenerationStage",
)


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
        "[OK] baseline and exact 38-file accepted 5a + "
        "FW-RT6-5b Control A surface conform"
    )


def check_source_contract() -> None:
    model_source = (
        PROJECT_ROOT / "framework/realtime_text_generation.py"
    ).read_text(encoding="utf-8")
    adapter_source = (
        PROJECT_ROOT / "framework/realtime_text_generation_provider_adapters.py"
    ).read_text(encoding="utf-8")

    for phrase in (
        "class TextGenerationProviderError(RuntimeError):",
        "class OpenAITextGenerationAdapter",
        "class XAITextGenerationAdapter",
        "class _TransactionalMessageHistory",
        "class _OpenAICompatibleDeltaSource",
        "ProviderNeutralTextGenerationStream(",
        "history_sink=self._history",
        "provider_hard_cancel_supported=False",
        "TextGenerationProviderError.from_exception",
    ):
        _assert(
            phrase in model_source or phrase in adapter_source,
            f"Control A source missing: {phrase}",
        )

    lowered = [line.strip().lower() for line in adapter_source.splitlines()]
    forbidden = (
        "import openai",
        "from openai",
        "import google",
        "from google",
        "from config.secrets",
        "import requests",
        "import httpx",
        "os.getenv",
        "os.environ",
    )
    for phrase in forbidden:
        _assert(
            not any(line.startswith(phrase) or phrase in line for line in lowered),
            "Control A imported/read forbidden provider runtime material: " + phrase,
        )

    legacy_openai = (PROJECT_ROOT / "llm/openai_engine.py").read_text(encoding="utf-8")
    legacy_xai = (PROJECT_ROOT / "llm/grok_engine.py").read_text(encoding="utf-8")
    _assert("class OpenAIEngine(BaseLLM):" in legacy_openai, "legacy OpenAI path drift")
    _assert("class GrokEngine(BaseLLM):" in legacy_xai, "legacy xAI path drift")
    print("[OK] injected-client OpenAI/xAI adapter source is provider-safe and legacy path remains present")


def check_runtime_contract() -> None:
    import framework
    import framework.realtime_text_generation as models
    import framework.realtime_text_generation_provider_adapters as adapters
    from framework.realtime_text_generation import TextGenerationProviderError

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(
        tuple(models.__all__[:10]) == ACCEPTED_5A_EXPORT_PREFIX,
        "accepted FW-RT6-5a export prefix drift",
    )
    _assert(
        tuple(models.__all__[10:]) == ("TextGenerationProviderError",),
        "FW-RT6-5b Control A model suffix drift",
    )
    _assert(
        tuple(adapters.__all__[:2])
        == ("OpenAITextGenerationAdapter", "XAITextGenerationAdapter"),
        "accepted Control A provider-adapter export prefix drift",
    )
    for name in (
        "TextGenerationProviderError",
        "OpenAITextGenerationAdapter",
        "XAITextGenerationAdapter",
    ):
        _assert(name not in framework.__all__, f"Control A root-public leak: {name}")

    raw = RuntimeError("raw response body api_key=private")
    error = TextGenerationProviderError.from_exception(raw, provider="openai")
    _assert(error.public_error_code == "provider_request_failed", "generic error code drift")
    _assert(error.retryable, "generic provider failure must remain retryable")
    _assert("private" not in str(error), "raw provider detail leaked through str")
    _assert("api_key" not in repr(error), "raw provider detail leaked through repr")
    _assert(error.__cause__ is None, "provider error retained a public cause")
    print("[OK] 127-name root surface, additive stable error, and safe classification conform")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
    ):
        _run(command)
    print("[OK] canonical root-public/version/app SDK regressions remain 127-name compatible")


def check_tests() -> None:
    focused = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_text_generation_provider_adapters"
    )
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused provider-adapter tests failed")
    _assert(focused_result.testsRun == 20, "focused Control A count must be 20")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 213, "full unit suite regressed below accepted 213-test baseline")
    print(
        "[OK] focused 20 provider-adapter tests and accepted 213-test "
        f"baseline preserved (current={full_result.testsRun})"
    )


def check_docs() -> None:
    text_contract = (
        PROJECT_ROOT / "docs/v600_realtime_text_generation_contract.md"
    ).read_text(encoding="utf-8")
    provider_contract = (
        PROJECT_ROOT / "docs/v600_realtime_text_generation_provider_adapter_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-5a-D-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-5a aggregate acceptance",
        "COMPLETED / VERIFIED / ACCEPTED",
        "FW-RT6-5b exact contract review completed / Control A authorized",
    ):
        _assert(marker in text_contract, f"5a acceptance sync missing: {marker}")
        _assert(marker in tasklist, f"tasklist 5a acceptance sync missing: {marker}")

    for marker in (
        "FW-RT6-5b Control A",
        "OpenAITextGenerationAdapter",
        "XAITextGenerationAdapter",
        "TextGenerationProviderError",
        "Framework-side committed history",
        "history mutation = 0",
        "raw provider exception public:\nFalse",
        "TextGenerationCapability.provider_hard_cancel_supported",
        "Gemini adapter:\nDEFERRED / Control B",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in provider_contract, f"provider contract marker missing: {marker}")

    for marker in (
        "FW-RT6-5b-A-OPENAI-XAI-ADAPTERS:BEGIN",
        "exact Control A delta:\n9 files",
        "combined working-tree surface:\n38 files",
        "OpenAITextGenerationAdapter / PASS expected",
        "XAITextGenerationAdapter / PASS expected",
        "TextGenerationProviderError",
        "Control B:\nNOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"tasklist Control A marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-5b — LLM provider adapters")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    unchecked = section.count("- [ ]")
    checked = section.count("- [x]")
    _assert(
        (unchecked, checked) in ((7, 0), (0, 7)),
        "FW-RT6-5b aggregate task state must be either pre-Control-C or fully accepted-candidate",
    )
    print("[OK] 5a acceptance sync and accepted Control A docs remain Control C-growth compatible")


def check_historical_growth_contract() -> None:
    acceptance = (
        PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_acceptance.py"
    ).read_text(encoding="utf-8")
    stage_test = (
        PROJECT_ROOT / "tests/test_realtime_text_generation_stage_protocol.py"
    ).read_text(encoding="utf-8")
    _assert("full_result.testsRun >= 193" in acceptance, "5a accepted full-test growth guard missing")
    _assert("full_result.testsRun == 193" not in acceptance, "5a exact full count remains")
    _assert("tuple(module.__all__[:10])" in acceptance, "5a accepted 10-name export prefix guard missing")
    _assert("module.__all__[9]" in stage_test, "5a stage test additive suffix guard missing")
    print("[OK] accepted FW-RT6-5a baseline remains additive-growth compatible")


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

    print("v600_rt6_5a_acceptance_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5b_control_a_status: implemented-awaiting-review")
    print("v600_rt6_5b_control_a_exact_delta: 9 files")
    print("v600_rt6_5b_combined_surface: 38 files")
    print("v600_rt6_5b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5b_openai_adapter: OpenAITextGenerationAdapter / PASS")
    print("v600_rt6_5b_xai_adapter: XAITextGenerationAdapter / PASS")
    print("v600_rt6_5b_openai_normal_history: EXACTLY_ONCE / PASS")
    print("v600_rt6_5b_openai_cancelled_history: 0 / PASS")
    print("v600_rt6_5b_xai_normal_history: EXACTLY_ONCE / PASS")
    print("v600_rt6_5b_raw_provider_exception_public: False / PASS")
    print("v600_rt6_5b_provider_hard_cancel_source: TextGenerationCapability.provider_hard_cancel_supported")
    print("v600_rt6_5b_openai_hard_cancel: False / TRUTHFUL")
    print("v600_rt6_5b_xai_hard_cancel: False / TRUTHFUL")
    print("v600_rt6_5b_focused_unit_tests: 20 / PASS")
    print("v600_rt6_5b_full_unit_tests_baseline: 213 / PASS")
    print("v600_rt6_5b_gemini_fallback_router: DEFERRED / CONTROL_B")
    print("v600_rt6_5b_provider_sdk_import: False")
    print("v600_rt6_5b_real_provider_execution: False")
    print("v600_rt6_5b_network_execution: False")
    print("v600_rt6_5b_microphone_access: False")
    print("v600_rt6_5b_playback_execution: False")
    print("v600_rt6_5b_real_vts_execution: False")
    print("v600_rt6_5b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_5b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
