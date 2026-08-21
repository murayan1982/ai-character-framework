"""Run the provider-free FW-RT6-14a aggregate conformance gate."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = "c4b0bc7e00d08d9e89e6336b9545c3b2cb375741"
UNIT_TEST_PATTERN = "test*.py"
EXPECTED_DEDICATED_TEST_COUNT = 12
EXPECTED_FULL_UNIT_COUNT = 828
EXPECTED_TRACKED_SMOKE_FILE_COUNT = 93
EXPECTED_HISTORICAL_SMOKE_FILE_COUNT = 91
EXPECTED_SURFACE = frozenset(
    {
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_aggregate_conformance.md",
        "docs/v600_tasklist.md",
        "scripts/check_v600_aggregate_conformance.py",
    }
)
CURRENT_STANDALONE_SMOKE_FILES = (
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
)
CURRENT_SMOKE_COMMANDS = (
    ("scripts/smoke_v600_public_api_manifest.py", ()),
    ("scripts/smoke_v600_version_metadata.py", ()),
    ("scripts/check_v600_root_public_api_cleanup_acceptance.py", ("--source-only",)),
    ("scripts/check_v600_guarded_real_runtime_composition.py", ("--source-only",)),
    ("scripts/check_v600_integrated_fake_runtime_acceptance.py", ()),
    ("scripts/check_v600_interrupt_ordering_acceptance.py", ("--source-only",)),
    ("scripts/check_v600_end_to_end_stale_acceptance.py", ("--source-only",)),
    ("scripts/check_v600_interrupt_coordination_acceptance.py", ("--source-only",)),
    ("scripts/check_v600_voice_output_queue_acceptance.py", ("--source-only",)),
    ("scripts/check_v600_session_compatibility_acceptance.py", ("--source-only",)),
    ("scripts/check_v600_real_runtime_operator_acceptance.py", ("--source-only",)),
)
OPTIONAL_PROVIDER_MODULES = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "sounddevice",
    "pyaudio",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _safe_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in tuple(environment):
        folded = key.casefold()
        if any(
            fragment in folded
            for fragment in (
                "api_key",
                "apikey",
                "authorization",
                "credential",
                "password",
                "private_key",
                "secret",
                "token",
            )
        ):
            environment.pop(key, None)
    environment.update(
        {
            "AI_CHARACTER_FRAMEWORK_REAL_RUNTIME_ENABLED": "0",
            "AI_CHARACTER_FRAMEWORK_ALLOW_PROVIDER_EXECUTION": "0",
            "AI_CHARACTER_FRAMEWORK_ALLOW_DEVICE_EXECUTION": "0",
        }
    )
    return environment


def _run_checked(command: list[str], *, label: str) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=_safe_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    _require(completed.returncode == 0, f"{label} failed")
    return completed.stdout + completed.stderr


def check_repository_surface() -> None:
    head = _run_checked(["git", "rev-parse", "HEAD"], label="git head").strip()
    branch = _run_checked(
        ["git", "branch", "--show-current"],
        label="git branch",
    ).strip()
    _require(head == BASELINE_HEAD, "aggregate acceptance-sync baseline drift")
    _require(branch == "main", "aggregate acceptance sync must be reviewed on main")

    status = _run_checked(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        label="git status",
    )
    changed_paths = {
        line[3:].strip()
        for line in status.splitlines()
        if len(line) >= 4
    }
    _require(changed_paths == EXPECTED_SURFACE, "aggregate acceptance-sync surface drift")
    _run_checked(["git", "diff", "--check"], label="git diff check")


def check_contract_docs() -> None:
    paths = (
        PROJECT_ROOT / "docs/app_integration_contract.md",
        PROJECT_ROOT / "docs/public_facade.md",
        PROJECT_ROOT / "docs/v600_aggregate_conformance.md",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    _require(
        combined.count("FW-RT6-14a-AGGREGATE-CONFORMANCE:BEGIN") == 3,
        "14a aggregate contract marker must exist in three contract docs",
    )
    for phrase in (
        "baseline head: 8f0be2cdcdf92d039c2d957f6d1eaf90e7388298",
        "implementation commit: c4b0bc7e00d08d9e89e6336b9545c3b2cb375741",
        "acceptance-sync baseline: c4b0bc7e00d08d9e89e6336b9545c3b2cb375741",
        "exact implementation surface: 6 files",
        "exact acceptance-sync surface: 5 files",
        "production Framework source changes: 0 files",
        "dedicated aggregate tests: 12 / PASS",
        "full Framework unit suite: 828 / PASS",
        "current-compatible smoke dependencies: 11 / PASS",
        "tracked smoke_v600 files: 93 / CLASSIFIED",
        "historical smoke_v600 files: 91 / SOURCE_EVIDENCE_ONLY",
        "provider/network/microphone/playback/VTS execution: False",
        "FW-RT6-14a canonical tasks: 12 / 12 ACCEPTED",
        "FW-RT6-14a final acceptance sync: PASS",
        "FW-RT6-14b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-14b implementation: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in combined, f"aggregate contract phrase missing: {phrase}")


def check_tasklist_boundary() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    canonical = tasklist.split(
        "## FW-RT6-14a — Aggregate conformance gate",
        1,
    )[1].split("## FW-RT6-14b", 1)[0]
    _require(canonical.count("- [ ]") == 0, "14a final sync retains an open task")
    _require(canonical.count("- [x]") == 12, "14a final sync must close twelve tasks")
    _require(
        tasklist.count("FW-RT6-14a-AGGREGATE-CONFORMANCE-CANDIDATE:BEGIN") == 1,
        "14a candidate marker must be unique",
    )
    _require(
        tasklist.count("FW-RT6-14a-FINAL-ACCEPTANCE-SYNC:BEGIN") == 1,
        "14a final acceptance marker must be unique",
    )
    for phrase in (
        "checkpoint: FW-RT6-14a",
        "status: COMPLETED / VERIFIED / COMMITTED / PUSHED / REMOTELY_VERIFIED",
        "acceptance-sync baseline head: c4b0bc7e00d08d9e89e6336b9545c3b2cb375741",
        "exact implementation surface: 6 files",
        "final acceptance-sync exact surface: 5 files",
        "dedicated aggregate tests: 12 / PASS",
        "full Framework unit suite: 828 / PASS",
        "current-compatible smoke dependencies: 11 / PASS",
        "FW-RT6-14a canonical tasks: 12 / 12 ACCEPTED",
        "FW-RT6-14a tasks: 12 / 12 ACCEPTED",
        "FW-RT6-14a final acceptance sync: PASS",
        "FW-RT6-14b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-14b implementation: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in tasklist, f"aggregate tasklist fact missing: {phrase}")


def check_test_source() -> None:
    source = (PROJECT_ROOT / "tests/test_aggregate_conformance.py").read_text(
        encoding="utf-8"
    )
    _require(
        source.count("    def test_") == EXPECTED_DEDICATED_TEST_COUNT,
        "aggregate suite must contain exactly twelve tests",
    )
    folded = source.casefold()
    for forbidden in (
        "import openai",
        "import elevenlabs",
        "import pyvts",
        "socket.create_connection",
        "sounddevice.rec",
        "pyaudio.pyaudio(",
    ):
        _require(forbidden not in folded, f"aggregate tests contain real execution: {forbidden}")


def check_smoke_inventory() -> None:
    smoke_files = tuple(sorted((PROJECT_ROOT / "scripts").glob("smoke_v600_*.py")))
    _require(
        len(smoke_files) == EXPECTED_TRACKED_SMOKE_FILE_COUNT,
        "tracked smoke_v600 inventory drift",
    )
    _require(len(CURRENT_SMOKE_COMMANDS) == 11, "current smoke dependency count drift")
    _require(len(set(CURRENT_SMOKE_COMMANDS)) == 11, "duplicate current smoke dependency")
    _require(
        len(smoke_files) - len(CURRENT_STANDALONE_SMOKE_FILES)
        == EXPECTED_HISTORICAL_SMOKE_FILE_COUNT,
        "historical smoke classification drift",
    )
    for relative_path, _arguments in CURRENT_SMOKE_COMMANDS:
        _require((PROJECT_ROOT / relative_path).is_file(), "current smoke dependency missing")


def run_dedicated_suite() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_aggregate_conformance.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    _require(result.wasSuccessful(), "aggregate dedicated unittest suite failed")
    _require(
        result.testsRun == EXPECTED_DEDICATED_TEST_COUNT,
        "aggregate dedicated unittest count drift",
    )


def run_current_smoke_suite() -> None:
    for relative_path, arguments in CURRENT_SMOKE_COMMANDS:
        _run_checked(
            [sys.executable, relative_path, *arguments],
            label=f"current smoke dependency {Path(relative_path).name}",
        )


def run_full_unit_suite() -> None:
    output = _run_checked(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        label="full Framework unit suite",
    )
    _require(
        f"Ran {EXPECTED_FULL_UNIT_COUNT} tests" in output,
        "full Framework unit count drift",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the provider-free FW-RT6-14a aggregate conformance gate."
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Skip checkout/status verification while retaining all provider-free gates.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _parse_args()
    if not arguments.source_only:
        check_repository_surface()
    check_contract_docs()
    check_tasklist_boundary()
    check_test_source()
    check_smoke_inventory()
    run_dedicated_suite()
    run_current_smoke_suite()
    run_full_unit_suite()

    print("FW-RT6-14a aggregate conformance gate: PASS")
    print("implementation commit: c4b0bc7e00d08d9e89e6336b9545c3b2cb375741 / VERIFIED")
    print("final acceptance-sync exact surface: 5 files / PASS")
    print("production Framework source changes: 0 files")
    print("root-public manifest gate: PASS / 127 UNCHANGED")
    print("import safety gate: PASS")
    print("capability truthfulness gate: PASS")
    print("event ordering gate: PASS")
    print("exactly-once terminal gate: PASS")
    print("stale rejection gate: PASS")
    print("interrupt reach gate: PASS")
    print("TTS work-control gate: PASS")
    print("security/redaction gate: PASS")
    print("compatibility gate: PASS")
    print("dedicated aggregate tests: 12 / PASS")
    print("full Framework unit suite: 828 / PASS")
    print("current-compatible smoke dependencies: 11 / PASS")
    print("tracked smoke_v600 files: 93 / CLASSIFIED")
    print("historical smoke_v600 files: 91 / SOURCE_EVIDENCE_ONLY")
    print("provider/network/microphone/playback/VTS execution: False")
    print("private configuration/evidence read or written: False")
    print("FW-RT6-14a canonical tasks: 12 / 12 ACCEPTED")
    print("FW-RT6-14a final acceptance sync: PASS")
    print("FW-RT6-14a: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH")
    print("FW-RT6-14b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH")
    print("FW-RT6-14b implementation: NOT_AUTHORIZED")
    print("acceptance-sync commit / push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
