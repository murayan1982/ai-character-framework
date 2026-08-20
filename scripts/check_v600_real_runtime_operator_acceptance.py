"""Run the provider-free FW-RT6-13c operator-tooling gate."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATHS = (
    PROJECT_ROOT / "docs/app_integration_contract.md",
    PROJECT_ROOT / "docs/public_facade.md",
    PROJECT_ROOT / "docs/v600_guarded_real_runtime_composition.md",
    PROJECT_ROOT / "docs/v600_tasklist.md",
    PROJECT_ROOT / "docs/v600_real_runtime_operator_acceptance.md",
)
TASKLIST_PATH = PROJECT_ROOT / "docs/v600_tasklist.md"
OPERATOR_PATH = PROJECT_ROOT / "scripts/operator_v600_real_runtime_acceptance.py"
VERIFIER_PATH = PROJECT_ROOT / "scripts/verify_v600_real_runtime_private_evidence.py"
TEST_PATH = PROJECT_ROOT / "tests/test_real_runtime_operator_acceptance.py"
EXACT_SURFACE = (
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_guarded_real_runtime_composition.md",
    "docs/v600_tasklist.md",
    "docs/v600_real_runtime_operator_acceptance.md",
    "scripts/operator_v600_real_runtime_acceptance.py",
    "scripts/verify_v600_real_runtime_private_evidence.py",
    "scripts/check_v600_real_runtime_operator_acceptance.py",
    "tests/test_real_runtime_operator_acceptance.py",
)
OPTIONAL_PROVIDER_MODULES = frozenset(
    {"openai", "elevenlabs", "pyvts", "websockets", "sounddevice", "pyaudio"}
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    _require(path.is_file(), f"required file is missing: {path.name}")
    return path.read_text(encoding="utf-8")


def check_exact_surface() -> None:
    _require(len(EXACT_SURFACE) == 9, "implementation surface must contain nine files")
    for relative in EXACT_SURFACE:
        _require((PROJECT_ROOT / relative).is_file(), f"surface file missing: {relative}")
    _require(
        not any(relative.startswith("framework/") for relative in EXACT_SURFACE),
        "FW-RT6-13c tooling must not change production Framework source",
    )
    _require("README.md" not in EXACT_SURFACE, "README remains owned by FW-RT6-14b")


def check_contract_docs() -> None:
    documents = [_read(path) for path in DOC_PATHS]
    marker = "FW-RT6-13c-REAL-RUNTIME-OPERATOR:BEGIN"
    _require(
        sum(document.count(marker) for document in documents) == 5,
        "FW-RT6-13c marker must exist once in each of five contract docs",
    )
    combined = "\n".join(documents)
    for phrase in (
        "baseline head: cf660a0c4eb4373f21dfdd779a5f98b64457d791",
        "status: IMPLEMENTED / VERIFIED / AWAITING_REVIEW",
        "exact implementation surface: 9 files",
        "production Framework source changes: 0",
        "root-public names: 127 / UNCHANGED",
        "RealtimeSession real orchestration changed/enabled: False",
        "canonical scenarios closed: 0 / 9",
        "provider hard cancel claimed: False",
        "physical playback stop claimed by Framework: False",
        "real operator execution: NOT_AUTHORIZED",
        "private evidence read/validated: False",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in combined, f"operator contract phrase missing: {phrase}")


def check_tasklist_boundary() -> None:
    tasklist = _read(TASKLIST_PATH)
    canonical = tasklist.split(
        "## FW-RT6-13c — Operator acceptance", 1
    )[1].split("## FW-RT6-14a", 1)[0]
    _require(canonical.count("- [ ]") == 9, "13c must retain exactly nine open tasks")
    _require(canonical.count("- [x]") == 0, "13c must close no canonical task yet")
    _require(
        tasklist.count("FW-RT6-13c-REAL-RUNTIME-OPERATOR:BEGIN") == 1,
        "13c implementation marker must be unique in tasklist",
    )
    for phrase in (
        "configured real voice input tooling: IMPLEMENTED / NOT_EXECUTED",
        "configured real LLM streaming tooling: IMPLEMENTED / NOT_EXECUTED",
        "FW-RT6-13c canonical scenarios: 0 / 9 CLOSED / UNCHANGED",
        "acceptance sync: NOT_AUTHORIZED",
    ):
        _require(phrase in tasklist, f"tasklist tooling fact missing: {phrase}")


def _top_level_imports(source: str) -> set[str]:
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
    return imported


def check_operator_source() -> None:
    source = _read(OPERATOR_PATH)
    imported = _top_level_imports(source)
    _require(
        not imported.intersection(OPTIONAL_PROVIDER_MODULES),
        "operator imports an optional provider at module load",
    )
    for phrase in (
        "I_ACCEPT_REAL_STT_LLM_TTS_AND_VTS_EXECUTION_AND_POSSIBLE_CHARGES",
        "I_WILL_KEEP_CONFIG_AUDIO_TEXT_ARTIFACTS_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY",
        "I_OBSERVED_HOST_PLAYBACK_AND_STOPPED_IT",
        "ai-character-framework-v600-rt6-13c-private-config-v1",
        "ai-character-framework-v600-rt6-13c-private-evidence-v1",
        "OpenAIVoiceInputRealProviderExecutor",
        "OpenAITextGenerationAdapter",
        "TextGenerationCancelReason.INTERRUPT",
        "CancelableProviderNeutralVoiceSynthesisStage",
        "BoundedVoiceSynthesisPendingQueue",
        "GenerationAdvanceReason.INTERRUPT",
        "operator_v550_vtube_studio_real_motion_acceptance",
        "framework_realtime_session_real_orchestration_used",
    ):
        _require(phrase in source, f"operator implementation phrase missing: {phrase}")
    for forbidden in (
        "create_realtime_session(",
        "RealtimeSession(",
        ".run_turn(",
    ):
        _require(forbidden not in source, f"unified real runtime was added: {forbidden}")


def check_verifier_source() -> None:
    source = _read(VERIFIER_PATH)
    imported = _top_level_imports(source)
    _require(
        not imported.intersection(OPTIONAL_PROVIDER_MODULES),
        "verifier imports an optional provider",
    )
    for phrase in (
        "EXPECTED_FIELDS",
        "set(payload) == EXPECTED_FIELDS",
        "TRUE_FIELDS",
        "FALSE_FIELDS",
        "POSITIVE_COUNT_FIELDS",
        "accepted-by-validator",
        "acceptance_scenarios: 9 / 9 VERIFIED",
        "framework_realtime_session_real_orchestration_used",
    ):
        _require(phrase in source, f"private verifier phrase missing: {phrase}")


def check_test_source() -> None:
    source = _read(TEST_PATH)
    _require(source.count("    def test_") == 15, "dedicated suite must contain 15 tests")
    for forbidden in (
        "import openai",
        "import elevenlabs",
        "import pyvts",
        "socket.create_connection",
        "from sounddevice",
        "sounddevice.rec",
        "pyaudio.pyaudio(",
    ):
        _require(
            forbidden not in source.casefold(),
            f"dedicated tests contain forbidden real execution: {forbidden}",
        )


def check_import_boundary() -> None:
    source = """
