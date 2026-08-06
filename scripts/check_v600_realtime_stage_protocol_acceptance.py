"""FW-RT6-3a Control C aggregate realtime-stage acceptance check.

Offline/mock-safe: validates Control A/B history, the exact six-file docs/test-only
Control C surface, provider-neutral stage protocols and injection, fake-stage
composition, public compatibility, accepted runtime regressions, and truthful
aggregate documentation without provider, network, microphone, playback, real
VTube Studio, private configuration, DRC repository, or root-draft stash access.
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

EXPECTED_BASELINE = "8db6a4ff1c9687b9e9d04b2f55a38611e27e0a5e"
EXPECTED_BASELINE_PARENT = "af474e2ceec9988bec1b7e7fadfe2d4037774597"
EXPECTED_BASELINE_SUBJECT = "refactor/test: inject realtime stages"

CONTROL_A = EXPECTED_BASELINE_PARENT
CONTROL_A_PARENT = "6fe95075e1c9ae9e62150eb9844edfe9f004a8e2"
CONTROL_A_SUBJECT = "feat/test: add realtime stage protocols"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/realtime_stage.py",
    "scripts/smoke_v600_realtime_stage_protocols.py",
}

CONTROL_B = EXPECTED_BASELINE
CONTROL_B_PARENT = CONTROL_A
CONTROL_B_SUBJECT = EXPECTED_BASELINE_SUBJECT
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_stage_injection.py",
}

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_stage_protocol_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}

UNCHANGED_ACCEPTED_PATHS = (
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/realtime_stage.py",
    "framework/realtime_session.py",
    "framework/realtime_generation_gate.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_terminal_registry.py",
    "framework/public_api.py",
    "framework/__init__.py",
    "scripts/smoke_v600_realtime_stage_protocols.py",
    "scripts/smoke_v600_realtime_stage_injection.py",
)

EXPECTED_FACTORY_PARAMETERS = (
    "project_root",
    "public_metadata",
    "real_runtime_enabled",
    "voice_input_stage",
    "text_generation_stage",
    "voice_output_stage",
    "motion_stage",
)
EXPECTED_STAGE_KINDS = (
    "voice_input",
    "text_generation",
    "voice_output",
    "motion",
)
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
        f"unexpected Control C surface: {sorted(_changed_paths())}",
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
    for relative in UNCHANGED_ACCEPTED_PATHS:
        _assert(
            _git("hash-object", relative) == _git("rev-parse", f"HEAD:{relative}"),
            f"accepted source changed during Control C: {relative}",
        )
    print("[OK] Control A/B history and exact six-file Control C surface conform")


def _load_script(filename: str, module_name: str) -> ModuleType:
    path = PROJECT_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
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
    stage_path = PROJECT_ROOT / "framework" / "realtime_stage.py"
    session_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    stage_source = stage_path.read_text(encoding="utf-8")
    session_source = session_path.read_text(encoding="utf-8")
    ast.parse(stage_source, filename=str(stage_path))
    ast.parse(session_source, filename=str(session_path))

    for phrase in (
        "class RealtimeStageKind(str, Enum):",
        "class RealtimeStageContext:",
        "class RealtimeStageResultEnvelope",
        "class VoiceInputStage(Protocol):",
        "class TextGenerationStage(Protocol):",
        "class VoiceOutputStage(Protocol):",
        "class MotionStage(Protocol):",
    ):
        _assert(phrase in stage_source, f"stage source missing: {phrase}")

    for method in ("preflight", "capability", "start", "cancel", "close"):
        _assert(
            stage_source.count(f"    def {method}(") >= 4,
            f"common stage method missing or incomplete: {method}",
        )

    for phrase in (
        "def _validated_injected_stages(",
        "def injected_stage_kinds(self) -> tuple[str, ...]:",
        "def stage_diagnostics(self) -> Mapping[str, int]:",
        "def _close_injected_stages(self) -> None:",
        "self._close_injected_stages()",
    ):
        _assert(phrase in session_source, f"session injection source missing: {phrase}")

    _assert(
        ".start(context=" not in session_source,
        "Control C must not add injected-stage start orchestration",
    )
    _assert(
        ".preflight()" not in session_source and ".capability()" not in session_source,
        "Control C must not add stage capability/preflight composition",
    )
    print("[OK] accepted stage protocol and injection source facts conform")


def check_public_compatibility() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES
    from framework.realtime_session import RealtimeSession

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    for name in (
        "RealtimeStageKind",
        "RealtimeStageContext",
        "RealtimeStageResultEnvelope",
        "VoiceInputStage",
        "TextGenerationStage",
        "VoiceOutputStage",
        "MotionStage",
    ):
        _assert(name not in framework.__all__, f"stage package name leaked to root: {name}")

    for callable_object, label in (
        (framework.create_realtime_session, "factory"),
        (RealtimeSession, "constructor"),
    ):
        signature = inspect.signature(callable_object)
        _assert(
            tuple(signature.parameters) == EXPECTED_FACTORY_PARAMETERS,
            f"{label} parameter drift",
        )
        for parameter in signature.parameters.values():
            _assert(
                parameter.kind is inspect.Parameter.KEYWORD_ONLY,
                f"{label} parameter is not keyword-only: {parameter.name}",
            )

    session = framework.create_realtime_session()
    _assert(session.injected_stage_kinds == (), "no-stage injected kinds drift")
    _assert(
        dict(session.stage_diagnostics)
        == {
            "injected_stage_count": 0,
            "stage_close_count": 0,
            "stage_close_error_count": 0,
        },
        "no-stage diagnostics drift",
    )
    session.close()
    print("[OK] root-public, factory, and count-only stage diagnostics conform")


def check_stage_controls_and_runtime_regressions() -> None:
    control_a = _load_script(
        "smoke_v600_realtime_stage_protocols.py",
        "_rt6_3a_control_c_control_a",
    )
    for name in (
        "check_stable_package_shape",
        "check_context_and_envelope_contract",
        "check_protocol_signatures_and_provider_neutrality",
        "check_structural_fake_stages",
    ):
        print(f"[RUN] Control A::{name}")
        getattr(control_a, name)()

    control_b = _load_script(
        "smoke_v600_realtime_stage_injection.py",
        "_rt6_3a_control_c_control_b",
    )
    for name in (
        "check_source_and_import_safety",
        "check_factory_contract",
        "check_fake_stage_injection_and_mock_path",
        "check_validation_and_safe_close_failure",
        "check_docs",
        "check_public_smokes",
    ):
        print(f"[RUN] Control B::{name}")
        getattr(control_b, name)()

    terminal_callback = _load_script(
        "smoke_v600_realtime_generation_gate_terminal_callback_compatibility.py",
        "_rt6_3a_control_c_terminal_callback",
    )
    terminal_callback.check_terminal_callback_late_operations()
    terminal_callback.check_normal_post_turn_no_active_interrupt()

    concurrency = _load_script(
        "smoke_v600_realtime_terminal_registry_reentrant_concurrency.py",
        "_rt6_3a_control_c_concurrency",
    )
    concurrency.check_reentrant_terminal_callback_rejection()
    concurrency.check_same_turn_concurrent_run_is_one_group()
    concurrency.check_different_turn_groups_remain_serialized()
    concurrency.check_close_contract_is_preserved()

    event_close = _load_script(
        "smoke_v600_realtime_event_hub_close_hardening.py",
        "_rt6_3a_control_c_event_close",
    )
    event_close.check_close_seals_and_post_close_is_silent()
    event_close.check_reentrant_close_is_deferred()
    event_close.check_concurrent_operations_do_not_interleave()
    event_close.check_concurrent_close_waits_for_operation_boundary()
    print("[OK] Controls A/B and accepted generation/terminal/event behavior conform")


def check_aggregate_docs() -> None:
    required_markers = {
        PROJECT_ROOT / "README.md": (
            "FW-RT6-3a-C-STAGE-PROTOCOL-ACCEPTANCE:BEGIN",
            "FW-RT6-3a-C-STAGE-PROTOCOL-ACCEPTANCE:END",
        ),
        PROJECT_ROOT / "docs" / "v600_tasklist.md": (
            "FW-RT6-3a-C-ACCEPTANCE-SYNC:BEGIN",
            "FW-RT6-3a-C-ACCEPTANCE-SYNC:END",
        ),
        PROJECT_ROOT / "docs" / "v600_current_source_gap_inventory.md": (
            "FW-RT6-3a-C-GAP-RESOLUTION-SYNC:BEGIN",
            "FW-RT6-3a-C-GAP-RESOLUTION-SYNC:END",
        ),
    }
    for path, markers in required_markers.items():
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            _assert(marker in text, f"missing aggregate marker: {marker}")

    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(encoding="utf-8")
    for line in (
        "- [x] `VoiceInputStage` protocolを定義する。",
        "- [x] `TextGenerationStage` protocolを定義する。",
        "- [x] `VoiceOutputStage` protocolを定義する。",
        "- [x] `MotionStage` protocolを定義する。",
        "- [x] preflight/capability/start/cancel/close contractを統一する。",
        "- [x] stage result envelopeへcontextを追加する。",
        "- [x] provider-specific objectsをpublic protocolから除外する。",
    ):
        _assert(line in tasklist, f"tasklist acceptance line missing: {line}")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in required_markers)
    for phrase in (
        "Control A provider-neutral stage protocols: ACCEPTED",
        "Control B RealtimeSession stage injection: ACCEPTED",
        "runtime source changed: False",
        "stable public package: framework.realtime_stage",
        "stage protocol count: 4",
        "stage injection: provider-neutral",
        "fake stage injection: PASS",
        "factory parameters: 7 / KEYWORD-ONLY",
        "current run_turn injected stage starts: 0 / DEFERRED",
        "stage close exception exposure: False / COUNT-ONLY",
        "root-public names: 121 / UNCHANGED",
        "provider SDK root import: False",
        "real legacy adapter migration: UNRESOLVED / LATER CHECKPOINT",
        "real unified turn orchestration: UNRESOLVED",
        "next checkpoint: FW-RT6-3b",
        "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED",
    ):
        _assert(phrase in combined, f"aggregate documentation missing: {phrase}")
    print("[OK] README, tasklist, and gap inventory record truthful stage acceptance")


def check_manifest_and_version_gates() -> None:
    _run_script(
        "smoke_v600_public_api_manifest.py",
        (
            "v600_public_api_manifest_name_count: 121",
            "v600_realtime_stage_protocol_status: accepted",
            "v600_realtime_stage_protocol_package: framework.realtime_stage",
            "v600_realtime_stage_factory_parameters: 7 / keyword-only",
            "v600_realtime_stage_fake_injection: PASS",
            "v600_realtime_stage_run_turn_execution: False / deferred",
            "v600_next_checkpoint: FW-RT6-3b",
        ),
    )
    _run_script(
        "smoke_v600_version_metadata.py",
        (
            "v600_framework_source_version: 6.0.0.dev0",
            "v600_latest_published_release: 5.5.0",
            "v600_root_public_name_count: 121",
            "v600_realtime_stage_protocol_changed: protocols-and-provider-neutral-injection-accepted",
            "v600_realtime_session_factory_signature_changed: additive-stage-injection-keyword-only",
            "v600_next_checkpoint: FW-RT6-3b",
        ),
    )
    print("[OK] public manifest and frozen version metadata record FW-RT6-3a acceptance")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] Control C validation stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_source_contract()
    check_import_safety()
    check_public_compatibility()
    check_stage_controls_and_runtime_regressions()
    check_aggregate_docs()
    check_manifest_and_version_gates()
    check_import_safety()

    print("v600_rt6_3a_control_c_status: implemented-awaiting-review")
    print("v600_rt6_3a_control_c_exact_change_surface_count: 6")
    print("v600_rt6_3a_control_c_runtime_source_changed: False")
    print("v600_rt6_3a_control_c_controls_a_b: accepted")
    print("v600_rt6_3a_control_c_stable_public_package: framework.realtime_stage")
    print("v600_rt6_3a_control_c_stage_protocol_count: 4")
    print("v600_rt6_3a_control_c_common_methods: preflight/capability/start/cancel/close")
    print("v600_rt6_3a_control_c_stage_context: session/turn/generation")
    print("v600_rt6_3a_control_c_provider_specific_public_objects: False")
    print("v600_rt6_3a_control_c_factory_parameters: 7 / keyword-only")
    print("v600_rt6_3a_control_c_stage_injection: provider-neutral")
    print("v600_rt6_3a_control_c_fake_stage_injection: PASS")
    print("v600_rt6_3a_control_c_constructor_stage_calls: 0")
    print("v600_rt6_3a_control_c_run_turn_stage_starts: 0 / deferred")
    print("v600_rt6_3a_control_c_stage_close_once: True")
    print("v600_rt6_3a_control_c_close_exception_exposed: False")
    print("v600_rt6_3a_control_c_root_public_names: 121 / unchanged")
    print("v600_rt6_3a_control_c_provider_sdk_root_import: False")
    print("v600_rt6_3a_control_c_real_legacy_adapter_migration: unresolved")
    print("v600_rt6_3a_control_c_real_orchestration: False")
    print("v600_rt6_3a_control_c_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3a_control_c_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3a_control_c_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_3a_next_checkpoint: FW-RT6-3b")
    print("v600_rt6_3a_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-3a Control C aggregate stage-protocol acceptance conforms")


if __name__ == "__main__":
    main()
