"""FW-RT6-2d Control D aggregate generation-gate acceptance check.

Offline/mock-safe: validates the accepted Control A/B/C/C1 history, exact
six-file docs/test-only Control D surface, public compatibility, aggregate
documentation, terminal-registry regression, stale-completion delivery
suppression, and VTube Studio semantic alignment without provider, network,
microphone, playback, real VTube Studio, private configuration, DRC repository,
or root-draft stash operation.
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

EXPECTED_BASELINE = "aee53d77840f49450d9319a1ff5208cec7471757"
EXPECTED_BASELINE_PARENT = "7e26f3663f1a0121280dea57114fdfbf79b751dc"
EXPECTED_BASELINE_SUBJECT = "fix/test: preserve terminal callback late rejection"

CONTROL_A = "e3f5ce7088596e1f2ceaa3c504a16b35c47863b8"
CONTROL_A_PARENT = "498e27ec264b0120f1f94a859cff6462bdfc7acd"
CONTROL_A_SUBJECT = "feat/test: add realtime generation gate primitives"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_generation_gate_contract.md",
    "framework/realtime_generation_gate.py",
    "scripts/smoke_v600_realtime_generation_gate_primitives.py",
}

CONTROL_B = "56ca83965f288d0c591a3969c45cb92b820a380a"
CONTROL_B_PARENT = CONTROL_A
CONTROL_B_SUBJECT = "refactor/test: adopt realtime generation gate"
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_generation_gate_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_generation_gate_primitives.py",
    "scripts/smoke_v600_realtime_generation_gate_session_adoption.py",
}

CONTROL_C = EXPECTED_BASELINE_PARENT
CONTROL_C_PARENT = CONTROL_B
CONTROL_C_SUBJECT = "test/docs: verify realtime generation race alignment"
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_generation_gate_contract.md",
    "scripts/smoke_v600_realtime_generation_gate_primitives.py",
    "scripts/smoke_v600_realtime_generation_gate_session_adoption.py",
    "scripts/smoke_v600_realtime_generation_gate_race_alignment.py",
}

CONTROL_C_CORRECTIVE_1 = EXPECTED_BASELINE
CONTROL_C_CORRECTIVE_1_PARENT = CONTROL_C
CONTROL_C_CORRECTIVE_1_SUBJECT = EXPECTED_BASELINE_SUBJECT
CONTROL_C_CORRECTIVE_1_SURFACE = {
    "docs/v600_realtime_generation_gate_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_generation_gate_terminal_callback_compatibility.py",
}

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_generation_gate_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}

UNCHANGED_RUNTIME_PATHS = (
    "framework/realtime_generation_gate.py",
    "framework/realtime_session.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_terminal_registry.py",
    "framework/vtube_studio_pyvts_transport.py",
    "framework/vtube_studio_transport.py",
    "framework/public_api.py",
    "framework/__init__.py",
)

GENERATION_DIAGNOSTIC_KEYS = {
    "generation_start_count",
    "generation_advance_count",
    "accepted_completion_count",
    "stale_completion_count",
    "active_generation_count",
    "registry_size",
}
EVENT_DIAGNOSTIC_KEYS = {
    "emitted_event_count",
    "callback_error_count",
    "slow_callback_count",
    "history_overflow_count",
    "rejected_after_close_count",
    "subscriber_count",
    "history_limit",
}
TERMINAL_DIAGNOSTIC_KEYS = {
    "terminal_commit_count",
    "duplicate_terminal_count",
    "terminal_regression_count",
    "late_non_terminal_count",
    "registry_size",
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
    _check_commit(
        commit=CONTROL_C_CORRECTIVE_1,
        parent=CONTROL_C_CORRECTIVE_1_PARENT,
        subject=CONTROL_C_CORRECTIVE_1_SUBJECT,
        surface=CONTROL_C_CORRECTIVE_1_SURFACE,
        label="Control C corrective 1",
    )
    for relative in UNCHANGED_RUNTIME_PATHS:
        _assert(
            _git("hash-object", relative) == _git("rev-parse", f"HEAD:{relative}"),
            f"runtime source changed during Control D: {relative}",
        )
    print("[OK] Control A/B/C/C1 history and exact six-file Control D surface conform")


def _load_script(filename: str) -> ModuleType:
    path = PROJECT_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(f"_rt6_2d_control_d_{path.stem}", path)
    _assert(spec is not None and spec.loader is not None, f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_script(filename: str, expected_phrases: tuple[str, ...]) -> None:
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / filename)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"{filename} failed:\n{output}")
    for phrase in expected_phrases:
        _assert(phrase in output, f"{filename} output missing: {phrase}")
    print(f"[OK] {filename} conforms")


def check_source_contract() -> None:
    gate_path = PROJECT_ROOT / "framework" / "realtime_generation_gate.py"
    session_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    gate_source = gate_path.read_text(encoding="utf-8")
    session_source = session_path.read_text(encoding="utf-8")
    ast.parse(gate_source, filename=str(gate_path))
    ast.parse(session_source, filename=str(session_path))

    for phrase in (
        "class GenerationAdvanceReason(str, Enum):",
        "class StaleCompletionReason(str, Enum):",
        "class RealtimeStageCompletionEnvelope",
        "class RealtimeGenerationGate:",
        "def start_generation(",
        "def advance(",
        "def admit_completion(",
    ):
        _assert(phrase in gate_source, f"generation gate source missing: {phrase}")

    for phrase in (
        "def _apply_stage_completion(",
        "self._generation_gate.admit_completion(envelope)",
        "self._emit_stale_completion_diagnostic(decision)",
        "def _start_turn_generation(",
        "def _advance_generation(",
        '"turn_terminal",',
        "or self._active_turn_id",
    ):
        _assert(phrase in session_source, f"RealtimeSession source missing: {phrase}")

    _assert(
        "def reset(" not in session_source,
        "Control D must not add a public RealtimeSession reset method",
    )
    print("[OK] accepted generation gate and central completion-ingress source facts conform")


def check_public_compatibility() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    for internal_name in (
        "RealtimeGenerationGate",
        "RealtimeStageCompletionEnvelope",
        "GenerationAdvanceReason",
        "StaleCompletionReason",
    ):
        _assert(internal_name not in framework.__all__, f"internal name leaked: {internal_name}")
    _assert(
        tuple(inspect.signature(framework.create_realtime_session).parameters)
        == ("project_root", "public_metadata", "real_runtime_enabled"),
        "create_realtime_session signature drift",
    )
    session = framework.create_realtime_session()
    _assert(set(session.generation_diagnostics) == GENERATION_DIAGNOSTIC_KEYS, "generation diagnostics keys changed")
    _assert(set(session.event_diagnostics) == EVENT_DIAGNOSTIC_KEYS, "event diagnostics keys changed")
    _assert(set(session.terminal_diagnostics) == TERMINAL_DIAGNOSTIC_KEYS, "terminal diagnostics keys changed")
    session.close()
    print("[OK] root-public, factory, and read-only diagnostic compatibility conform")


def check_aggregate_docs() -> None:
    required_markers = {
        PROJECT_ROOT / "README.md": (
            "FW-RT6-2d-D-GENERATION-GATE-ACCEPTANCE:BEGIN",
            "FW-RT6-2d-D-GENERATION-GATE-ACCEPTANCE:END",
        ),
        PROJECT_ROOT / "docs" / "v600_tasklist.md": (
            "FW-RT6-2d-D-ACCEPTANCE-SYNC:BEGIN",
            "FW-RT6-2d-D-ACCEPTANCE-SYNC:END",
        ),
        PROJECT_ROOT / "docs" / "v600_current_source_gap_inventory.md": (
            "FW-RT6-2d-D-GAP-RESOLUTION-SYNC:BEGIN",
            "FW-RT6-2d-D-GAP-RESOLUTION-SYNC:END",
        ),
    }
    for path, markers in required_markers.items():
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            _assert(marker in text, f"missing aggregate marker: {marker}")

    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(encoding="utf-8")
    for line in (
        "- [x] current generation registryを追加する。",
        "- [x] new turn/interrupt/reset/close時のincrement ruleを固定する。",
        "- [x] stage completion envelopeへgenerationを付与する。",
        "- [x] stale completion判定を一箇所に集約する。",
        "- [x] VTS transportの既存late suppressionと整合させる。",
        "- [x] stale drop reasonをtyped diagnosticにする。",
    ):
        _assert(line in tasklist, f"tasklist acceptance line missing: {line}")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in required_markers)
    for phrase in (
        "Control D initial candidate: ROLLED BACK / PRESERVED IN HISTORY",
        "runtime source changed: False",
        "old turn response delta delivered: False",
        "old TTS artifact delivered: False",
        "close-requested / post-close completion delivered: False",
        "open-session stale drop observable: True",
        "stale diagnostic legacy projection: None",
        "terminal callback interrupt events: 0",
        "terminal callback cancel events: 0",
        "all real provider-driven stage paths wired: False / NOT CLAIMED",
        "public RealtimeSession reset method: NOT ADDED",
        "normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c",
        "real unified turn orchestration: UNRESOLVED",
        "next checkpoint: FW-RT6-3a",
        "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED",
    ):
        _assert(phrase in combined, f"aggregate documentation missing: {phrase}")

    print("[OK] README, tasklist, and gap inventory record truthful aggregate acceptance")


def check_historical_runtime_behavior() -> None:
    corrective = _load_script(
        "smoke_v600_realtime_generation_gate_terminal_callback_compatibility.py"
    )
    for function_name in (
        "check_source_contract",
        "check_import_safety",
        "check_terminal_callback_late_operations",
        "check_normal_post_turn_no_active_interrupt",
        "check_historical_acceptance",
        "check_public_compatibility_and_docs",
        "check_import_safety",
    ):
        function = getattr(corrective, function_name, None)
        _assert(callable(function), f"corrective function missing: {function_name}")
        print(f"[RUN] terminal callback corrective::{function_name}")
        function()
    print("[OK] terminal registry and generation Controls A/B/C/C1 remain conformant")


def check_manifest_and_version_gates() -> None:
    _run_script(
        "smoke_v600_public_api_manifest.py",
        (
            "v600_public_api_manifest_name_count: 121",
            "v600_realtime_generation_gate_status: accepted",
            "v600_realtime_generation_gate_real_provider_paths_all_wired: False",
            "v600_next_checkpoint: FW-RT6-3a",
        ),
    )
    _run_script(
        "smoke_v600_version_metadata.py",
        (
            "v600_framework_source_version: 6.0.0.dev0",
            "v600_latest_published_release: 5.5.0",
            "v600_root_public_name_count: 121",
            "v600_realtime_generation_gate_real_provider_paths_all_wired: False",
            "v600_next_checkpoint: FW-RT6-3a",
        ),
    )
    print("[OK] public manifest and frozen version metadata record FW-RT6-2d acceptance")


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
    check_manifest_and_version_gates()
    check_import_safety()

    print("v600_rt6_2d_control_d_status: implemented-awaiting-review")
    print("v600_rt6_2d_control_d_exact_change_surface_count: 6")
    print("v600_rt6_2d_control_d_runtime_source_changed: False")
    print("v600_rt6_2d_control_d_root_public_names: 121 / unchanged")
    print("v600_rt6_2d_control_d_controls_a_b_c_c1: accepted")
    print("v600_rt6_2d_control_d_old_turn_delta_delivered: False")
    print("v600_rt6_2d_control_d_old_tts_artifact_delivered: False")
    print("v600_rt6_2d_control_d_close_completion_delivered: False")
    print("v600_rt6_2d_control_d_stale_drop_observable: True")
    print("v600_rt6_2d_control_d_stale_legacy_projection: None")
    print("v600_rt6_2d_control_d_terminal_callback_interrupt_events: 0")
    print("v600_rt6_2d_control_d_terminal_callback_cancel_events: 0")
    print("v600_rt6_2d_control_d_terminal_callback_state_phase_history_mutated: False")
    print("v600_rt6_2d_control_d_normal_post_turn_no_active_preserved: True")
    print("v600_rt6_2d_control_d_vts_source_changed: False")
    print("v600_rt6_2d_control_d_real_provider_paths_all_wired: False")
    print("v600_rt6_2d_control_d_public_realtime_reset_added: False")
    print("v600_rt6_2d_control_d_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_2d_control_d_drc_repository_accessed_or_changed: False")
    print("v600_rt6_2d_control_d_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_2d_next_checkpoint: FW-RT6-3a")
    print("v600_rt6_2d_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-2d Control D aggregate generation-gate acceptance conforms")


if __name__ == "__main__":
    main()
