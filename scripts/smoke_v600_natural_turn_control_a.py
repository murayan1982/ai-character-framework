"""FW-RT6-12c Control A experimental natural-turn contract gate."""

from __future__ import annotations

import argparse
import ast
import importlib
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "e5a41949370d341448e51ba47a6209b14dee9f80"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_natural_turn_extensions.md",
    "framework/natural_turn.py",
    "scripts/smoke_v600_natural_turn_control_a.py",
    "tests/test_natural_turn_control_a.py",
}
EXPECTED_ACCEPTANCE_SURFACE = EXPECTED_SURFACE | {"docs/v600_tasklist.md"}
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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
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


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    actual = {
        path.strip().replace("\\", "/") for path in paths if path.strip()
    }
    _require(
        actual in (EXPECTED_SURFACE, EXPECTED_ACCEPTANCE_SURFACE),
        "Control A exact surface drift; "
        f"implementation={sorted(EXPECTED_SURFACE)!r}; "
        f"acceptance={sorted(EXPECTED_ACCEPTANCE_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    label = (
        "seven-file acceptance"
        if actual == EXPECTED_ACCEPTANCE_SURFACE
        else "six-file implementation"
    )
    print(f"[OK] baseline and exact {label} FW-RT6-12c Control A surface conform")


def check_namespace_and_import_safety() -> None:
    namespace = importlib.import_module("framework.natural_turn")
    _require(namespace.__all__ == EXPECTED_EXPORTS, "namespace exports drift")
    _require(namespace.NATURAL_TURN_API_VERSION == "6.0", "API version drift")
    _require(len(set(namespace.__all__)) == 6, "namespace exports are not unique")

    tree = ast.parse(
        (PROJECT_ROOT / "framework/natural_turn.py").read_text(encoding="utf-8")
    )
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    _require(
        imports
        == {
            "__future__",
            "dataclasses",
            "enum",
            "types",
            "typing",
            "public_safety",
        },
        f"natural-turn module import drift: {sorted(imports)!r}",
    )

    probe = r'''
import os
import sys
sys.path.insert(0, os.getcwd())
import framework.natural_turn as natural_turn
assert len(natural_turn.__all__) == 6
assert not natural_turn.default_natural_turn_capability_set().supported_extensions
forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets", "requests", "httpx",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
assert not loaded.intersection(forbidden), sorted(loaded.intersection(forbidden))
'''
    _run([sys.executable, "-I", "-c", probe])
    print("[OK] explicit six-name namespace is provider, network, device, and background safe")


def check_capability_contract() -> None:
    from framework.natural_turn import (
        NaturalTurnCapability,
        NaturalTurnCapabilitySet,
        NaturalTurnExtension,
        default_natural_turn_capability_set,
    )

    _require(
        tuple(extension.value for extension in NaturalTurnExtension)
        == EXPECTED_EXTENSIONS,
        "natural-turn extension vocabulary drift",
    )
    capability_set = default_natural_turn_capability_set()
    _require(isinstance(capability_set, NaturalTurnCapabilitySet), "set type drift")
    _require(len(capability_set.capabilities) == 7, "capability count drift")
    _require(not capability_set.supported_extensions, "default support overclaim")
    for extension in EXPECTED_EXTENSIONS:
        capability = capability_set.for_extension(extension)
        _require(not capability.supported, f"default support overclaim: {extension}")
        _require(capability.experimental, f"experimental flag drift: {extension}")
        _require(
            capability.owner.value == "host_application",
            f"default owner drift: {extension}",
        )
        _require(
            capability.explicit_activation_required,
            f"explicit activation drift: {extension}",
        )
        _require(
            not any(
                (
                    capability.microphone_device_access,
                    capability.background_execution,
                    capability.provider_execution,
                    capability.network_execution,
                )
            ),
            f"default execution overclaim: {extension}",
        )

    explicit = NaturalTurnCapability(
        extension="noise_suppression",
        supported=True,
        owner="explicit_adapter",
    )
    _require(explicit.supported, "explicit adapter capability construction failed")
    print("[OK] seven independent default-off capability contracts conform")


