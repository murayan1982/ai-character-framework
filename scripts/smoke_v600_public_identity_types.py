"""FW-RT6-1a Control A public identity primitive smoke.

Offline-safe: validates root-public scalar identities, serialization, validation,
legacy manifest ordering, and correlation policy without provider execution.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "24b0e24e89e1382e0151f4172ae850b25ccd48a1"
EXPECTED_SURFACE = {
    "framework/identity.py",
    "framework/public_api.py",
    "framework/__init__.py",
    "scripts/smoke_v600_public_identity_types.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
    "scripts/smoke_app_sdk.py",
    "docs/v600_public_identity_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
LEGACY_PUBLIC_API_NAMES = (
    'OpenAIVoiceInputClient',
    'OpenAIVoiceInputClientFactory',
    'OpenAIVoiceInputPreflight',
    'OpenAIVoiceInputPreflightStatus',
    'OpenAIVoiceInputProviderAdapter',
    'OpenAIVoiceInputFakeClientMarker',
    'OpenAIVoiceInputFakeExecutionPolicy',
    'OpenAIVoiceInputFakeExecutionStatus',
    'OpenAIVoiceInputFakeExecutor',
    'OpenAIVoiceInputPrivateCredential',
    'OpenAIVoiceInputRealClientFactory',
    'OpenAIVoiceInputRealProviderExecutor',
    'OpenAIVoiceInputRealProviderPolicy',
    'OpenAIVoiceInputRealProviderStatus',
    'OpenAIVoiceInputRuntimeMode',
    'VoiceInputProviderExecutionConfig',
    'resolve_voice_input_provider_execution_config',
    'get_voice_input_provider_execution_status',
    'GuardedRealVoiceInputProviderAdapter',
    'VoiceInputProviderAdapterInfo',
    'VoiceInputProviderAdapter',
    'FakeVoiceInputProviderAdapter',
    'VoiceInputAudioSourceKind',
    'VoiceInputAudioSource',
    'VoiceInputAudioRef',
    'VoiceInputAudioFormat',
    'VoiceInputAudioEncoding',
    'FacadeConfigError',
    'FacadeError',
    'FacadeProviderError',
    'TextChatSession',
    'TextChatSessionEvent',
    'TextChatSessionInfo',
    'TextChatStateChange',
    'VoiceOutputRequest',
    'VoiceArtifactRef',
    'VoiceOutputResult',
    'VoiceOutputSession',
    'VoiceOutputSessionInfo',
    'VoiceSynthesisRequest',
    'VoiceSynthesisResult',
    'create_text_chat_session',
    'create_voice_output_session',
    'TextChatResult',
    'CapabilityStatus',
    'FrameworkCapabilities',
    'get_capabilities',
    'VoiceInputErrorCode',
    'VoiceInputOutcome',
    'VoiceInputRequest',
    'VoiceInputResult',
    'VoiceInputSession',
    'VoiceInputSessionInfo',
    'create_voice_input_session',
    'VoiceInputCapabilities',
    'VoiceInputProviderConfig',
    'VoiceInputProviderStatus',
    'get_voice_input_capabilities',
    'resolve_voice_input_provider_config',
    'RealtimeErrorCode',
    'RealtimeEvent',
    'RealtimeEventType',
    'RealtimeState',
    'RealtimeTurn',
    'RealtimeTurnResult',
    'RealtimeSession',
    'RealtimeSessionInfo',
    'create_realtime_session',
    'BargeInDecision',
    'BargeInPolicy',
    'BargeInPolicyMode',
    'InterruptOutcome',
    'InterruptReason',
    'InterruptRequest',
    'InterruptResult',
    'InterruptScope',
    'OutputFlushOutcome',
    'OutputFlushRequest',
    'OutputFlushResult',
    'TTSQueueState',
    'MotionAdapterStatus',
    'MotionCapability',
    'MotionErrorCode',
    'MotionEventType',
    'MotionIntent',
    'MotionOutcome',
    'MotionRequest',
    'MotionResult',
    'MotionState',
    'MotionSession',
    'MotionSessionInfo',
    'create_motion_session',
    'MotionAdapterExecutionConfig',
    'get_motion_adapter_execution_capability',
    'resolve_motion_adapter_execution_config',
)
IDENTITY_NAMES = ("SessionId", "TurnId", "GenerationId", "EventSequence")
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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control A baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control A surface: {sorted(_changed_paths())}")
    print("[OK] Control A baseline and exact ten-file surface match")


def check_root_public_manifest() -> None:
    import framework
    from framework.public_api import IDENTITY_PUBLIC_EXPORTS, PUBLIC_API_NAMES

    _assert(PUBLIC_API_NAMES[:95] == LEGACY_PUBLIC_API_NAMES, "legacy 95-name prefix/order drift")
    _assert(tuple(IDENTITY_PUBLIC_EXPORTS) == IDENTITY_NAMES, "identity public group drift")
    _assert(PUBLIC_API_NAMES[95:] == IDENTITY_NAMES, "identity names must be appended")
    _assert(len(PUBLIC_API_NAMES) == 99, "canonical root-public total must be 99")
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    for name in IDENTITY_NAMES:
        _assert(getattr(framework, name) is not None, f"missing root-public identity: {name}")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider SDK imported by root identity surface")
    print("[OK] legacy public prefix is preserved and four identity names are appended")


def check_identity_values() -> None:
    from framework import EventSequence, GenerationId, SessionId, TurnId

    cases = (
        (SessionId, "fw_session_"),
        (TurnId, "fw_turn_"),
        (GenerationId, "fw_generation_"),
    )
    for identity_type, prefix in cases:
        value = identity_type.new()
        _assert(isinstance(value, str), f"{identity_type.__name__} must remain a string")
        _assert(re.fullmatch(re.escape(prefix) + r"[0-9a-f]{32}", value) is not None, "serialized identity format drift")
        _assert(identity_type.parse(value) is value, "parse should preserve an existing typed value")
        _assert(identity_type.parse(value.to_json_value()) == value, "identity JSON roundtrip failed")
        _assert(json.loads(json.dumps(value)) == str(value), "identity JSON scalar drift")

    session_id = SessionId.new()
    turn_id = TurnId.new()
    generation_id = GenerationId.new()
    _assert(len({session_id, turn_id, generation_id}) == 3, "identity values must be hashable")

    sequence = EventSequence.first()
    _assert(isinstance(sequence, int) and not isinstance(sequence, bool), "EventSequence must be an integer")
    _assert(sequence == 1 and sequence.next() == 2, "EventSequence monotonic contract drift")
    _assert(EventSequence.parse(sequence.to_json_value()) == sequence, "sequence JSON roundtrip failed")
    _assert(json.loads(json.dumps(sequence)) == 1, "sequence JSON scalar drift")
    print("[OK] identity generation and JSON scalar serialization conform")


def check_validation() -> None:
    from framework import EventSequence, GenerationId, SessionId, TurnId

    valid_session = SessionId.new()
    invalid_session_values = (
        "",
        " " + valid_session,
        valid_session + " ",
        str(TurnId.new()),
        str(GenerationId.new()),
        "session_" + "0" * 32,
        "fw_session_" + "A" * 32,
        "fw_session_" + "z" * 32,
        "fw_session_../private",
        "provider-request-123",
    )
    for value in invalid_session_values:
        try:
            SessionId.parse(value)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid SessionId was accepted: {value!r}")

    for value in (0, -1, True, False, 1.0, "1"):
        try:
            EventSequence.parse(value)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid EventSequence was accepted: {value!r}")
    print("[OK] cross-kind, path-like, malformed, and non-positive identities are rejected")


def check_import_safety() -> None:
    code = r"""
