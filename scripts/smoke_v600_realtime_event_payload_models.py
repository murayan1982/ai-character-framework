"""FW-RT6-1c Control A typed realtime event payload model smoke.

Offline-safe: validates the exact additive public surface, immutable payload
models, public serialization, provider-safe validation, and non-adoption
boundaries without provider, network, microphone, playback, or motion runtime
execution.
"""

from __future__ import annotations

import dataclasses
import json
import subprocess
import sys
from pathlib import Path
from types import MappingProxyType
from typing import get_args

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "285e546d7065eee24d144a4fc39da82d3097bd1f"
EXPECTED_SURFACE = {
    "framework/realtime_event_payloads.py",
    "framework/public_api.py",
    "framework/__init__.py",
    "scripts/smoke_v600_realtime_event_payload_models.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
    "scripts/smoke_app_sdk.py",
    "docs/v600_realtime_event_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
PREVIOUS_PUBLIC_API_NAMES = ('OpenAIVoiceInputClient', 'OpenAIVoiceInputClientFactory', 'OpenAIVoiceInputPreflight', 'OpenAIVoiceInputPreflightStatus', 'OpenAIVoiceInputProviderAdapter', 'OpenAIVoiceInputFakeClientMarker', 'OpenAIVoiceInputFakeExecutionPolicy', 'OpenAIVoiceInputFakeExecutionStatus', 'OpenAIVoiceInputFakeExecutor', 'OpenAIVoiceInputPrivateCredential', 'OpenAIVoiceInputRealClientFactory', 'OpenAIVoiceInputRealProviderExecutor', 'OpenAIVoiceInputRealProviderPolicy', 'OpenAIVoiceInputRealProviderStatus', 'OpenAIVoiceInputRuntimeMode', 'VoiceInputProviderExecutionConfig', 'resolve_voice_input_provider_execution_config', 'get_voice_input_provider_execution_status', 'GuardedRealVoiceInputProviderAdapter', 'VoiceInputProviderAdapterInfo', 'VoiceInputProviderAdapter', 'FakeVoiceInputProviderAdapter', 'VoiceInputAudioSourceKind', 'VoiceInputAudioSource', 'VoiceInputAudioRef', 'VoiceInputAudioFormat', 'VoiceInputAudioEncoding', 'FacadeConfigError', 'FacadeError', 'FacadeProviderError', 'TextChatSession', 'TextChatSessionEvent', 'TextChatSessionInfo', 'TextChatStateChange', 'VoiceOutputRequest', 'VoiceArtifactRef', 'VoiceOutputResult', 'VoiceOutputSession', 'VoiceOutputSessionInfo', 'VoiceSynthesisRequest', 'VoiceSynthesisResult', 'create_text_chat_session', 'create_voice_output_session', 'TextChatResult', 'CapabilityStatus', 'FrameworkCapabilities', 'get_capabilities', 'VoiceInputErrorCode', 'VoiceInputOutcome', 'VoiceInputRequest', 'VoiceInputResult', 'VoiceInputSession', 'VoiceInputSessionInfo', 'create_voice_input_session', 'VoiceInputCapabilities', 'VoiceInputProviderConfig', 'VoiceInputProviderStatus', 'get_voice_input_capabilities', 'resolve_voice_input_provider_config', 'RealtimeErrorCode', 'RealtimeEvent', 'RealtimeEventType', 'RealtimeState', 'RealtimeTurn', 'RealtimeTurnResult', 'RealtimeSession', 'RealtimeSessionInfo', 'create_realtime_session', 'BargeInDecision', 'BargeInPolicy', 'BargeInPolicyMode', 'InterruptOutcome', 'InterruptReason', 'InterruptRequest', 'InterruptResult', 'InterruptScope', 'OutputFlushOutcome', 'OutputFlushRequest', 'OutputFlushResult', 'TTSQueueState', 'MotionAdapterStatus', 'MotionCapability', 'MotionErrorCode', 'MotionEventType', 'MotionIntent', 'MotionOutcome', 'MotionRequest', 'MotionResult', 'MotionState', 'MotionSession', 'MotionSessionInfo', 'create_motion_session', 'MotionAdapterExecutionConfig', 'get_motion_adapter_execution_capability', 'resolve_motion_adapter_execution_config', 'SessionId', 'TurnId', 'GenerationId', 'EventSequence', 'RealtimePhase', 'TurnOutcome', 'RecoveryAction', 'LifecycleTransitionErrorCode', 'LifecycleTransitionError')
PAYLOAD_PUBLIC_NAMES = (
    "RealtimeEventPayloadKind",
    "LifecycleEventPayload",
    "TranscriptEventPayload",
    "ResponseEventPayload",
    "SynthesisEventPayload",
    "AudioEventPayload",
    "MotionEventPayload",
    "InterruptEventPayload",
    "DiagnosticEventPayload",
    "RealtimeEventPayload",
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
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control A baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control A surface: {sorted(_changed_paths())}")
    print("[OK] Control A baseline and exact ten-file surface match")


def check_root_public_manifest() -> None:
    import framework
    from framework.public_api import (
        PUBLIC_API_NAMES,
        REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS,
    )

    _assert(PUBLIC_API_NAMES[:104] == PREVIOUS_PUBLIC_API_NAMES, "accepted 104-name prefix/order drift")
    _assert(tuple(REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS) == PAYLOAD_PUBLIC_NAMES, "payload public group drift")
    _assert(PUBLIC_API_NAMES[104:] == PAYLOAD_PUBLIC_NAMES, "payload names must be appended")
    _assert(len(PUBLIC_API_NAMES) == 114, "canonical root-public total must be 114")
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    for name in PAYLOAD_PUBLIC_NAMES:
        _assert(getattr(framework, name) is not None, f"missing root-public payload name: {name}")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider SDK imported by payload surface")
    print("[OK] accepted 104-name prefix is preserved and ten payload names are appended")


def check_payload_kinds_and_union() -> None:
    from framework import (
        AudioEventPayload,
        DiagnosticEventPayload,
        InterruptEventPayload,
        LifecycleEventPayload,
        MotionEventPayload,
        RealtimeEventPayload,
        RealtimeEventPayloadKind,
        ResponseEventPayload,
        SynthesisEventPayload,
        TranscriptEventPayload,
    )

    _assert(
        tuple(value.value for value in RealtimeEventPayloadKind)
        == ("lifecycle", "transcript", "response", "synthesis", "audio", "motion", "interrupt", "diagnostic"),
        "payload kind value/order drift",
    )
    _assert(
        set(get_args(RealtimeEventPayload))
        == {
            LifecycleEventPayload,
            TranscriptEventPayload,
            ResponseEventPayload,
            SynthesisEventPayload,
            AudioEventPayload,
            MotionEventPayload,
            InterruptEventPayload,
            DiagnosticEventPayload,
        },
        "RealtimeEventPayload union drift",
    )
    _assert(json.loads(json.dumps(RealtimeEventPayloadKind.AUDIO)) == "audio", "payload kind JSON drift")
    print("[OK] payload discriminator and typed union are stable JSON-safe contracts")


def check_payload_models() -> None:
    from framework import (
        AudioEventPayload,
        DiagnosticEventPayload,
        EventSequence,
        InterruptEventPayload,
        InterruptOutcome,
        InterruptScope,
        LifecycleEventPayload,
        MotionEventPayload,
        MotionOutcome,
        RecoveryAction,
        ResponseEventPayload,
        SynthesisEventPayload,
        TranscriptEventPayload,
        TurnOutcome,
    )

    payloads = (
        LifecycleEventPayload(
            outcome="completed",
            recovery_action="none",
            reason="normal completion",
        ),
        TranscriptEventPayload(text="hello", is_final=True, confidence=0.75),
        ResponseEventPayload(text="delta", delta_index=0, is_final=False),
        SynthesisEventPayload(request_state="generated", audio_format="wav"),
        AudioEventPayload(artifact_ref="fw_audio_001", available=True),
        MotionEventPayload(request_id="motion-001", outcome="completed"),
        InterruptEventPayload(scope="current_turn", outcome="accepted", reason="host request"),
        DiagnosticEventPayload(
            code="stale_result_dropped",
            drop_reason="generation_mismatch",
            dropped_sequence=1,
            overflow_count=0,
        ),
    )
    for payload in payloads:
        _assert(dataclasses.is_dataclass(payload), "payload must be a dataclass")
        _assert(payload.__dataclass_params__.frozen, "payload must be frozen")
        mapping = payload.as_dict()
        _assert(isinstance(mapping, MappingProxyType), "payload mapping must be immutable")
        json.dumps(dict(mapping))

    lifecycle, transcript, response, synthesis, audio, motion, interrupt, diagnostic = payloads
    _assert(lifecycle.outcome is TurnOutcome.COMPLETED, "lifecycle outcome normalization drift")
    _assert(lifecycle.recovery_action is RecoveryAction.NONE, "lifecycle recovery normalization drift")
    _assert(transcript.is_final and transcript.confidence == 0.75, "transcript payload drift")
    _assert(response.delta_index == 0 and not response.is_final, "response payload drift")
    _assert(synthesis.audio_format == "wav", "synthesis payload drift")
    _assert(audio.available and audio.artifact_ref == "fw_audio_001", "audio payload drift")
    _assert(motion.outcome is MotionOutcome.COMPLETED, "motion outcome normalization drift")
    _assert(interrupt.scope is InterruptScope.CURRENT_TURN, "interrupt scope normalization drift")
    _assert(interrupt.outcome is InterruptOutcome.ACCEPTED, "interrupt outcome normalization drift")
    _assert(diagnostic.dropped_sequence == EventSequence.first(), "diagnostic sequence normalization drift")
    print("[OK] all eight immutable payload models normalize and serialize safely")


def check_validation_and_privacy() -> None:
    from framework import (
        AudioEventPayload,
        DiagnosticEventPayload,
        InterruptEventPayload,
        LifecycleEventPayload,
        MotionEventPayload,
        ResponseEventPayload,
        TranscriptEventPayload,
    )

    _expect_failure(lambda: TranscriptEventPayload(text=object(), is_final=True), TypeError)
    _expect_failure(lambda: TranscriptEventPayload(text="x", is_final=1), TypeError)
    _expect_failure(lambda: TranscriptEventPayload(text="x", is_final=True, confidence=1.1), ValueError)
    _expect_failure(lambda: ResponseEventPayload(text="x", delta_index=-1), ValueError)
    _expect_failure(lambda: AudioEventPayload(artifact_ref=r"C:\\private\\audio.wav", available=True), ValueError)
    _expect_failure(lambda: AudioEventPayload(artifact_ref="provider_token_123", available=True), ValueError)
    _expect_failure(lambda: AudioEventPayload(available=True), ValueError)
    _expect_failure(lambda: AudioEventPayload(artifact_ref="fw_audio_1", available=True, invalidated=True), ValueError)
    _expect_failure(lambda: MotionEventPayload(request_id=object()), TypeError)
    _expect_failure(lambda: InterruptEventPayload(scope=object(), outcome="accepted"), ValueError)
    _expect_failure(lambda: DiagnosticEventPayload(code="drop", overflow_count=-1), ValueError)
    _expect_failure(lambda: LifecycleEventPayload(reason=object()), TypeError)
    print("[OK] arbitrary objects, private artifact paths, secrets, and invalid scalar values are rejected")


def check_non_adoption_and_docs() -> None:
    from framework import RealtimeEvent

    event_fields = {field.name for field in dataclasses.fields(RealtimeEvent)}
    _assert("payload" not in event_fields, "RealtimeEvent payload adopted prematurely")
    _assert("sequence" not in event_fields, "RealtimeEvent sequence adopted prematurely")
    _assert("generation_id" not in event_fields, "RealtimeEvent generation adopted prematurely")
    _assert("terminal" not in event_fields, "RealtimeEvent terminal flag adopted prematurely")

    session_source = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    _assert("RealtimeEventPayload" not in session_source, "session payload emission adopted prematurely")
    _assert("EventSequence.first" not in session_source, "session sequence ownership adopted prematurely")
    _assert("GenerationId.new" not in session_source, "session generation ownership adopted prematurely")

    contract = (PROJECT_ROOT / "docs/v600_realtime_event_contract.md").read_text(encoding="utf-8")
    public = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    for text in (contract, public, app):
        _assert("FW-RT6-1c-A-TYPED-PAYLOADS:BEGIN" in text, "typed payload marker missing")
        _assert("__CONTROL_" not in text, "unresolved event payload placeholder")
    for phrase in (
        "RealtimeEvent envelope adoption: DEFERRED TO CONTROL B",
        "RealtimeSession ordered emission: DEFERRED TO CONTROL D",
        "terminal registry / exactly-once suppression: NOT IMPLEMENTED",
    ):
        _assert(phrase in contract, f"event contract phrase missing: {phrase}")
    print("[OK] docs lock payload semantics while event/session adoption remains deferred")


def check_import_safety() -> None:
    code = r'''
import sys
import framework
from framework import AudioEventPayload, RealtimeEventPayloadKind, TranscriptEventPayload
assert len(framework.__all__) == 114
assert RealtimeEventPayloadKind.TRANSCRIPT.value == "transcript"
assert TranscriptEventPayload(text="x", is_final=True).as_dict()["is_final"] is True
assert AudioEventPayload(artifact_ref="fw_audio_1", available=True).available is True
forbidden = {
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "speech_recognition", "pyaudio", "google.genai", "xai_sdk",
}
loaded = sorted(forbidden & set(sys.modules))
if loaded:
    raise AssertionError(loaded)
print("event-payload-import-safe")
'''
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(result.returncode == 0, result.stdout + result.stderr)
    _assert("event-payload-import-safe" in result.stdout, "payload import subprocess did not complete")
    print("[OK] root-public payload import stays provider/network/runtime safe")


def main() -> None:
    check_repository_contract()
    check_root_public_manifest()
    check_payload_kinds_and_union()
    check_payload_models()
    check_validation_and_privacy()
    check_non_adoption_and_docs()
    check_import_safety()
    print("v600_realtime_event_payload_models_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 10")
    print("v600_previous_root_public_prefix_count: 104")
    print("v600_realtime_event_payload_public_name_count: 10")
    print("v600_root_public_name_count: 114")
    print("v600_typed_payload_union_defined: True")
    print("v600_payload_public_serialization_supported: True")
    print("v600_provider_object_retained: False")
    print("v600_realtime_event_envelope_adopted: False")
    print("v600_event_sequence_generation_wired: False")
    print("v600_terminal_registry_implemented: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1c Control B")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1c Control A typed realtime event payload smoke passed")


if __name__ == "__main__":
    main()
