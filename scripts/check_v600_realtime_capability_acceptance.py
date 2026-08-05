"""Aggregate FW-RT6-1d detailed capability snapshot acceptance checker.

Mock-safe: this checker performs no provider, network, microphone, playback,
VTube Studio, private-configuration, or host-application operation.
"""

from __future__ import annotations

import importlib
import inspect
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_CONTROL_C_COMMIT = "753748d463f800647b251c788d217a5c5adc4049"
EXPECTED_CONTROL_B_COMMIT = "30166d7e6fdf4291d7ecd475b988bfd1492ae7a3"
EXPECTED_CONTROL_A_COMMIT = "a27b3e17ff7d8158859a5a624e3b03225384bfc8"
EXPECTED_CONTROL_A_PARENT = "4709f0190f3779b83b8cb01a0cd67f6760ff8e35"

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_capability_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}

CONTROL_A_SUBJECT = "feat/test: add detailed realtime capability models"
CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_capability_contract.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime_capabilities.py",
    "framework/version.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_capability_models.py",
    "scripts/smoke_v600_version_metadata.py",
}

CONTROL_B_SUBJECT = "refactor/test: aggregate truthful global capabilities"
CONTROL_B_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v510_capability_snapshot_contract.md",
    "docs/v600_realtime_capability_contract.md",
    "framework/capabilities.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v510_capability_snapshot.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_capability_aggregation.py",
    "scripts/smoke_v600_version_metadata.py",
}

CONTROL_C_SUBJECT = "refactor/test: adopt session capability snapshot"
CONTROL_C_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_capability_contract.md",
    "framework/capabilities.py",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_capability_session_adoption.py",
}

TASK_LINES = (
    "- [x] `FrameworkCapabilities`のv5.1固定実装を置換する。",
    "- [x] session-scoped `RealtimeCapabilitySnapshot`を追加する。",
    "- [x] text generation capabilityを定義する。",
    "- [x] voice input capabilityを定義する。",
    "- [x] voice output capabilityを定義する。",
    "- [x] motion capabilityを定義する。",
    "- [x] configured/runtime_available/guardedを分離する。",
    "- [x] fake runtime/real runtimeを分離する。",
    "- [x] cooperative cancel/provider hard cancelを分離する。",
    "- [x] snapshot generation/scopeを追加する。",
    "- [x] v5 summary booleanをcompatibility fieldとして維持する。",
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


def _commit_subject(commit: str) -> str:
    return _git("show", "-s", "--format=%s", commit)


def _commit_parent(commit: str) -> str:
    return _git("rev-parse", f"{commit}^")


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines()
        if line.strip()
    }


def _assert_commit(commit: str, parent: str, subject: str, surface: set[str]) -> None:
    _assert(_commit_subject(commit) == subject, f"subject drift: {subject}")
    _assert(_commit_parent(commit) == parent, f"parent drift: {subject}")
    _assert(_commit_surface(commit) == surface, f"surface drift: {subject}")


def check_repository_contract() -> None:
    _assert(
        _git("rev-parse", "HEAD") == EXPECTED_CONTROL_C_COMMIT,
        "unexpected Control D baseline",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control D surface: {sorted(_changed_paths())}",
    )
    _assert_commit(
        EXPECTED_CONTROL_A_COMMIT,
        EXPECTED_CONTROL_A_PARENT,
        CONTROL_A_SUBJECT,
        CONTROL_A_SURFACE,
    )
    _assert_commit(
        EXPECTED_CONTROL_B_COMMIT,
        EXPECTED_CONTROL_A_COMMIT,
        CONTROL_B_SUBJECT,
        CONTROL_B_SURFACE,
    )
    _assert_commit(
        EXPECTED_CONTROL_C_COMMIT,
        EXPECTED_CONTROL_B_COMMIT,
        CONTROL_C_SUBJECT,
        CONTROL_C_SURFACE,
    )
    print("[OK] Control A/B/C history and exact Control D surface conform")