def check_public_safety_and_root_boundary() -> None:
    import framework
    from framework.natural_turn import NaturalTurnCapability
    from framework.public_safety import REDACTED_BINARY, REDACTED_VALUE

    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in EXPECTED_EXPORTS:
        _require(name not in framework.__all__, f"explicit name leaked root: {name}")
        _require(not hasattr(framework, name), f"explicit attribute leaked root: {name}")
    capability = NaturalTurnCapability(
        extension="wake_word",
        public_metadata={"payload": b"private", "api_key": "private"},
    )
    projection = capability.as_dict()
    metadata = projection["public_metadata"]
    _require(metadata["payload"] == REDACTED_BINARY, "binary metadata leak")
    _require(metadata["api_key"] == REDACTED_VALUE, "secret metadata leak")
    _require("private" not in repr(capability), "private value leaked through repr")
    print("[OK] immutable public projections are payload-safe and root remains 127 names")


def check_docs_task_and_runtime_boundary() -> tuple[bool, bool, bool]:
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    guide = (PROJECT_ROOT / "docs/v600_natural_turn_extensions.md").read_text(
        encoding="utf-8"
    )
    for source, markers in (
        (
            app,
            (
                "FW-RT6-12c-A-APP-NATURAL-TURN:BEGIN",
                "FW-RT6-12c-A-APP-NATURAL-TURN:END",
            ),
        ),
        (
            facade,
            (
                "FW-RT6-12c-A-PUBLIC-NATURAL-TURN:BEGIN",
                "FW-RT6-12c-A-PUBLIC-NATURAL-TURN:END",
            ),
        ),
    ):
        for marker in markers:
            _require(source.count(marker) == 1, f"documentation marker drift: {marker}")
    combined = "\n".join((app, facade, guide)).lower()
    for phrase in (
        "framework.natural_turn",
        "explicit",
        "host",
        "independent",
        "not required for v6.0.0 p0 acceptance",
        "control b",
    ):
        _require(phrase in combined, f"contract documentation missing: {phrase}")
    for extension in EXPECTED_EXTENSIONS:
        _require(extension in combined, f"documented extension missing: {extension}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split(
        "## FW-RT6-12c — Experimental natural-turn extensions", 1
    )[1].split("## FW-RT6-13a", 1)[0]
    _require(section.count("- [ ]") == 0, "Control A changed 12c task state")
    _require(section.count("- [x]") == 0, "Control A closed a 12c task")
    _require(
        "各項目は別roadmap/exact contractとする。" in section,
        "separate exact-contract boundary missing",
    )
    acceptance_marker_count = tasklist.count(
        "FW-RT6-12c-A-ACCEPTANCE-SYNC:BEGIN"
    )
    _require(
        acceptance_marker_count <= 1,
        "Control A acceptance-sync marker duplicated",
    )
    if acceptance_marker_count:
        _require(
            tasklist.count("FW-RT6-12c-A-ACCEPTANCE-SYNC:END") == 1,
            "Control A acceptance-sync end marker drift",
        )
        _require(
            "Control A: COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH"
            in tasklist,
            "Control A accepted status missing",
        )
    aggregate_marker_count = tasklist.count(
        "FW-RT6-12c-C-AGGREGATE-ACCEPTANCE:BEGIN"
    )
    _require(aggregate_marker_count <= 1, "Control C aggregate marker duplicated")
    if aggregate_marker_count:
        for marker in (
            "FW-RT6-12c-C-AGGREGATE-ACCEPTANCE:END",
            "FW-RT6-12c-C-NATURAL-TURN-ACCEPTANCE:BEGIN",
            "FW-RT6-12c-C-NATURAL-TURN-ACCEPTANCE:END",
        ):
            source = facade if "NATURAL-TURN" in marker else tasklist
            _require(source.count(marker) == 1, f"Control C marker drift: {marker}")
        _require(
            (PROJECT_ROOT / "scripts/check_v600_natural_turn_acceptance.py").is_file(),
            "Control C aggregate gate missing",
        )
        for phrase in (
            "Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
            "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
            "Control A/B gate/test semantic sync: 4 files / CONTROL_C AGGREGATE STATE ONLY",
            "FW-RT6-12c roadmap items closed: 0 / 7 / UNCHANGED",
        ):
            _require(phrase in tasklist, f"Control C aggregate fact missing: {phrase}")
    for relative_path in (
        "framework/__init__.py",
        "framework/voice_input_session.py",
    ):
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        _require("natural_turn" not in source, f"unexpected adoption appeared: {relative_path}")

    control_b_adopted = (
        facade.count("FW-RT6-12c-B-PUBLIC-SESSION-CAPABILITIES:BEGIN") == 1
    )
    realtime_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(
        encoding="utf-8"
    )
    if control_b_adopted:
        _require(
            "natural_turn_capabilities" in realtime_source,
            "Control B read-only capability property missing",
        )
        for forbidden_member in (
            "configure_natural_turn",
            "activate_natural_turn",
            "start_natural_turn",
            "natural_mode",
        ):
            _require(
                forbidden_member not in realtime_source,
                f"Control B execution API appeared: {forbidden_member}",
            )
    else:
        _require(
            "natural_turn" not in realtime_source,
            "runtime adoption appeared before Control B",
        )
    print("[OK] public/app/guide contracts conform; execution remains separately gated")
    return bool(acceptance_marker_count), control_b_adopted, bool(aggregate_marker_count)


