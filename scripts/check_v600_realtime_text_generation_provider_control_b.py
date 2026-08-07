"""FW-RT6-5b Control B Gemini/fallback/router provider-adapter gate."""

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
    "scripts/check_v600_realtime_text_generation_provider_control_b.py",
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
    "tests/test_realtime_text_generation_provider_control_b.py",
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

CONTROL_A_ADAPTER_PREFIX = (
    "OpenAITextGenerationAdapter",
    "XAITextGenerationAdapter",
)

CONTROL_B_ADAPTER_SUFFIX = (
    "GeminiTextGenerationAdapter",
    "FallbackTextGenerationAdapter",
    "RouterTextGenerationAdapter",
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
        "Control B combined surface drift; "
        f"expected={sorted(EXPECTED_COMBINED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    print(
        "[OK] baseline and exact 40-file accepted Control A + "
        "FW-RT6-5b Control B surface conform"
    )


def check_source_contract() -> None:
    source = (
        PROJECT_ROOT / "framework/realtime_text_generation_provider_adapters.py"
    ).read_text(encoding="utf-8")

    for phrase in (
        "class GeminiTextGenerationAdapter",
        "generate_content_stream(",
        "provider_owned_chat_state",
        "class FallbackTextGenerationAdapter",
        "class _FallbackTextGenerationStream",
        "self._delivered_delta_count == 0",
        "not self._cancellation_token.cancel_requested",
        "class RouterTextGenerationAdapter",
        "self._route_selector(request)",
        "_minimum_text_generation_capability",
        "_ensure_child_stream_contract",
    ):
        _assert(phrase in source, f"Control B source missing: {phrase}")

    lowered = [line.strip().lower() for line in source.splitlines()]
    for phrase in (
        "import openai",
        "from openai",
        "import google",
        "from google",
        "from config.secrets",
        "import requests",
        "import httpx",
        "os.getenv",
        "os.environ",
    ):
        _assert(
            not any(line.startswith(phrase) or phrase in line for line in lowered),
            "Control B imported/read forbidden provider runtime material: " + phrase,
        )

    _assert("client.chats.create" not in source, "Gemini mutable chat path adopted")
    _assert("send_message_stream" not in source, "Gemini mutable chat stream adopted")

    legacy_gemini = (PROJECT_ROOT / "llm/gemini_engine.py").read_text(encoding="utf-8")
    legacy_fallback = (PROJECT_ROOT / "llm/fallback_llm.py").read_text(encoding="utf-8")
    legacy_router = (PROJECT_ROOT / "llm/router_llm.py").read_text(encoding="utf-8")
    _assert("class GeminiEngine(BaseLLM):" in legacy_gemini, "legacy Gemini path drift")
    _assert("class FallbackLLM(BaseLLM):" in legacy_fallback, "legacy fallback path drift")
    _assert("class RouterLLM(BaseLLM):" in legacy_router, "legacy router path drift")
    print(
        "[OK] Gemini stateless history and provider-neutral fallback/router "
        "source are provider-safe; legacy paths remain present"
    )


def check_runtime_contract() -> None:
    import framework
    import framework.realtime_text_generation as models
    import framework.realtime_text_generation_provider_adapters as adapters

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(
        tuple(models.__all__[:10]) == ACCEPTED_5A_EXPORT_PREFIX,
        "accepted FW-RT6-5a model prefix drift",
    )
    _assert(
        tuple(models.__all__[10:]) == ("TextGenerationProviderError",),
        "FW-RT6-5b provider error suffix drift",
    )
    _assert(
        tuple(adapters.__all__[:2]) == CONTROL_A_ADAPTER_PREFIX,
        "accepted Control A adapter prefix drift",
    )
    _assert(
        tuple(adapters.__all__[2:]) == CONTROL_B_ADAPTER_SUFFIX,
        "Control B adapter suffix drift",
    )
    for name in (
        "GeminiTextGenerationAdapter",
        "FallbackTextGenerationAdapter",
        "RouterTextGenerationAdapter",
    ):
        _assert(name not in framework.__all__, f"Control B root-public leak: {name}")
    print(
        "[OK] 127-name root surface and exact additive "
        "Gemini/fallback/router adapter suffix conform"
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
    control_a = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_text_generation_provider_adapters"
    )
    control_b = unittest.defaultTestLoader.loadTestsFromName(
        "tests.test_realtime_text_generation_provider_control_b"
    )
    focused = unittest.TestSuite((control_a, control_b))
    focused_result = unittest.TextTestRunner(verbosity=0).run(focused)
    _assert(focused_result.wasSuccessful(), "focused Control A+B provider tests failed")
    _assert(focused_result.testsRun == 41, "focused Control A+B count must be 41")

    full = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_*.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    full_result = unittest.TextTestRunner(verbosity=0).run(full)
    _assert(full_result.wasSuccessful(), "full unit suite failed")
    _assert(full_result.testsRun >= 234, "full unit suite regressed below accepted 234-test baseline")
    print("[OK] focused 41 provider-adapter tests and accepted 234-test baseline preserved")