def check_public_manifest(framework: object) -> None:
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert(len(PUBLIC_API_NAMES) == len(set(PUBLIC_API_NAMES)), "duplicate public name")
    _assert(
        PUBLIC_API_NAMES[-7:]
        == (
            "CapabilitySnapshotScope",
            "RuntimeCapabilityState",
            "TextGenerationCapability",
            "RealtimeVoiceInputCapability",
            "RealtimeVoiceOutputCapability",
            "RealtimeMotionCapability",
            "RealtimeCapabilitySnapshot",
        ),
        "detailed capability public suffix drift",
    )
    print("[OK] canonical 121-name public manifest preserves the accepted prefix")


def check_model_contract(framework: object) -> None:
    state = framework.RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=False,
        fake_runtime=True,
        real_runtime=False,
        unavailable_reason=None,
    )
    _assert(state.usable is True, "usable state drift")
    _assert(isinstance(state.as_dict(), MappingProxyType), "state dict is mutable")

    for kwargs in (
        {"fake_runtime": True, "real_runtime": True, "runtime_available": True},
        {"fake_runtime": True, "runtime_available": False},
        {"real_runtime": True, "runtime_available": False},
    ):
        try:
            framework.RuntimeCapabilityState(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid runtime state accepted: {kwargs}")

    snapshot = framework.RealtimeCapabilitySnapshot(
        session_id=None,
        snapshot_scope=framework.CapabilitySnapshotScope.GLOBAL,
        snapshot_generation=1,
    )
    _assert(
        snapshot.snapshot_scope is framework.CapabilitySnapshotScope.GLOBAL,
        "scope drift",
    )
    _assert(snapshot.session_id is None, "global snapshot gained session")
    _assert(isinstance(snapshot.as_dict(), MappingProxyType), "snapshot dict is mutable")
    print("[OK] detailed capability state, scope, generation, and immutability conform")


def check_global_snapshot(framework: object) -> None:
    capabilities = framework.get_capabilities(real_tts_enabled=False)
    _assert(isinstance(capabilities, framework.FrameworkCapabilities), "return type drift")
    _assert(capabilities.schema_version == "v5.1.capabilities", "v5 schema drift")

    snapshot = capabilities.realtime_snapshot
    _assert(isinstance(snapshot, framework.RealtimeCapabilitySnapshot), "global snapshot missing")
    _assert(snapshot.schema_version == "v6.realtime_capabilities", "detailed schema drift")
    _assert(
        snapshot.snapshot_scope is framework.CapabilitySnapshotScope.GLOBAL,
        "global scope drift",
    )
    _assert(snapshot.snapshot_generation == 1, "global generation drift")
    _assert(snapshot.session_id is None, "global session identity drift")

    _assert(snapshot.text_generation.runtime.fake_runtime is True, "text fake runtime drift")
    _assert(snapshot.text_generation.runtime.runtime_available is True, "text runtime unavailable")
    _assert(snapshot.text_generation.streaming_supported is True, "global text streaming drift")
    _assert(
        snapshot.text_generation.cooperative_cancel_supported is True,
        "global cooperative cancel drift",
    )
    _assert(
        snapshot.text_generation.provider_hard_cancel_supported is False,
        "hard cancel overclaim",
    )

    _assert(snapshot.voice_input.runtime.fake_runtime is True, "voice-input fake runtime drift")
    _assert(snapshot.voice_input.final_transcript_supported is True, "final transcript support drift")
    _assert(snapshot.voice_input.partial_transcript_supported is False, "partial transcript overclaim")
    _assert(snapshot.voice_input.audio_chunk_input_supported is False, "audio chunk overclaim")

    _assert(snapshot.voice_output.runtime.configured is False, "disabled voice output configured")
    _assert(snapshot.voice_output.runtime.runtime_available is False, "voice output overclaim")
    _assert(snapshot.voice_output.runtime.real_runtime is False, "voice output real overclaim")
    _assert(
        snapshot.voice_output.runtime.unavailable_reason == "real_tts_disabled",
        "voice output reason drift",
    )
    _assert(snapshot.voice_output.provider_hard_cancel_supported is False, "voice hard cancel overclaim")
    _assert(snapshot.voice_output.pending_flush_supported is False, "flush overclaim")

    _assert(snapshot.motion.runtime.fake_runtime is True, "global motion fake runtime drift")
    _assert(snapshot.motion.runtime.runtime_available is True, "global motion unavailable")
    _assert(snapshot.motion.completion_event_supported is True, "motion completion drift")
    _assert(snapshot.motion.provider_neutral_intent_supported is True, "motion intent drift")

    _assert(snapshot.supports_text_chat is True, "text summary drift")
    _assert(snapshot.supports_voice_input is True, "voice-input summary drift")
    _assert(snapshot.supports_voice_output is True, "voice-output summary drift")
    _assert(snapshot.supports_motion is True, "motion summary drift")
    _assert(snapshot.real_runtime_enabled is False, "global real runtime overclaim")
    _assert(snapshot.hard_cancel_supported is False, "global hard cancel overclaim")
    _assert(snapshot.tts_queue_flush_supported is False, "global queue flush overclaim")
    print("[OK] truthful global compatibility and detailed capability snapshots conform")


def check_session_snapshot(framework: object) -> None:
    signature = inspect.signature(framework.create_realtime_session)
    _assert(
        tuple(signature.parameters)
        == ("project_root", "public_metadata", "real_runtime_enabled"),
        "realtime factory parameter drift",
    )
    _assert(
        all(
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
            for parameter in signature.parameters.values()
        ),
        "realtime factory is no longer keyword-only",
    )

    session = framework.create_realtime_session(real_runtime_enabled=True)
    first = session.capabilities
    second = session.capabilities
    info = session.info

    _assert(first is second, "session snapshot is not lifetime-stable")
    _assert(
        first.snapshot_scope is framework.CapabilitySnapshotScope.SESSION,
        "session scope drift",
    )
    _assert(first.snapshot_generation == 1, "session generation drift")
    _assert(first.session_id == info.session_id, "session identity mismatch")
    _assert(first.supports_text_chat is True, "session text summary drift")
    _assert(first.supports_voice_input is True, "session voice-input summary drift")
    _assert(first.supports_voice_output is True, "session voice-output summary drift")
    _assert(first.supports_motion is False, "session motion wiring overclaim")
    _assert(first.real_runtime_enabled is False, "request became availability")
    _assert(info.real_runtime_enabled is False, "session info real-runtime overclaim")
    _assert(first.public_metadata["real_runtime_requested"] is True, "request intent missing")
    _assert(first.public_metadata["real_runtime_available"] is False, "availability overclaim")
    _assert(first.motion.runtime.runtime_available is False, "session motion overclaim")
    _assert(
        first.motion.runtime.unavailable_reason == "not_wired_to_realtime_session",
        "session motion reason drift",
    )
    _assert(first.text_generation.streaming_supported is False, "session streaming overclaim")
    _assert(
        first.text_generation.cooperative_cancel_supported is False,
        "session cancel overclaim",
    )
    _assert(first.voice_input.final_transcript_supported is True, "session final transcript drift")
    _assert(first.voice_input.partial_transcript_supported is False, "session partial overclaim")
    _assert(first.voice_output.pending_flush_supported is False, "session flush overclaim")
    _assert(first.hard_cancel_supported is False, "session hard cancel overclaim")
    _assert(first.tts_queue_flush_supported is False, "session queue flush overclaim")
    session.close()
    _assert(session.capabilities is first, "snapshot changed after close")
    print("[OK] session-scoped identity, lifetime stability, and stage facts conform")


def check_docs() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(encoding="utf-8")
    inventory = (
        PROJECT_ROOT / "docs" / "v600_current_source_gap_inventory.md"
    ).read_text(encoding="utf-8")

    _assert("FW-RT6-1d-D-CAPABILITY-ACCEPTANCE:BEGIN" in readme, "README acceptance missing")
    _assert("FW-RT6-1d-D-ACCEPTANCE-SYNC:BEGIN" in tasklist, "tasklist acceptance missing")
    _assert("FW-RT6-1d-D-GAP-RESOLUTION-SYNC:BEGIN" in inventory, "gap sync missing")
    for line in TASK_LINES:
        _assert(line in tasklist, f"task not accepted: {line}")
    for phrase in (
        "voice input current status accurate: True",
        "realtime current status accurate: True",
        "motion current status accurate: True",
        "unsupported overclaim: False",
        "next checkpoint: FW-RT6-2a",
    ):
        _assert(phrase in readme, f"README phrase missing: {phrase}")
        _assert(phrase in tasklist, f"tasklist phrase missing: {phrase}")
    _assert(
        "G-06 stale global capability summary: RESOLVED" in inventory,
        "G-06 resolution missing",
    )
    _assert(
        "G-07 normal real STT session composition: UNRESOLVED" in inventory,
        "G-07 deferral missing",
    )
    manifest_smoke = (
        PROJECT_ROOT / "scripts" / "smoke_v600_public_api_manifest.py"
    ).read_text(encoding="utf-8")
    version_smoke = (
        PROJECT_ROOT / "scripts" / "smoke_v600_version_metadata.py"
    ).read_text(encoding="utf-8")
    for phrase in (
        'print("v600_public_api_manifest_status: accepted")',
        'print("v600_next_checkpoint: FW-RT6-2a")',
    ):
        _assert(
            phrase in manifest_smoke,
            f"public manifest diagnostic drift: {phrase}",
        )
    for phrase in (
        'print("v600_version_metadata_status: accepted")',
        'print("v600_capability_truthfulness_changed: global-builder-and-session-adoption-accepted")',
        'print("v600_next_checkpoint: FW-RT6-2a")',
    ):
        _assert(
            phrase in version_smoke,
            f"version diagnostic drift: {phrase}",
        )

    print("[OK] README, tasklist, gap inventory, and general diagnostics record truthful acceptance")


def check_import_safety() -> None:
    loaded = tuple(sys.modules)
    forbidden = sorted(
        name
        for name in loaded
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] aggregate capability acceptance stayed provider/runtime import-safe")


def main() -> None:
    check_repository_contract()
    framework = importlib.import_module("framework")
    check_import_safety()
    check_public_manifest(framework)
    check_model_contract(framework)
    check_global_snapshot(framework)
    check_session_snapshot(framework)
    check_docs()
    check_import_safety()

    print("v600_realtime_capability_acceptance_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 6")
    print("v600_root_public_name_count: 121")
    print("v600_v5_capability_schema_preserved: True")
    print("v600_detailed_capability_schema: v6.realtime_capabilities")
    print("v600_global_detailed_snapshot_accepted: True")
    print("v600_session_scoped_snapshot_accepted: True")
    print("v600_snapshot_scope_generation_accepted: True")
    print("v600_configured_runtime_guarded_separated: True")
    print("v600_fake_real_runtime_separated: True")
    print("v600_cooperative_hard_cancel_separated: True")
    print("v600_voice_input_current_status_accurate: True")
    print("v600_realtime_current_status_accurate: True")
    print("v600_motion_current_status_accurate: True")
    print("v600_unsupported_overclaim: False")
    print("v600_real_unified_runtime: False")
    print("v600_motion_wired_into_realtime_session: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_checkpoint: FW-RT6-2a")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-1d detailed capability snapshot aggregate acceptance passed")


if __name__ == "__main__":
    main()
