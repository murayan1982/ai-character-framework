"""FW-RT6-1d Control A detailed realtime capability model smoke.

Offline-safe: validates the additive public model vocabulary, truthful runtime
state separation, detailed stage fields, snapshot scope/generation, v5 summary
compatibility fields, central schema metadata, and explicit non-adoption limits.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "4709f0190f3779b83b8cb01a0cd67f6760ff8e35"
EXPECTED_SURFACE = {
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
EXPECTED_ACCEPTED_PREFIX_HASH = (
    "70210be24c38dc62c3b634e2f68e0c77ff3d2667822f0ab505e0bfe0db323c82"
)
CAPABILITY_PUBLIC_NAMES = (
    "CapabilitySnapshotScope",
    "RuntimeCapabilityState",
    "TextGenerationCapability",
    "RealtimeVoiceInputCapability",
    "RealtimeVoiceOutputCapability",
    "RealtimeMotionCapability",
    "RealtimeCapabilitySnapshot",
)
FORBIDDEN_IMPORTS = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "speech_recognition",
    "pyaudio",
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


def _expect_failure(callable_, expected: type[BaseException]) -> None:
    try:
        callable_()
    except expected:
        return
    raise AssertionError(f"expected {expected.__name__}")


def check_repository_contract() -> None:
    _assert(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected Control A baseline",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] Control A baseline and exact eleven-file surface match")


def check_public_manifest() -> None:
    import framework
    from framework.public_api import (
        PUBLIC_API_NAMES,
        REALTIME_CAPABILITY_PUBLIC_EXPORTS,
    )

    prefix_hash = hashlib.sha256(
        "\n".join(PUBLIC_API_NAMES[:114]).encode("utf-8")
    ).hexdigest()
    _assert(prefix_hash == EXPECTED_ACCEPTED_PREFIX_HASH, "accepted 114-name prefix drift")
    _assert(
        tuple(REALTIME_CAPABILITY_PUBLIC_EXPORTS) == CAPABILITY_PUBLIC_NAMES,
        "detailed capability public group drift",
    )
    _assert(
        PUBLIC_API_NAMES[114:] == CAPABILITY_PUBLIC_NAMES,
        "detailed capability names must be appended",
    )
    _assert(len(PUBLIC_API_NAMES) == 121, "canonical root-public total must be 121")
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    for name in CAPABILITY_PUBLIC_NAMES:
        _assert(getattr(framework, name) is not None, f"missing root-public name: {name}")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider/runtime import occurred")
    print("[OK] accepted 114-name prefix is preserved and seven capability names are appended")


def check_runtime_state() -> None:
    from framework import RuntimeCapabilityState

    state = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=False,
        fake_runtime=True,
        real_runtime=False,
        unavailable_reason=None,
        public_metadata={"boundary": "fake"},
    )
    _assert(dataclasses.is_dataclass(state), "runtime state must be dataclass")
    _assert(state.__dataclass_params__.frozen, "runtime state must be frozen")
    _assert(state.usable, "configured available unguarded runtime should be usable")
    _assert(isinstance(state.as_dict(), MappingProxyType), "state mapping must be immutable")
    _assert(state.as_dict()["fake_runtime"] is True, "fake runtime flag drift")

    guarded = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=True,
        real_runtime=True,
        unavailable_reason="provider_execution_guarded",
    )
    _assert(not guarded.usable, "guarded runtime must not be usable")
    _expect_failure(
        lambda: RuntimeCapabilityState(
            runtime_available=True,
            fake_runtime=True,
            real_runtime=True,
        ),
        ValueError,
    )
    _expect_failure(
        lambda: RuntimeCapabilityState(fake_runtime=True),
        ValueError,
    )
    print("[OK] configured/runtime/guard/fake/real state is truthful and validated")


def check_stage_models() -> None:
    from framework import (
        RealtimeMotionCapability,
        RealtimeVoiceInputCapability,
        RealtimeVoiceOutputCapability,
        RuntimeCapabilityState,
        TextGenerationCapability,
    )

    fake = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        fake_runtime=True,
        unavailable_reason=None,
    )
    real_guarded = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        guarded=True,
        real_runtime=True,
        unavailable_reason="execution_guarded",
    )
    text = TextGenerationCapability(
        runtime=fake,
        streaming_supported=True,
        cooperative_cancel_supported=True,
        provider_hard_cancel_supported=False,
    )
    voice_input = RealtimeVoiceInputCapability(
        runtime=real_guarded,
        audio_chunk_input_supported=False,
        partial_transcript_supported=False,
        final_transcript_supported=True,
        input_abort_supported=False,
        backpressure_supported=False,
        accepted_audio_formats=("WAV", "pcm16", "wav"),
        maximum_chunk_size=4096,
        maximum_duration=30,
    )
    voice_output = RealtimeVoiceOutputCapability(
        runtime=real_guarded,
        streaming_audio_supported=False,
        generation_cancel_supported=False,
        provider_hard_cancel_supported=False,
        pending_flush_supported=False,
        active_audio_invalidation_supported=False,
        audio_formats=("MP3",),
        maximum_text_size=1000,
    )
    motion = RealtimeMotionCapability(
        runtime=fake,
        request_cancel_supported=False,
        completion_event_supported=True,
        provider_neutral_intent_supported=True,
    )

    for value in (text, voice_input, voice_output, motion):
        _assert(dataclasses.is_dataclass(value), "stage capability must be dataclass")
        _assert(value.__dataclass_params__.frozen, "stage capability must be frozen")
        mapping = value.as_dict()
        _assert(isinstance(mapping, MappingProxyType), "stage mapping must be immutable")
        json.dumps(dict(mapping))

    _assert(
        voice_input.accepted_audio_formats == ("wav", "pcm16"),
        "accepted audio formats should normalize and de-duplicate",
    )
    _assert(voice_input.maximum_duration == 30.0, "duration normalization drift")
    _assert(voice_output.audio_formats == ("mp3",), "audio format normalization drift")
    _assert(text.cooperative_cancel_supported, "cooperative cancel field drift")
    _assert(not text.provider_hard_cancel_supported, "hard cancel overclaim")
    _expect_failure(
        lambda: RealtimeVoiceInputCapability(maximum_chunk_size=0),
        ValueError,
    )
    _expect_failure(
        lambda: RealtimeVoiceOutputCapability(maximum_text_size=True),
        TypeError,
    )
    print("[OK] text, voice-input, voice-output, and motion detail models conform")


def check_snapshot() -> None:
    from framework import (
        CapabilitySnapshotScope,
        RealtimeCapabilitySnapshot,
        RealtimeMotionCapability,
        RealtimeVoiceInputCapability,
        RealtimeVoiceOutputCapability,
        RuntimeCapabilityState,
        SessionId,
        TextGenerationCapability,
    )
    from framework.version import (
        CAPABILITIES_SCHEMA_VERSION,
        REALTIME_CAPABILITIES_SCHEMA_VERSION,
    )

    fake = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        fake_runtime=True,
        unavailable_reason=None,
    )
    snapshot = RealtimeCapabilitySnapshot(
        session_id=SessionId.new(),
        snapshot_scope="session",
        snapshot_generation=2,
        text_generation=TextGenerationCapability(
            runtime=fake,
            streaming_supported=True,
            cooperative_cancel_supported=True,
        ),
        voice_input=RealtimeVoiceInputCapability(
            runtime=fake,
            final_transcript_supported=True,
        ),
        voice_output=RealtimeVoiceOutputCapability(runtime=fake),
        motion=RealtimeMotionCapability(
            runtime=fake,
            completion_event_supported=True,
            provider_neutral_intent_supported=True,
        ),
        supports_text_chat=True,
        supports_voice_input=True,
        supports_voice_output=True,
        supports_motion=True,
        real_runtime_enabled=False,
        hard_cancel_supported=False,
        tts_queue_flush_supported=False,
    )
    _assert(snapshot.snapshot_scope is CapabilitySnapshotScope.SESSION, "scope normalization drift")
    _assert(snapshot.snapshot_generation == 2, "snapshot generation drift")
    _assert(snapshot.schema_version == "v6.realtime_capabilities", "v6 schema drift")
    _assert(
        REALTIME_CAPABILITIES_SCHEMA_VERSION == "v6.realtime_capabilities",
        "central v6 schema constant drift",
    )
    _assert(
        CAPABILITIES_SCHEMA_VERSION == "v5.1.capabilities",
        "frozen v5 schema must remain unchanged",
    )
    _assert(snapshot.supports_text_chat, "v5 summary compatibility field drift")
    _assert(not snapshot.hard_cancel_supported, "hard cancel summary overclaim")
    mapping = snapshot.as_dict()
    _assert(isinstance(mapping, MappingProxyType), "snapshot mapping must be immutable")
    json.dumps(dict(mapping))

    global_snapshot = RealtimeCapabilitySnapshot(
        session_id=None,
        snapshot_scope=CapabilitySnapshotScope.GLOBAL,
    )
    _assert(global_snapshot.session_id is None, "global snapshot session ID drift")
    _expect_failure(lambda: RealtimeCapabilitySnapshot(session_id=None), ValueError)
    _expect_failure(
        lambda: RealtimeCapabilitySnapshot(
            session_id=SessionId.new(),
            snapshot_generation=0,
        ),
        ValueError,
    )
    print("[OK] snapshot scope, generation, session identity, schema, and v5 summaries conform")


def check_non_adoption_and_import_safety() -> None:
    import framework
    from framework.capabilities import get_capabilities

    _assert(
        get_capabilities().schema_version == "v5.1.capabilities",
        "Control A must not replace FrameworkCapabilities yet",
    )
    realtime_session_source = (
        PROJECT_ROOT / "framework" / "realtime_session.py"
    ).read_text(encoding="utf-8")
    _assert(
        "RealtimeCapabilitySnapshot" not in realtime_session_source,
        "Control A must not adopt snapshot in RealtimeSession",
    )
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "forbidden provider/runtime import")

    code = r"""