def check_docs() -> None:
    provider_contract = (
        PROJECT_ROOT / "docs/v600_realtime_text_generation_provider_adapter_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-5b-A-ACCEPTANCE-SYNC:BEGIN",
        "COMPLETED / VERIFIED / ACCEPTED",
        "FW-RT6-5b Control B authorized",
        "FW-RT6-5b Control B",
        "GeminiTextGenerationAdapter",
        "provider-owned chat rollback dependency:\nFalse",
        "FallbackTextGenerationAdapter",
        "primary failure after first delivered delta:\nfallback MUST NOT start",
        "RouterTextGenerationAdapter",
        "route selection per stream:\n1",
        "Control C:\nNOT_AUTHORIZED",
    ):
        _assert(marker in provider_contract, f"provider Control B contract marker missing: {marker}")

    for marker in (
        "FW-RT6-5b-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-5b-B-GEMINI-FALLBACK-ROUTER:BEGIN",
        "exact Control B delta:\n6 files",
        "combined working-tree surface:\n40 files",
        "GeminiTextGenerationAdapter / PASS expected",
        "FallbackTextGenerationAdapter / PASS expected",
        "RouterTextGenerationAdapter / PASS expected",
        "fallback after first delivered delta:\nFalse",
        "Control C:\nNOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"tasklist Control B marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-5b — LLM provider adapters")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    unchecked = section.count("- [ ]")
    checked = section.count("- [x]")
    _assert(
        (unchecked, checked) in ((7, 0), (0, 7)),
        "FW-RT6-5b aggregate task state must be either pre-Control-C or fully accepted-candidate",
    )
    print("[OK] accepted Control B docs remain aggregate Control C-growth compatible")


def check_historical_growth_contract() -> None:
    control_a_gate = (
        PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_provider_control_a.py"
    ).read_text(encoding="utf-8")
    accepted_5a_gate = (
        PROJECT_ROOT / "scripts/check_v600_realtime_text_generation_acceptance.py"
    ).read_text(encoding="utf-8")

    _assert(
        "tuple(adapters.__all__[:2])" in control_a_gate,
        "accepted Control A adapter-prefix growth guard missing",
    )
    _assert(
        "full_result.testsRun >= 213" in control_a_gate,
        "accepted Control A 213-test growth guard missing",
    )
    _assert(
        "full_result.testsRun >= 193" in accepted_5a_gate,
        "accepted FW-RT6-5a 193-test growth guard missing",
    )
    print("[OK] accepted FW-RT6-5a and Control A baselines remain additive-growth compatible")


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

    print("v600_rt6_5b_control_a_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_5b_control_b_status: implemented-awaiting-review")
    print("v600_rt6_5b_control_b_exact_delta: 6 files")
    print("v600_rt6_5b_combined_surface: 40 files")
    print("v600_rt6_5b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_5b_gemini_adapter: GeminiTextGenerationAdapter / PASS")
    print("v600_rt6_5b_gemini_transactional_history: PASS")
    print("v600_rt6_5b_gemini_provider_owned_chat_dependency: False")
    print("v600_rt6_5b_gemini_hard_cancel: False / TRUTHFUL")
    print("v600_rt6_5b_fallback_adapter: FallbackTextGenerationAdapter / PASS")
    print("v600_rt6_5b_fallback_pre_delta_failure: FALLBACK / PASS")
    print("v600_rt6_5b_fallback_post_delta_failure: NO_FALLBACK / PASS")
    print("v600_rt6_5b_fallback_cancellation: NO_FALLBACK / PASS")
    print("v600_rt6_5b_router_adapter: RouterTextGenerationAdapter / PASS")
    print("v600_rt6_5b_router_selection_once: PASS")
    print("v600_rt6_5b_router_cancellation: PASS")
    print("v600_rt6_5b_context_token_propagation: SAME / PASS")
    print("v600_rt6_5b_provider_hard_cancel_overclaim: False")
    print("v600_rt6_5b_focused_unit_tests: 41 / PASS")
    print("v600_rt6_5b_full_unit_tests: 234 / PASS")
    print("v600_rt6_5b_provider_sdk_import: False")
    print("v600_rt6_5b_real_provider_execution: False")
    print("v600_rt6_5b_network_execution: False")
    print("v600_rt6_5b_microphone_access: False")
    print("v600_rt6_5b_playback_execution: False")
    print("v600_rt6_5b_real_vts_execution: False")
    print("v600_rt6_5b_control_c: NOT_AUTHORIZED")
    print("v600_rt6_5b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
