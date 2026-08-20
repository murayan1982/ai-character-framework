"""FW-RT6-12c Control B read-only session-capability adoption gate."""

from __future__ import annotations

import argparse
import inspect
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "b556712bb20465cf712be449b7c956f784b22044"
EXPECTED_IMPLEMENTATION_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_natural_turn_extensions.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_natural_turn_control_a.py",
    "scripts/smoke_v600_natural_turn_control_b.py",
    "tests/test_natural_turn_control_a.py",
    "tests/test_natural_turn_control_b.py",
}
EXPECTED_ACCEPTANCE_SURFACE = EXPECTED_IMPLEMENTATION_SURFACE | {
    "docs/v600_tasklist.md",
}
EXPECTED_EXTENSIONS = (
    "microphone_listening_while_speaking",
    "vad_based_automatic_detection",
    "wake_word",
    "background_input_monitoring",
    "automatic_next_turn_capture",
    "echo_cancellation",
    "noise_suppression",
)
EXPECTED_FACTORY_PARAMETERS = (
    "project_root",
    "public_metadata",
    "real_runtime_enabled",
    "voice_input_stage",
    "text_generation_stage",
    "voice_output_stage",
    "motion_stage",
    "config",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], *, environment: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        completed.returncode == 0,
        "command failed: " + " ".join(command) + "\n" + (completed.stdout or "") + (completed.stderr or ""),
    )
    return completed.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    paths = _git("-c", "core.safecrlf=false", "diff", "HEAD", "--name-only").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    actual = {path.strip().replace("\\", "/") for path in paths if path.strip()}
    _require(
        actual in (EXPECTED_IMPLEMENTATION_SURFACE, EXPECTED_ACCEPTANCE_SURFACE),
        "Control B exact surface drift; "
        f"implementation={sorted(EXPECTED_IMPLEMENTATION_SURFACE)!r}; "
        f"acceptance={sorted(EXPECTED_ACCEPTANCE_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    label = (
        "nine-file acceptance"
        if actual == EXPECTED_ACCEPTANCE_SURFACE
        else "eight-file implementation"
    )
    print(f"[OK] baseline and exact {label} FW-RT6-12c Control B surface conform")


def check_session_capability_adoption() -> None:
    import framework
    from framework.natural_turn import NaturalTurnCapabilitySet

    _require(len(framework.__all__) == 127, "root-public inventory changed")
    _require(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == EXPECTED_FACTORY_PARAMETERS,
        "realtime factory signature drift",
    )
    _require(
        hasattr(framework.RealtimeSession, "natural_turn_capabilities"),
        "RealtimeSession natural-turn property missing",
    )
    _require(
        not hasattr(framework.VoiceInputSession, "natural_turn_capabilities"),
        "VoiceInputSession natural-turn adoption appeared",
    )
    session = framework.RealtimeSession()
    snapshot = session.natural_turn_capabilities
    _require(isinstance(snapshot, NaturalTurnCapabilitySet), "snapshot type drift")
    _require(session.natural_turn_capabilities is snapshot, "snapshot is not session-owned")
    _require(
        tuple(item.extension.value for item in snapshot.capabilities) == EXPECTED_EXTENSIONS,
        "extension inventory drift",
    )
    _require(not snapshot.supported_extensions, "default support overclaim")
    session.close()
    _require(session.natural_turn_capabilities is snapshot, "snapshot unreadable after close")
    for name in (
        "configure_natural_turn",
        "configure_natural_turn_extension",
        "activate_natural_turn",
        "start_natural_turn",
        "stop_natural_turn",
        "natural_mode",
    ):
        _require(not hasattr(framework.RealtimeSession, name), f"execution API appeared: {name}")
    print("[OK] RealtimeSession adopts one cached default-off snapshot with no execution API")


def check_lazy_import_and_execution_safety() -> None:
    probe = r'''
import os
import sys
import threading
sys.path.insert(0, os.getcwd())
import framework
assert "framework.natural_turn" not in sys.modules
session = framework.RealtimeSession()
assert "framework.natural_turn" not in sys.modules
assert session.capabilities is session.capabilities
assert "framework.natural_turn" not in sys.modules
threads_before = {thread.ident for thread in threading.enumerate()}
snapshot = session.natural_turn_capabilities
threads_after = {thread.ident for thread in threading.enumerate()}
assert threads_before == threads_after
assert not snapshot.supported_extensions
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets", "requests", "httpx",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
session.close()
assert session.natural_turn_capabilities is snapshot
'''
    environment = {key: value for key, value in os.environ.items() if key != "OPENAI_API_KEY"}
    _run([sys.executable, "-I", "-c", probe], environment=environment)
    print("[OK] root/session remain namespace-lazy and property access adds no execution")