import sys
import framework
forbidden = {
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "speech_recognition", "pyaudio", "tts.voice_engine", "live2d.vts_client",
}
loaded = sorted(forbidden & set(sys.modules))
if loaded:
    raise AssertionError(loaded)
print("capability-import-safe")
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(completed.returncode == 0, completed.stdout + completed.stderr)
    _assert("capability-import-safe" in completed.stdout, "import safety subprocess failed")
    print("[OK] Control A remains model-only and provider/runtime import-safe")


def check_docs() -> None:
    for relative_path in (
        "docs/v600_realtime_capability_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-1d-A-DETAILED-CAPABILITY-MODELS:BEGIN" in text,
            f"missing Control A begin marker: {relative_path}",
        )
        _assert(
            "FW-RT6-1d-A-DETAILED-CAPABILITY-MODELS:END" in text,
            f"missing Control A end marker: {relative_path}",
        )
    print("[OK] capability contract and host-app docs record truthful Control A scope")


def main() -> None:
    check_repository_contract()
    check_public_manifest()
    check_runtime_state()
    check_stage_models()
    check_snapshot()
    check_non_adoption_and_import_safety()
    check_docs()

    print("v600_rt6_1d_control_a_status: implemented-awaiting-review")
    print("v600_rt6_1d_control_a_exact_change_surface: True")
    print("v600_rt6_1d_control_a_root_public_names: 121")
    print("v600_rt6_1d_control_a_accepted_prefix: 114 / unchanged")
    print("v600_rt6_1d_control_a_detailed_capability_models: 7")
    print("v600_rt6_1d_control_a_v5_schema_preserved: True")
    print("v600_rt6_1d_control_a_framework_capabilities_replaced: False")
    print("v600_rt6_1d_control_a_realtime_session_adopted: False")
    print("v600_rt6_1d_control_a_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_1d_control_a_models: OK")


if __name__ == "__main__":
    main()