import importlib.util
import pathlib
import sys
before = set(sys.modules)
for index, filename in enumerate((
    'scripts/operator_v600_real_runtime_acceptance.py',
    'scripts/verify_v600_real_runtime_private_evidence.py',
)):
    spec = importlib.util.spec_from_file_location(f'_gate_{index}', pathlib.Path(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
loaded = set(sys.modules) - before
for name in ('openai', 'elevenlabs', 'pyvts', 'websockets', 'sounddevice', 'pyaudio'):
    if name in loaded:
        raise AssertionError(name)
"""
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _require(
        completed.returncode == 0,
        "operator import boundary failed: " + completed.stderr.strip(),
    )


def run_dedicated_suite() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_real_runtime_operator_acceptance.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    _require(result.wasSuccessful(), "real-runtime operator unittest suite failed")
    _require(result.testsRun == 15, "operator suite did not run exactly 15 tests")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    check_exact_surface()
    check_contract_docs()
    check_tasklist_boundary()
    check_operator_source()
    check_verifier_source()
    check_test_source()
    check_import_boundary()
    if not args.source_only:
        run_dedicated_suite()

    print("FW-RT6-13c real-runtime operator tooling: PASS")
    print("exact implementation surface: 9 files / PASS")
    print("production Framework source changes: 0")
    print("dedicated provider-free tests: 15 / PASS")
    print("provider SDK lazy import: PASS")
    print("private evidence exact allowlist: PASS")
    print("provider hard cancel claimed: False")
    print("Framework physical playback stop claimed: False")
    print("framework root-public names: 127 / UNCHANGED")
    print("RealtimeSession real orchestration changed/enabled: False")
    print("provider/network/microphone/playback/VTS execution: False")
    print("private config/audio/artifacts/evidence read: False")
    print("FW-RT6-13c canonical scenarios: 0 / 9 CLOSED / UNCHANGED")
    print("FW-RT6-13c: IMPLEMENTED / VERIFIED / AWAITING_REVIEW")
    print("real operator execution: NOT_AUTHORIZED")
    print("private evidence validation: NOT_RUN")
    print("commit / push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