def check_docs_and_task_boundary() -> bool:
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs/v600_natural_turn_extensions.md").read_text(encoding="utf-8")
    for source, markers in (
        (app, ("FW-RT6-12c-B-APP-SESSION-CAPABILITIES:BEGIN", "FW-RT6-12c-B-APP-SESSION-CAPABILITIES:END")),
        (facade, ("FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:BEGIN", "FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:END")),
        (guide, ("FW-RT6-12c-B-SESSION-CAPABILITIES:BEGIN", "FW-RT6-12c-B-SESSION-CAPABILITIES:END")),
    ):
        for marker in markers:
            _require(source.count(marker) == 1, f"documentation marker drift: {marker}")
    combined = "\n".join((app, facade, guide)).lower()
    for phrase in (
        "natural_turn_capabilities",
        "read-only",
        "0 / 7",
        "voiceinputsession",
        "not an activation",
    ):
        _require(phrase in combined, f"Control B contract missing: {phrase}")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-12c — Experimental natural-turn extensions", 1)[1].split("## FW-RT6-13a", 1)[0]
    _require(section.count("- [ ]") == 0, "Control B changed 12c task state")
    _require(section.count("- [x]") == 0, "Control B closed a 12c task")
    _require("各項目は別roadmap/exact contractとする。" in section, "separate extension boundary missing")
    acceptance_marker_count = tasklist.count(
        "FW-RT6-12c-B-ACCEPTANCE-SYNC:BEGIN"
    )
    _require(
        acceptance_marker_count <= 1,
        "Control B acceptance-sync marker duplicated",
    )
    if acceptance_marker_count:
        _require(
            tasklist.count("FW-RT6-12c-B-ACCEPTANCE-SYNC:END") == 1,
            "Control B acceptance-sync end marker drift",
        )
        for phrase in (
            "Control B: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH",
            "combined worktree surface: 9 files",
            "FW-RT6-12c roadmap items closed: 0 / 7",
            "aggregate exact contract review: AUTHORIZED_AFTER_COMMIT_PUSH",
        ):
            _require(phrase in tasklist, f"Control B acceptance fact missing: {phrase}")
    print("[OK] public/app/guide contracts conform and all seven runtime items remain open")
    return bool(acceptance_marker_count)


def check_focused_tests() -> None:
    source = (PROJECT_ROOT / "tests/test_natural_turn_control_b.py").read_text(encoding="utf-8")
    _require(source.count("    def test_") == 12, "Control B test count drift")
    _run([sys.executable, "scripts/smoke_v600_natural_turn_control_a.py", "--source-only"])
    _run([sys.executable, "-m", "unittest", "tests.test_natural_turn_control_a", "tests.test_natural_turn_control_b"])
    print("[OK] accepted 16 Control A and 12 Control B focused tests passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true", help="skip Git baseline/exact-surface checks")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_session_capability_adoption()
    check_lazy_import_and_execution_safety()
    acceptance_synced = check_docs_and_task_boundary()
    check_focused_tests()
    status = (
        "COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH"
        if acceptance_synced
        else "IMPLEMENTED / AWAITING_REVIEW"
    )
    sync_status = (
        "IMPLEMENTED / AWAITING_REVIEW"
        if acceptance_synced
        else "NOT_AUTHORIZED"
    )
    print(f"v600_rt6_12c_control_b_status: {status}")
    print("v600_rt6_12c_control_b_exact_surface: 8 files")
    print("v600_rt6_12c_session_capability_adoption: RealtimeSession / READ_ONLY")
    print("v600_rt6_12c_extensions: 7 / EXACT / INDEPENDENT")
    print("v600_rt6_12c_default_supported: 0 / 7")
    print("v600_rt6_12c_activation_api: NONE")
    print("v600_rt6_12c_voice_input_session_adoption: False")
    print("v600_rt6_12c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_12c_provider_network_device_background_execution: False")
    print("v600_rt6_12c_task_count: 0 / 7 CLOSED")
    print(f"v600_rt6_12c_control_b_acceptance_sync: {sync_status}")
    print("v600_rt6_12c_aggregate_acceptance: NOT_AUTHORIZED")
    print("v600_rt6_12c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12c Control B session-capability gate passed")


if __name__ == "__main__":
    main()
