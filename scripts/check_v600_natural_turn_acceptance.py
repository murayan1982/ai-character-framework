"""FW-RT6-12c Control C aggregate natural-turn acceptance gate.

The gate is offline-safe. It aggregates the accepted Control A vocabulary and
Control B read-only session snapshot without adding natural-turn execution.
"""

from __future__ import annotations

import argparse
from dataclasses import FrozenInstanceError
import importlib
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "f92d7dcf20e5a5591a406329fd1d0fb96b186b64"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_natural_turn_acceptance.py",
    "scripts/smoke_v600_natural_turn_control_a.py",
    "scripts/smoke_v600_natural_turn_control_b.py",
    "tests/test_natural_turn_control_a.py",
    "tests/test_natural_turn_control_b.py",
}
EXPECTED_EXPORTS = (
    "NATURAL_TURN_API_VERSION",
    "NaturalTurnExtension",
    "NaturalTurnOwnership",
    "NaturalTurnCapability",
    "NaturalTurnCapabilitySet",
    "default_natural_turn_capability_set",
)
EXPECTED_EXTENSIONS = (
    "microphone_listening_while_speaking",
    "vad_based_automatic_detection",
    "wake_word",
    "background_input_monitoring",
    "automatic_next_turn_capture",
    "echo_cancellation",
    "noise_suppression",
)
EXPECTED_ROADMAP_LINES = (
    "microphone listening while speaking",
    "VAD-based automatic detection",
    "wake word",
    "background input monitoring",
    "automatic next-turn capture",
    "echo cancellation",
    "noise suppression",
)
ACCEPTED_GATES = (
    "scripts/check_v600_session_compatibility_acceptance.py",
    "scripts/check_v600_root_public_api_cleanup_acceptance.py",
    "scripts/check_v600_migration_examples_acceptance.py",
    "scripts/check_v600_public_audio_chunk_streaming_acceptance.py",
    "scripts/check_v600_backpressure_acceptance.py",
)
FORBIDDEN_RUNTIME_MODULES = {
    "openai",
    "elevenlabs",
    "pyvts",
    "pyaudio",
    "sounddevice",
    "websocket",
    "websockets",
    "requests",
    "httpx",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(
    command: list[str],
    *,
    capture: bool = True,
    environment: dict[str, str] | None = None,
) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=capture,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (completed.stdout or "")
        + (completed.stderr or ""),
    )
    return completed.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def _bounded_section(source: str, begin: str, end: str) -> str:
    _require(source.count(begin) == 1, f"section begin marker drift: {begin}")
    _require(source.count(end) == 1, f"section end marker drift: {end}")
    return source.split(begin, 1)[1].split(end, 1)[0]


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-12c Control C surface conform")


