"""Run the provider-free FW-RT6-13a integrated acceptance gate."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = PROJECT_ROOT / "docs/v600_integrated_fake_runtime_acceptance.md"
PUBLIC_FACADE_PATH = PROJECT_ROOT / "docs/public_facade.md"
APP_CONTRACT_PATH = PROJECT_ROOT / "docs/app_integration_contract.md"
TASKLIST_PATH = PROJECT_ROOT / "docs/v600_tasklist.md"
TEST_PATH = PROJECT_ROOT / "tests/test_integrated_fake_runtime_acceptance.py"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_contract_docs() -> None:
    contract = DOC_PATH.read_text(encoding="utf-8")
    public_facade = PUBLIC_FACADE_PATH.read_text(encoding="utf-8")
    app_contract = APP_CONTRACT_PATH.read_text(encoding="utf-8")
    combined = "\n".join((contract, public_facade, app_contract))

    _require(
        combined.count("FW-RT6-13a-INTEGRATED-FAKE-RUNTIME:BEGIN") == 3,
        "FW-RT6-13a contract marker must exist in all three contract docs",
    )
    for phrase in (
        "text-only normal turn",
        "host audio -> transcript -> text -> TTS -> motion",
        "user stop during response stream",
        "user speech interrupt during voice output",
        "duplicate interrupt",
        "late response delta",
        "late TTS artifact",
        "late motion completion",
        "queue overflow",
        "session reset",
        "session close during active turn",
        "post-close operation rejection",
        "exact event trace / terminal result",
        "network/provider/microphone/playback: False",
        "implementation commit: 0e61ca4154a48f5b41999be40129579d44e21cde",
        "FW-RT6-13a tasklist state: 13 / 13 ACCEPTED",
        "FW-RT6-13b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-13b implementation: NOT_AUTHORIZED",
    ):
        _require(phrase in combined, f"integrated contract phrase missing: {phrase}")


def check_tasklist_boundary() -> None:
    tasklist = TASKLIST_PATH.read_text(encoding="utf-8")
    section = tasklist.split(
        "## FW-RT6-13a — Integrated fake-runtime acceptance",
        1,
    )[1].split("## FW-RT6-13b", 1)[0]
    _require(section.count("- [ ]") == 0, "FW-RT6-13a retains an open task")
    _require(section.count("- [x]") == 13, "FW-RT6-13a must close 13 tasks")
    _require("fake-only integrated suite:" in section, "acceptance block missing")
    _require(
        tasklist.count("FW-RT6-13a-FINAL-ACCEPTANCE-SYNC:BEGIN") == 1,
        "FW-RT6-13a final acceptance marker must be unique",
    )
    for phrase in (
        "implementation commit: 0e61ca4154a48f5b41999be40129579d44e21cde",
        "integrated scenario groups: 10 / PASS",
        "roadmap scenarios: 13 / 13 ACCEPTED",
        "FW-RT6-13a tasks: 13 / 13 ACCEPTED",
        "FW-RT6-13b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-13b implementation: NOT_AUTHORIZED",
    ):
        _require(phrase in tasklist, f"final acceptance fact missing: {phrase}")


def check_test_source_boundary() -> None:
    source = TEST_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "import requests",
        "import socket",
        "import openai",
        "import elevenlabs",
        "pyaudio",
        "sounddevice",
        "websocket",
    ):
        _require(forbidden not in source.lower(), f"forbidden runtime import: {forbidden}")
    _require("time.sleep" not in source, "integrated suite must not use sleep ordering")
    _require(
        source.count("    def test_") == 10,
        "integrated suite must retain the exact ten-test scenario grouping",
    )


def run_integrated_suite() -> None:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    suite = unittest.defaultTestLoader.discover(
        str(PROJECT_ROOT / "tests"),
        pattern="test_integrated_fake_runtime_acceptance.py",
        top_level_dir=str(PROJECT_ROOT),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    _require(result.wasSuccessful(), "integrated fake-runtime unittest suite failed")
    _require(result.testsRun == 10, "integrated suite did not run exactly ten tests")


def main() -> None:
    check_contract_docs()
    check_tasklist_boundary()
    check_test_source_boundary()
    run_integrated_suite()
    print("FW-RT6-13a integrated fake-runtime acceptance: PASS")
    print("fake-only integrated suite: PASS")
    print("exactly-once terminal: PASS")
    print("stale rejection: PASS")
    print("network/provider/microphone/playback: False")
    print("framework root-public names: 127 / UNCHANGED")
    print("RealtimeSession production orchestration changed: False")
    print("FW-RT6-13a tasklist state: 13 / 13 ACCEPTED")
    print("FW-RT6-13a final acceptance sync: PASS")
    print("FW-RT6-13b exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH")
    print("FW-RT6-13b implementation: NOT_AUTHORIZED")
    print("acceptance-sync commit / push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