def check_focused_tests() -> None:
    source = (PROJECT_ROOT / "tests/test_natural_turn_control_a.py").read_text(
        encoding="utf-8"
    )
    _require(source.count("    def test_") == 16, "Control A test count drift")
    _run([sys.executable, "-m", "unittest", "tests.test_natural_turn_control_a"])
    print("[OK] 16 focused FW-RT6-12c Control A tests passed")


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
    check_namespace_and_import_safety()
    check_capability_contract()
    check_public_safety_and_root_boundary()
    acceptance_synced, control_b_adopted, aggregate_synced = (
        check_docs_task_and_runtime_boundary()
    )
    check_focused_tests()

    status = (
        "COMPLETED / VERIFIED / ACCEPTED / CLOSED"
        if aggregate_synced
        else (
            "COMPLETED / VERIFIED / ACCEPTED / AWAITING_COMMIT_PUSH"
            if acceptance_synced
            else "IMPLEMENTED / AWAITING_REVIEW"
        )
    )
    sync_status = (
        "b556712bb20465cf712be449b7c956f784b22044 / CLOSED"
        if aggregate_synced
        else (
            "IMPLEMENTED / AWAITING_REVIEW"
            if acceptance_synced
            else "NOT_AUTHORIZED"
        )
    )
    print(f"v600_rt6_12c_control_a_status: {status}")
    print("v600_rt6_12c_control_a_exact_surface: 6 files")
    print("v600_rt6_12c_namespace_exports: 6 / EXACT / EXPLICIT_ONLY")
    print("v600_rt6_12c_extensions: 7 / EXACT / INDEPENDENT")
    print("v600_rt6_12c_default_supported: 0 / 7")
    print("v600_rt6_12c_root_public_names: 127 / UNCHANGED")
    print(
        "v600_rt6_12c_session_capability_adoption: "
        + ("RealtimeSession / CONTROL_B / READ_ONLY" if control_b_adopted else "False")
    )
    print("v600_rt6_12c_extension_execution: False")
    print("v600_rt6_12c_p0_required: False")
    print("v600_rt6_12c_provider_network_device_background_execution: False")
    print(f"v600_rt6_12c_control_a_acceptance_sync: {sync_status}")
    print(
        "v600_rt6_12c_control_b: "
        + (
            "COMPLETED / VERIFIED / ACCEPTED / CLOSED"
            if aggregate_synced
            else (
                "IMPLEMENTED / AWAITING_REVIEW"
                if control_b_adopted
                else "NOT_AUTHORIZED"
            )
        )
    )
    print(
        "v600_rt6_12c_control_c: "
        + ("IMPLEMENTED / AWAITING_REVIEW" if aggregate_synced else "NOT_AUTHORIZED")
    )
    print("v600_rt6_12c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-12c Control A natural-turn capability gate passed")


if __name__ == "__main__":
    main()
