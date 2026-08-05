"""FW-RT6-1d Control B truthful global capability aggregation smoke.

Mock-safe: validates the accepted Control A history, exact Control B surface,
v5.1 compatibility fields, the additive detailed global snapshot, truthful
mock/real separation, and explicit non-adoption of session-scoped wiring.
"""

from __future__ import annotations

import dataclasses
import inspect
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "a27b3e17ff7d8158859a5a624e3b03225384bfc8"
EXPECTED_PARENT_HEAD = "4709f0190f3779b83b8cb01a0cd67f6760ff8e35"
EXPECTED_CONTROL_A_SUBJECT = "feat/test: add detailed realtime capability models"
EXPECTED_SURFACE = {
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
FORBIDDEN_IMPORTS = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
    "tts.voice_engine",
    "live2d.vts_client",
}


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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control B baseline")
    _assert(_git("rev-parse", f"{EXPECTED_BASELINE_HEAD}^") == EXPECTED_PARENT_HEAD, "Control A parent drift")
    _assert(_git("show", "-s", "--format=%s", EXPECTED_BASELINE_HEAD) == EXPECTED_CONTROL_A_SUBJECT, "Control A subject drift")
    control_a_surface = {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", EXPECTED_BASELINE_HEAD
        ).splitlines()
        if line.strip()
    }
    _assert(control_a_surface == CONTROL_A_SURFACE, "Control A surface drift")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control B surface: {sorted(_changed_paths())}")
    print("[OK] accepted Control A history and exact ten-file Control B surface conform")


def check_compatibility_surface() -> None:
    import framework
    from framework.version import CAPABILITIES_SCHEMA_VERSION

    _assert(len(framework.__all__) == 121, "root-public count changed")
    _assert(CAPABILITIES_SCHEMA_VERSION == "v5.1.capabilities", "v5.1 schema changed")
    signature = inspect.signature(framework.get_capabilities)
    _assert(tuple(signature.parameters) == ("project_root", "real_tts_enabled"), "get_capabilities signature drift")
    _assert(all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in signature.parameters.values()), "signature should remain keyword-only")
    snapshot = framework.get_capabilities()
    _assert(isinstance(snapshot, framework.FrameworkCapabilities), "return type drift")
    _assert(dataclasses.is_dataclass(snapshot), "FrameworkCapabilities must remain dataclass")
    _assert(snapshot.schema_version == "v5.1.capabilities", "compatibility schema drift")
    for name in ("text_chat", "voice_output", "voice_input", "realtime", "motion"):
        _assert(isinstance(getattr(snapshot, name), framework.CapabilityStatus), f"{name} compatibility field drift")
    print("[OK] v5.1 return type, schema, signature, and summary fields are preserved")


def check_truthful_global_snapshot() -> None:
    import framework

    capabilities = framework.get_capabilities()
    detailed = capabilities.realtime_snapshot
    _assert(isinstance(detailed, framework.RealtimeCapabilitySnapshot), "detailed global snapshot missing")
    _assert(detailed.snapshot_scope is framework.CapabilitySnapshotScope.GLOBAL, "global scope drift")
    _assert(detailed.session_id is None, "global snapshot must not claim session identity")
    _assert(detailed.snapshot_generation == 1, "global generation drift")

    expected = {
        "voice_input": "mock_voice_input_available",
        "realtime": "mock_realtime_available",
        "motion": "mock_motion_available",
    }
    for name, reason in expected.items():
        summary = getattr(capabilities, name)
        _assert(summary.supported and summary.configured and summary.available, f"{name} mock boundary should be usable")
        _assert(summary.status == "fallback", f"{name} should identify fallback")
        _assert(summary.reason_code == reason, f"{name} reason drift")

    _assert(detailed.text_generation.runtime.fake_runtime, "text fake runtime not identified")
    _assert(detailed.voice_input.runtime.fake_runtime, "voice-input fake runtime not identified")
    _assert(detailed.motion.runtime.fake_runtime, "motion fake runtime not identified")
    _assert(not detailed.voice_output.runtime.usable, "voice output usability overclaim")
    _assert(detailed.text_generation.streaming_supported, "text streaming support underclaim")
    _assert(detailed.text_generation.cooperative_cancel_supported, "text cooperative cancel underclaim")
    _assert(not detailed.text_generation.provider_hard_cancel_supported, "hard cancel overclaim")
    _assert(not detailed.voice_input.audio_chunk_input_supported, "audio chunk input overclaim")
    _assert(not detailed.voice_input.partial_transcript_supported, "partial transcript overclaim")
    _assert(detailed.voice_input.final_transcript_supported, "final transcript boundary underclaim")
    _assert(not detailed.voice_output.pending_flush_supported, "pending flush overclaim")
    _assert(not detailed.voice_output.active_audio_invalidation_supported, "audio invalidation overclaim")
    _assert(detailed.motion.completion_event_supported, "motion completion event underclaim")
    _assert(detailed.motion.provider_neutral_intent_supported, "motion intent underclaim")
    _assert(not detailed.motion.request_cancel_supported, "motion cancel overclaim")
    _assert(not detailed.real_runtime_enabled, "real unified runtime overclaim")
    _assert(not detailed.hard_cancel_supported, "aggregate hard cancel overclaim")
    _assert(not detailed.tts_queue_flush_supported, "aggregate queue flush overclaim")
    print("[OK] global public boundaries and detailed stage capability facts are truthful")


def check_non_adoption_and_import_safety() -> None:
    from framework.realtime_session import RealtimeSession

    _assert(not hasattr(RealtimeSession, "capabilities"), "session snapshot adoption must remain Control C")
    _assert(not hasattr(RealtimeSession, "get_capabilities"), "session snapshot builder must remain Control C")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider/runtime import occurred")
    print("[OK] Control B remains global-only and provider/runtime execution safe")


def check_docs() -> None:
    files = (
        "docs/v510_capability_snapshot_contract.md",
        "docs/v600_realtime_capability_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    )
    required = (
        "FW-RT6-1d Control B",
        "a27b3e17ff7d8158859a5a624e3b03225384bfc8",
        "v5.1.capabilities",
        "v6.realtime_capabilities",
        "mock_realtime_available",
        "RealtimeSession snapshot adoption: False",
        "provider/network/microphone/playback/VTS execution: False",
    )
    for rel in files:
        text = (PROJECT_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        for phrase in required:
            _assert(phrase in text, f"{rel} missing {phrase}")
    print("[OK] compatibility and host-app docs record truthful Control B scope")


def main() -> None:
    check_repository_contract()
    check_compatibility_surface()
    check_truthful_global_snapshot()
    check_non_adoption_and_import_safety()
    check_docs()
    print("v600_rt6_1d_control_b_status: implemented-awaiting-review")
    print("v600_rt6_1d_control_b_exact_change_surface: True")
    print("v600_rt6_1d_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_1d_control_b_v5_schema_preserved: True")
    print("v600_rt6_1d_control_b_global_detailed_snapshot: True")
    print("v600_rt6_1d_control_b_voice_input_public_boundary_missing: False")
    print("v600_rt6_1d_control_b_realtime_public_boundary_missing: False")
    print("v600_rt6_1d_control_b_motion_public_boundary_missing: False")
    print("v600_rt6_1d_control_b_realtime_session_adopted: False")
    print("v600_rt6_1d_control_b_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_1d_control_b_aggregation: OK")


if __name__ == "__main__":
    main()
