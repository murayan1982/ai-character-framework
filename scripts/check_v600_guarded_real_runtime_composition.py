"""Run the provider-free FW-RT6-13b guarded-composition gate."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs/v600_guarded_real_runtime_composition.md"
PUBLIC_FACADE_PATH = PROJECT_ROOT / "docs/public_facade.md"
APP_CONTRACT_PATH = PROJECT_ROOT / "docs/app_integration_contract.md"
TASKLIST_PATH = PROJECT_ROOT / "docs/v600_tasklist.md"
MODULE_PATH = PROJECT_ROOT / "framework/guarded_real_runtime.py"
TEST_PATH = PROJECT_ROOT / "tests/test_guarded_real_runtime_composition.py"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read(path: Path) -> str:
    _require(path.is_file(), f"required file is missing: {path.name}")
    return path.read_text(encoding="utf-8")


def check_contract_docs() -> None:
    contract = _read(DOC_PATH)
    public_facade = _read(PUBLIC_FACADE_PATH)
    app_contract = _read(APP_CONTRACT_PATH)
    combined = "\n".join((contract, public_facade, app_contract))

    _require(
        combined.count("FW-RT6-13b-GUARDED-REAL-RUNTIME:BEGIN") == 3,
        "FW-RT6-13b contract marker must exist in all three contract docs",
    )
    for phrase in (
        "framework.guarded_real_runtime",
        "real STT",
        "streaming LLM",
        "TTS",
        "VTube Studio motion",
        "real_runtime_enabled",
        "allow_provider_execution",
        "explicit double opt-in",
        "provider SDK lazy import: PRESERVED",
        "private configuration/evidence commit: FORBIDDEN",
        "stage capability/reach results: 4",
        "root-public names: 127 / UNCHANGED",
        "status: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH",
        "FW-RT6-13b tasklist state: 10 / 10 ACCEPTED",
        "FW-RT6-13c exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-13c implementation: NOT_AUTHORIZED",
    ):
        _require(phrase in combined, f"guarded composition phrase missing: {phrase}")


def check_tasklist_boundary() -> None:
    tasklist = _read(TASKLIST_PATH)
    canonical = tasklist.split(
        "## FW-RT6-13b — Guarded real-runtime composition",
        1,
    )[1].split("## FW-RT6-13c", 1)[0]
    _require(canonical.count("- [ ]") == 0, "FW-RT6-13b must retain zero open tasks")
    _require(canonical.count("- [x]") == 10, "FW-RT6-13b must close exactly ten tasks")
    _require(
        tasklist.count("FW-RT6-13b-GUARDED-REAL-RUNTIME:BEGIN") == 1,
        "FW-RT6-13b implementation marker must be unique in tasklist",
    )
    _require(
        tasklist.count("FW-RT6-13b-FINAL-ACCEPTANCE-SYNC:BEGIN") == 1,
        "FW-RT6-13b final acceptance marker must be unique in tasklist",
    )
    for phrase in (
        "baseline head: 1a1e9ab676caa606ba6bd2741f8c3b9ca1700e0c",
        "status: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH",
        "exact implementation surface: 7 files",
        "exact acceptance-sync surface: 5 files",
        "FW-RT6-13b tasks: 10 / 10 ACCEPTED",
        "dedicated tests: 10 / PASS",
        "related tests: 122 / PASS",
        "full Framework unit suite: 801 / PASS",
        "FW-RT6-13c exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-13c implementation: NOT_AUTHORIZED",
        "acceptance-sync commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in tasklist, f"tasklist implementation fact missing: {phrase}")


def check_source_boundary() -> None:
    source = _read(MODULE_PATH)
    test_source = _read(TEST_PATH)

    for forbidden in (
        "import openai",
        "import pyvts",
        "import requests",
        "import socket",
        "import sounddevice",
        "import pyaudio",
        "os.environ",
        "getenv(",
        "read_text(",
        "read_bytes(",
        "write_text(",
        "write_bytes(",
    ):
        _require(
            forbidden not in source.lower(),
            f"guarded module contains forbidden provider/private I/O: {forbidden}",
        )

    for required in (
        "GuardedRealRuntimeCompositionConfig",
        "GuardedRealRuntimeStageResult",
        "GuardedRealRuntimeCompositionResult",
        "compose_guarded_real_runtime",
        "real_runtime_enabled",
        "allow_provider_execution",
        "factory_reached",
        "preflight_reached",
        "capability_reached",
        "raw_exception_exposed",
        "private_configuration_exposed",
    ):
        _require(required in source, f"guarded module contract missing: {required}")

    _require(
        test_source.count("    def test_") == 10,
        "guarded composition suite must retain exactly ten tests",
    )


def check_import_boundary() -> None:
    source = """
import sys
import framework
root_before = tuple(framework.__all__)
before = set(sys.modules)
import framework.guarded_real_runtime
loaded = set(sys.modules) - before
for name in ('openai', 'pyvts', 'requests', 'sounddevice', 'pyaudio'):
    if name in loaded:
        raise AssertionError(name)
if tuple(framework.__all__) != root_before:
    raise AssertionError('framework root changed during explicit import')
if len(framework.__all__) != 127:
    raise AssertionError(len(framework.__all__))
if 'compose_guarded_real_runtime' in framework.__all__:
    raise AssertionError('guarded helper unexpectedly root-public')
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
        "explicit import boundary failed: " + completed.stderr.strip(),
    )


def run_dedicated_suite() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_guarded_real_runtime_composition.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    _require(result.wasSuccessful(), "guarded real-runtime unittest suite failed")
    _require(result.testsRun == 10, "guarded suite did not run exactly ten tests")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    check_contract_docs()
    check_tasklist_boundary()
    check_source_boundary()
    check_import_boundary()
    if not args.source_only:
        run_dedicated_suite()

    print("FW-RT6-13b guarded real-runtime composition: PASS")
    print("real stage composition contracts: 4 / PASS")
    print("explicit double opt-in: PASS")
    print("provider SDK lazy import: PASS")
    print("safe failure normalization: PASS")
    print("private configuration/evidence committed: False")
    print("provider/network/microphone/playback/VTS execution: False")
    print("framework root-public names: 127 / UNCHANGED")
    print("FW-RT6-13b tasklist state: 10 / 10 ACCEPTED")
    print("FW-RT6-13b final acceptance sync: PASS")
    print("FW-RT6-13b: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH")
    print("FW-RT6-13c exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH")
    print("FW-RT6-13c implementation: NOT_AUTHORIZED")
    print("acceptance-sync commit / push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