def check_accepted_history_and_aggregate_state() -> None:
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-12c-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-12c-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-12c-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-12c-B-ACCEPTANCE-SYNC:END",
        "FW-RT6-12c-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-12c-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")
    for marker in (
        "FW-RT6-12c-A-PUBLIC-NATURAL-TURN:BEGIN",
        "FW-RT6-12c-A-PUBLIC-NATURAL-TURN:END",
        "FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:BEGIN",
        "FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:END",
        "FW-RT6-12c-C-NATURAL-TURN-ACCEPTANCE:BEGIN",
        "FW-RT6-12c-C-NATURAL-TURN-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public facade marker drift: {marker}")

    aggregate = _bounded_section(
        tasklist,
        "FW-RT6-12c-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-12c-C-AGGREGATE-ACCEPTANCE:END",
    )
    for phrase in (
        "baseline head: f92d7dcf20e5a5591a406329fd1d0fb96b186b64",
        "Control A implementation and acceptance: b556712bb20465cf712be449b7c956f784b22044",
        "Control B implementation and acceptance: f92d7dcf20e5a5591a406329fd1d0fb96b186b64",
        "Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
        "Control C: IMPLEMENTED / AWAITING_REVIEW",
        "exact Control C surface: 7 files",
        "Control A/B gate/test semantic sync: 4 files / CONTROL_C AGGREGATE STATE ONLY",
        "accepted aggregate contracts: 2 / 2",
        "Control A vocabulary contract: ACCEPTED",
        "Control B RealtimeSession read-only snapshot contract: ACCEPTED",
        "FW-RT6-12c roadmap items closed: 0 / 7 / UNCHANGED",
        "final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-13a: NOT_AUTHORIZED",
        "Control C commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in aggregate, f"aggregate acceptance fact missing: {phrase}")

    primary = tasklist.split(
        "## FW-RT6-12c — Experimental natural-turn extensions", 1
    )[1].split("## FW-RT6-13a", 1)[0]
    _require(primary.count("- [ ]") == 0, "Control C added an open 12c checkbox")
    _require(primary.count("- [x]") == 0, "Control C closed a 12c roadmap item")
    _require(
        "各項目は別roadmap/exact contractとする。" in primary,
        "independent roadmap boundary missing",
    )
    for line in EXPECTED_ROADMAP_LINES:
        _require(primary.count(line) == 1, f"roadmap line drift: {line}")
    print("[OK] accepted Control A/B history and aggregate state conform")
    print("[OK] seven independent roadmap items remain 0 / 7 closed")


def check_gate_test_semantic_sync() -> None:
    sources = {
        "Control A gate": PROJECT_ROOT / "scripts/smoke_v600_natural_turn_control_a.py",
        "Control B gate": PROJECT_ROOT / "scripts/smoke_v600_natural_turn_control_b.py",
        "Control A tests": PROJECT_ROOT / "tests/test_natural_turn_control_a.py",
        "Control B tests": PROJECT_ROOT / "tests/test_natural_turn_control_b.py",
    }
    _require(
        sources["Control A tests"].read_text(encoding="utf-8").count("    def test_")
        == 16,
        "Control A test count drift",
    )
    _require(
        sources["Control B tests"].read_text(encoding="utf-8").count("    def test_")
        == 12,
        "Control B test count drift",
    )
    for label, path in sources.items():
        source = path.read_text(encoding="utf-8")
        _require(
            "check_v600_natural_turn_acceptance.py" in source,
            f"{label} Control C aggregate-state sync missing",
        )
        _require(
            "FW-RT6-12c-C-AGGREGATE-ACCEPTANCE:BEGIN" in source,
            f"{label} Control C marker sync missing",
        )

    _run(
        [sys.executable, "scripts/smoke_v600_natural_turn_control_a.py", "--source-only"],
        capture=False,
    )
    _run(
        [sys.executable, "scripts/smoke_v600_natural_turn_control_b.py", "--source-only"],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_natural_turn_control_a",
            "tests.test_natural_turn_control_b",
        ],
        capture=False,
    )
    print("[OK] four gate/test files receive aggregate-state-only sync")
    print("[OK] accepted 16 Control A and 12 Control B focused tests passed")