import sys
import framework
from framework import EventSequence, GenerationId, SessionId, TurnId
assert len(framework.__all__) == 99
assert SessionId.new().startswith("fw_session_")
assert TurnId.new().startswith("fw_turn_")
assert GenerationId.new().startswith("fw_generation_")
assert EventSequence.first() == 1
forbidden = {
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "speech_recognition", "pyaudio", "google.genai", "xai_sdk",
}
loaded = sorted(forbidden & set(sys.modules))
if loaded:
    raise AssertionError(loaded)
print("identity-import-safe")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(result.returncode == 0, result.stdout + result.stderr)
    _assert("identity-import-safe" in result.stdout, "identity import subprocess did not complete")
    print("[OK] root-public identity import stays provider/runtime safe")


def check_docs_and_policy() -> None:
    contract = (PROJECT_ROOT / "docs/v600_public_identity_contract.md").read_text(encoding="utf-8")
    public = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    _assert("FW-RT6-1a-A-PUBLIC-IDENTITY:BEGIN" in public, "public facade marker missing")
    _assert("FW-RT6-1a-A-PUBLIC-IDENTITY:BEGIN" in app, "app integration marker missing")
    for required in (
        "TextChatResult: session_id / turn_id / generation_id",
        "VoiceInputResult: session_id / turn_id / generation_id",
        "VoiceOutputResult: session_id / turn_id / generation_id",
        "MotionResult: session_id / turn_id / generation_id",
        "provider request identifiers copied into Framework identity fields: False",
        "EventSequence stored on stage result models: False",
    ):
        _assert(required in contract, f"identity policy marker missing: {required}")
    _assert("__CONTROL_" not in contract + public + app, "unresolved identity contract placeholder")
    print("[OK] all-stage correlation policy is documented without premature result wiring")


def main() -> None:
    check_repository_contract()
    check_root_public_manifest()
    check_identity_values()
    check_validation()
    check_import_safety()
    check_docs_and_policy()
    print("v600_public_identity_status: implemented-awaiting-review")
    print("v600_legacy_root_public_prefix_count: 95")
    print("v600_identity_public_name_count: 4")
    print("v600_root_public_name_count: 99")
    print("v600_session_identity_stable: True")
    print("v600_turn_identity_stable: True")
    print("v600_generation_identity_stable: True")
    print("v600_event_sequence_positive: True")
    print("v600_provider_identifier_exposed: False")
    print("v600_result_correlation_wired: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1a Control B")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1a Control A public identity smoke passed")


if __name__ == "__main__":
    main()
