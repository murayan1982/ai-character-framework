"""FW-RT6-2c Control D aggregate terminal-registry acceptance check.

Offline/mock-safe: validates the accepted Control A/B/C history, exact
docs/test-only Control D surface, public compatibility, aggregate documentation,
and the currently implemented terminal-registry behavior without provider,
network, microphone, playback, VTube Studio, private configuration, or DRC
repository execution.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
from pathlib import Path
import subprocess
import sys
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "8393c82a312af73f0b18db106b6e32c959f251a2"
EXPECTED_BASELINE_PARENT = "24cf8f3ff151d3732ad99617d78e1999c1d86ed2"
EXPECTED_BASELINE_SUBJECT = "fix/test: harden realtime terminal finality"

CONTROL_A = "d41d6ae09c18f9d53996490780ca53035952165c"
CONTROL_A_PARENT = "9d0913b9c302b34a2317c4000e3117b814e90447"
CONTROL_A_SUBJECT = "feat/test: add realtime terminal registry primitives"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_terminal_registry.py",
    "scripts/smoke_v600_realtime_terminal_registry_primitives.py",
}

CONTROL_B = EXPECTED_BASELINE_PARENT
CONTROL_B_PARENT = CONTROL_A
CONTROL_B_SUBJECT = "refactor/test: adopt realtime terminal registry"
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_terminal_registry_session_adoption.py",
}

CONTROL_C = EXPECTED_BASELINE
CONTROL_C_PARENT = CONTROL_B
CONTROL_C_SUBJECT = EXPECTED_BASELINE_SUBJECT
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_terminal_registry_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_terminal_registry_reentrant_concurrency.py",
}

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_terminal_registry_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}

FORBIDDEN_IMPORT_FRAGMENTS = (
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).splitlines()
        if line.strip()
    }


def _check_commit(
    *,
    commit: str,
    parent: str,
    subject: str,
    surface: set[str],
    label: str,
) -> None:
    _assert(_git("rev-parse", f"{commit}^") == parent, f"{label} parent drift")
    _assert(
        _git("show", "-s", "--format=%s", commit) == subject,
        f"{label} subject drift",
    )
    _assert(_commit_surface(commit) == surface, f"{label} surface drift")


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control D surface: {sorted(_changed_paths())}",
    )
    _check_commit(
        commit=CONTROL_A,
        parent=CONTROL_A_PARENT,
        subject=CONTROL_A_SUBJECT,
        surface=CONTROL_A_SURFACE,
        label="Control A",
    )
    _check_commit(
        commit=CONTROL_B,
        parent=CONTROL_B_PARENT,
        subject=CONTROL_B_SUBJECT,
        surface=CONTROL_B_SURFACE,
        label="Control B",
    )
    _check_commit(
        commit=CONTROL_C,
        parent=CONTROL_C_PARENT,
        subject=CONTROL_C_SUBJECT,
        surface=CONTROL_C_SURFACE,
        label="Control C",
    )
    print("[OK] Control A/B/C history and exact six-file Control D surface conform")


def _load_script(name: str) -> ModuleType:
    path = PROJECT_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_control_d_{name}", path)
    _assert(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_functions(script: str, names: tuple[str, ...]) -> None:
    module = _load_script(script)
    for name in names:
        function = getattr(module, name, None)
        _assert(callable(function), f"{script}.{name} is missing")
        print(f"[RUN] {script}.py::{name}")
        function()


def check_source_contract() -> None:
    registry_path = PROJECT_ROOT / "framework" / "realtime_terminal_registry.py"
    session_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    registry_source = registry_path.read_text(encoding="utf-8")
    session_source = session_path.read_text(encoding="utf-8")
    ast.parse(registry_source, filename=str(registry_path))
    ast.parse(session_source, filename=str(session_path))

    for phrase in (
        "class RealtimeTerminalRegistry",
        "def commit(",
        "def admit_non_terminal(",
        "duplicate_terminal_count",
        "terminal_regression_count",
        "late_non_terminal_count",
    ):
        _assert(phrase in registry_source, f"registry source missing: {phrase}")

    for phrase in (
        "RealtimeTerminalRegistry[RealtimeTurnResult]()",
        "def terminal_results",
        "def terminal_diagnostics",
        "def _commit_terminal_result",
        "_TURN_TERMINAL_EVENT_TYPES = frozenset(",
        "not self._terminal_registry.admit_non_terminal(turn_id)",
        "class _LateNonTerminalRejected(RuntimeError):",
        'safe_message="Realtime turn is already terminal."',
    ):
        _assert(phrase in session_source, f"session source missing: {phrase}")

    print("[OK] accepted terminal registry/session source facts conform")


def check_public_compatibility() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert(
        "RealtimeTerminalRegistry" not in framework.__all__,
        "internal terminal registry leaked root-public",
    )
    _assert(
        "_LateNonTerminalRejected" not in framework.__all__,
        "private rejection signal leaked root-public",
    )
    _assert(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == ("project_root", "public_metadata", "real_runtime_enabled"),
        "create_realtime_session signature drift",
    )
    session = framework.create_realtime_session()
    _assert(
        set(session.event_diagnostics)
        == {
            "emitted_event_count",
            "callback_error_count",
            "slow_callback_count",
            "history_overflow_count",
            "rejected_after_close_count",
            "subscriber_count",
            "history_limit",
        },
        "event diagnostics keys changed",
    )
    _assert(
        set(session.terminal_diagnostics)
        == {
            "terminal_commit_count",
            "duplicate_terminal_count",
            "terminal_regression_count",
            "late_non_terminal_count",
            "registry_size",
        },
        "terminal diagnostics keys changed",
    )
    print("[OK] root-public and read-only diagnostic compatibility conform")


def check_aggregate_docs() -> None:
    required_markers = {
        PROJECT_ROOT / "README.md": (
            "FW-RT6-2c-D-TERMINAL-REGISTRY-ACCEPTANCE:BEGIN",
            "FW-RT6-2c-D-TERMINAL-REGISTRY-ACCEPTANCE:END",
        ),
        PROJECT_ROOT / "docs" / "v600_tasklist.md": (
            "FW-RT6-2c-D-ACCEPTANCE-SYNC:BEGIN",
            "FW-RT6-2c-D-ACCEPTANCE-SYNC:END",
        ),
        PROJECT_ROOT / "docs" / "v600_current_source_gap_inventory.md": (
            "FW-RT6-2c-D-GAP-RESOLUTION-SYNC:BEGIN",
            "FW-RT6-2c-D-GAP-RESOLUTION-SYNC:END",
        ),
    }
    for path, markers in required_markers.items():
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            _assert(marker in text, f"missing aggregate marker: {marker}")

    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(
        encoding="utf-8"
    )
    for line in (
        "- [x] turn terminal registryを追加する。",
        "- [x] first terminal commitをatomicにする。",
        "- [x] duplicate terminalを抑止する。",
        "- [x] late non-terminal eventを拒否する。",
        "- [x] terminal reason/resultを保持する。",
        "- [x] stale/duplicate diagnostic counterを追加する。",
        "- [x] multi-thread race testを追加する。",
    ):
        _assert(line in tasklist, f"tasklist acceptance line missing: {line}")

    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in required_markers
    )
    for phrase in (
        "current verified RealtimeSession first-terminal path: TURN_COMPLETED",
        "all provider-driven terminal paths wired: False / NOT CLAIMED",
        "generation stale-result rejection: DEFERRED / FW-RT6-2d",
        "next checkpoint: FW-RT6-2d",
        "G-04 per-session terminal registry: RESOLVED",
        "G-04 same-turn concurrent integration race: RESOLVED",
        "G-05 generation stale-result rejection: UNRESOLVED / FW-RT6-2d",
    ):
        _assert(phrase in combined, f"aggregate documentation missing: {phrase}")

    print("[OK] README, tasklist, and gap inventory record truthful aggregate acceptance")


def check_historical_runtime_behavior() -> None:
    _run_functions(
        "smoke_v600_realtime_terminal_registry_primitives",
        (
            "check_import_safety",
            "check_first_duplicate_regression_and_retention",
            "check_identity_compatibility_and_validation",
            "check_atomic_multi_thread_race",
            "check_import_safety",
        ),
    )
    _run_functions(
        "smoke_v600_realtime_terminal_registry_session_adoption",
        (
            "check_import_safety",
            "check_public_compatibility",
            "check_atomic_terminal_delivery_and_duplicate_suppression",
            "check_import_safety",
        ),
    )
    _run_functions(
        "smoke_v600_realtime_terminal_registry_reentrant_concurrency",
        (
            "check_source_contract",
            "check_import_safety",
            "check_reentrant_terminal_callback_rejection",
            "check_same_turn_concurrent_run_is_one_group",
            "check_different_turn_groups_remain_serialized",
            "check_close_contract_is_preserved",
            "check_public_compatibility_and_docs",
            "check_import_safety",
        ),
    )
    _run_functions(
        "smoke_v600_realtime_event_hub_close_hardening",
        (
            "check_import_safety",
            "check_close_seals_and_post_close_is_silent",
            "check_reentrant_close_is_deferred",
            "check_concurrent_operations_do_not_interleave",
            "check_concurrent_close_waits_for_operation_boundary",
            "check_import_safety",
        ),
    )
    print("[OK] accepted terminal and close/concurrency runtime behavior remains conformant")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] Control D validation stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_source_contract()
    check_import_safety()
    check_public_compatibility()
    check_aggregate_docs()
    check_historical_runtime_behavior()
    check_import_safety()

    print("v600_rt6_2c_control_d_status: implemented-awaiting-review")
    print("v600_rt6_2c_control_d_exact_change_surface_count: 6")
    print("v600_rt6_2c_control_d_runtime_source_changed: False")
    print("v600_rt6_2c_control_d_root_public_names: 121 / unchanged")
    print("v600_rt6_2c_control_d_controls_a_b_c: accepted")
    print("v600_rt6_2c_control_d_current_verified_terminal_path: TURN_COMPLETED")
    print("v600_rt6_2c_control_d_all_provider_terminal_paths_wired: False")
    print("v600_rt6_2c_control_d_one_terminal_event_per_turn: PASS")
    print("v600_rt6_2c_control_d_duplicate_terminal_suppressed: PASS")
    print("v600_rt6_2c_control_d_state_regression_rejected: PASS")
    print("v600_rt6_2c_control_d_same_turn_concurrent_groups: 1")
    print("v600_rt6_2c_control_d_same_turn_terminal_events: 1")
    print("v600_rt6_2c_control_d_same_turn_terminal_records: 1")
    print("v600_rt6_2c_control_d_terminal_callback_late_events: 0")
    print("v600_rt6_2c_control_d_event_diagnostics_changed: False")
    print("v600_rt6_2c_control_d_generation_stale_rejection: deferred-FW-RT6-2d")
    print("v600_rt6_2c_control_d_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2c_next_checkpoint: FW-RT6-2d")
    print("v600_rt6_2c_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-2c Control D aggregate terminal-registry acceptance conforms")


if __name__ == "__main__":
    main()