def check_contract_and_session_truth() -> None:
    import framework

    natural_turn = importlib.import_module("framework.natural_turn")
    _require(natural_turn.__all__ == EXPECTED_EXPORTS, "namespace exports drift")
    _require(natural_turn.NATURAL_TURN_API_VERSION == "6.0", "API version drift")
    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in EXPECTED_EXPORTS:
        _require(name not in framework.__all__, f"explicit-only export leaked root: {name}")
    default = natural_turn.default_natural_turn_capability_set()
    _require(
        tuple(capability.extension.value for capability in default.capabilities)
        == EXPECTED_EXTENSIONS,
        "extension inventory drift",
    )
    _require(not default.supported_extensions, "default support overclaim")
    for capability in default.capabilities:
        _require(capability.experimental, "experimental truth drift")
        _require(capability.owner.value == "host_application", "default owner drift")
        _require(capability.explicit_activation_required, "activation truth drift")
        _require(
            not any(
                (
                    capability.microphone_device_access,
                    capability.background_execution,
                    capability.provider_execution,
                    capability.network_execution,
                )
            ),
            f"execution overclaim: {capability.extension.value}",
        )
    try:
        default.capabilities = ()  # type: ignore[misc]
    except (FrozenInstanceError, AttributeError, TypeError):
        pass
    else:
        raise AssertionError("capability set is mutable")

    _require(
        hasattr(framework.RealtimeSession, "natural_turn_capabilities"),
        "RealtimeSession capability snapshot missing",
    )
    _require(
        not hasattr(framework.VoiceInputSession, "natural_turn_capabilities"),
        "VoiceInputSession adoption appeared",
    )
    session = framework.RealtimeSession()
    snapshot = session.natural_turn_capabilities
    _require(snapshot is session.natural_turn_capabilities, "snapshot is not cached")
    _require(not snapshot.supported_extensions, "session support overclaim")
    session.close()
    _require(session.natural_turn_capabilities is snapshot, "snapshot unreadable after close")
    for member in (
        "configure_natural_turn",
        "configure_natural_turn_extension",
        "activate_natural_turn",
        "start_natural_turn",
        "stop_natural_turn",
        "observe_natural_turn",
        "natural_mode",
    ):
        _require(
            not hasattr(framework.RealtimeSession, member),
            f"natural-turn execution API appeared: {member}",
        )
    print("[OK] exact six-name vocabulary and seven default-off capabilities conform")
    print("[OK] one immutable read-only RealtimeSession snapshot conforms")


def check_import_and_execution_safety() -> None:
    probe = r'''
import os
import sys
import threading
sys.path.insert(0, os.getcwd())
import framework
assert "framework.natural_turn" not in sys.modules
session = framework.RealtimeSession()
assert "framework.natural_turn" not in sys.modules
threads_before = {thread.ident for thread in threading.enumerate()}
snapshot = session.natural_turn_capabilities
threads_after = {thread.ident for thread in threading.enumerate()}
assert threads_before == threads_after
assert not snapshot.supported_extensions
assert len(framework.__all__) == 127
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets", "requests", "httpx",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
session.close()
assert session.natural_turn_capabilities is snapshot
'''
    environment = {
        key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"
    }
    _run([sys.executable, "-I", "-c", probe], environment=environment)
    print("[OK] aggregate import remains provider, network, device, and background safe")


def check_accepted_regression_gates() -> None:
    for gate in ACCEPTED_GATES:
        _require((PROJECT_ROOT / gate).is_file(), f"accepted gate missing: {gate}")
        _run([sys.executable, gate, "--source-only"], capture=False)
    print("[OK] accepted FW-RT6-11a/11b/11c/12a/12b gates passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="skip Git baseline/exact-surface checks",
    )
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_history_and_aggregate_state()
    check_contract_and_session_truth()
    check_import_and_execution_safety()
    check_gate_test_semantic_sync()
    check_accepted_regression_gates()
    print("v600_rt6_12c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_12c_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_12c_control_c_exact_surface: 7 files")
    print("v600_rt6_12c_existing_gate_test_sync: 4 files / AGGREGATE STATE ONLY")
    print("v600_rt6_12c_accepted_aggregate_contracts: 2 / 2")
    print("v600_rt6_12c_namespace_exports: 6 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12c_extensions: 7 / EXACT / INDEPENDENT")
    print("v600_rt6_12c_session_capability_adoption: RealtimeSession / READ_ONLY")
    print("v600_rt6_12c_default_supported: 0 / 7")
    print("v600_rt6_12c_activation_api: NONE")
    print("v600_rt6_12c_voice_input_session_adoption: False")
    print("v600_rt6_12c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12c_provider_network_device_background_execution: False")
    print("v600_rt6_12c_roadmap_items_closed: 0 / 7 / UNCHANGED")
    print("v600_rt6_12c_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_13a: NOT_AUTHORIZED")
    print("v600_rt6_12c_control_c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12c Control C aggregate natural-turn gate passed")


if __name__ == "__main__":
    main()
