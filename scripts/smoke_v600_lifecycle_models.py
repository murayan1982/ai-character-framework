"""FW-RT6-1b Control A public lifecycle model smoke.

Offline-safe: validates the exact additive public surface, lifecycle scalar
models, transition matrix, typed failures, and non-adoption deferrals without
provider or runtime execution.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "c89ca5f0ae186564a8f7bced2ea7ce1462459172"
EXPECTED_SURFACE = {
    "framework/lifecycle.py",
    "framework/public_api.py",
    "framework/__init__.py",
    "scripts/smoke_v600_lifecycle_models.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
    "scripts/smoke_app_sdk.py",
    "docs/v600_lifecycle_contract.md",
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
    'SessionId',
    'TurnId',
    'GenerationId',
    'EventSequence',
)
LIFECYCLE_NAMES = (
    "RealtimePhase",
    "TurnOutcome",
    "RecoveryAction",
    "LifecycleTransitionErrorCode",
    "LifecycleTransitionError",
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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control A baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control A surface: {sorted(_changed_paths())}")
    print("[OK] Control A baseline and exact ten-file surface match")


def check_root_public_manifest() -> None:
    import framework
    from framework.public_api import LIFECYCLE_PUBLIC_EXPORTS, PUBLIC_API_NAMES

    _assert(PUBLIC_API_NAMES[:99] == LEGACY_PUBLIC_API_NAMES, "legacy 99-name prefix/order drift")
    _assert(tuple(LIFECYCLE_PUBLIC_EXPORTS) == LIFECYCLE_NAMES, "lifecycle public group drift")
    _assert(PUBLIC_API_NAMES[99:] == LIFECYCLE_NAMES, "lifecycle names must be appended")
    _assert(len(PUBLIC_API_NAMES) == 104, "canonical root-public total must be 104")
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    for name in LIFECYCLE_NAMES:
        _assert(getattr(framework, name) is not None, f"missing root-public lifecycle type: {name}")
    _assert(not (FORBIDDEN_IMPORTS & set(sys.modules)), "provider SDK imported by lifecycle surface")
    print("[OK] legacy 99-name prefix is preserved and five lifecycle names are appended")


def check_enum_contracts() -> None:
    from framework import RealtimePhase, RecoveryAction, TurnOutcome

    _assert(
        tuple(value.value for value in RealtimePhase)
        == ("idle", "listening", "transcribing", "thinking", "speaking", "motion", "recovering"),
        "RealtimePhase value/order drift",
    )
    _assert(
        tuple(value.value for value in TurnOutcome)
        == ("completed", "interrupted", "cancelled", "failed", "rejected", "closed"),
        "TurnOutcome value/order drift",
    )
    _assert(
        tuple(value.value for value in RecoveryAction)
        == ("none", "reuse_session", "reset_turn", "reset_session", "reconnect", "close_session", "permanent_failure"),
        "RecoveryAction value/order drift",
    )
    _assert(not ({"completed", "interrupted", "cancelled", "failed", "rejected", "closed"} & {v.value for v in RealtimePhase}), "terminal value leaked into phase")
    _assert(json.loads(json.dumps(RealtimePhase.THINKING)) == "thinking", "phase JSON scalar drift")
    _assert(json.loads(json.dumps(TurnOutcome.REJECTED)) == "rejected", "outcome JSON scalar drift")
    _assert(json.loads(json.dumps(RecoveryAction.RESET_TURN)) == "reset_turn", "recovery JSON scalar drift")
    print("[OK] phase, terminal outcome, and recovery enums are separate JSON-safe scalars")


def check_phase_matrix() -> None:
    from framework import LifecycleTransitionError, LifecycleTransitionErrorCode, RealtimePhase
    from framework.lifecycle import validate_phase_transition

    valid = (
        (RealtimePhase.IDLE, RealtimePhase.LISTENING),
        (RealtimePhase.LISTENING, RealtimePhase.TRANSCRIBING),
        (RealtimePhase.TRANSCRIBING, RealtimePhase.THINKING),
        (RealtimePhase.THINKING, RealtimePhase.SPEAKING),
        (RealtimePhase.SPEAKING, RealtimePhase.MOTION),
        (RealtimePhase.MOTION, RealtimePhase.RECOVERING),
        (RealtimePhase.RECOVERING, RealtimePhase.IDLE),
        (RealtimePhase.IDLE, RealtimePhase.IDLE),
    )
    for previous, next_phase in valid:
        _assert(validate_phase_transition(previous, next_phase) is next_phase, "valid phase transition rejected")

    invalid = (
        (RealtimePhase.SPEAKING, RealtimePhase.THINKING),
        (RealtimePhase.MOTION, RealtimePhase.TRANSCRIBING),
        (RealtimePhase.RECOVERING, RealtimePhase.SPEAKING),
    )
    for previous, next_phase in invalid:
        try:
            validate_phase_transition(previous, next_phase)
        except LifecycleTransitionError as exc:
            _assert(exc.code is LifecycleTransitionErrorCode.INVALID_PHASE_TRANSITION, "wrong transition error code")
            _assert(exc.from_phase is previous and exc.to_phase is next_phase, "transition error context drift")
            _assert(exc.safe_message == str(exc), "transition error should expose one safe message")
            _assert(not hasattr(exc, "provider_payload"), "transition error should not retain provider payload")
        else:
            raise AssertionError("invalid phase transition was accepted")
    print("[OK] transition matrix accepts valid paths and returns typed public-safe failures")


def check_terminal_validation() -> None:
    from framework import LifecycleTransitionError, LifecycleTransitionErrorCode, TurnOutcome
    from framework.lifecycle import validate_terminal_transition

    _assert(validate_terminal_transition(None, TurnOutcome.COMPLETED) is TurnOutcome.COMPLETED, "first terminal should be accepted")
    try:
        validate_terminal_transition(TurnOutcome.COMPLETED, TurnOutcome.COMPLETED)
    except LifecycleTransitionError as exc:
        _assert(exc.code is LifecycleTransitionErrorCode.DUPLICATE_TERMINAL, "duplicate terminal code drift")
        _assert(exc.existing_outcome is TurnOutcome.COMPLETED, "duplicate existing outcome drift")
    else:
        raise AssertionError("duplicate terminal was accepted")

    try:
        validate_terminal_transition(TurnOutcome.COMPLETED, TurnOutcome.FAILED)
    except LifecycleTransitionError as exc:
        _assert(exc.code is LifecycleTransitionErrorCode.TERMINAL_REGRESSION, "terminal regression code drift")
        _assert(exc.attempted_outcome is TurnOutcome.FAILED, "terminal attempted outcome drift")
    else:
        raise AssertionError("terminal regression was accepted")
    print("[OK] first terminal, duplicate terminal, and terminal regression semantics conform")


def check_non_adoption_and_docs() -> None:
    realtime = (PROJECT_ROOT / "framework/realtime.py").read_text(encoding="utf-8")
    session = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    _assert("from .lifecycle import" not in realtime, "RealtimeTurnResult adopted lifecycle models prematurely")
    _assert("RealtimePhase" not in session, "RealtimeSession adopted canonical phase prematurely")
    _assert("outcome: RealtimeState | str" in realtime, "legacy turn outcome contract changed in Control A")

    contract = (PROJECT_ROOT / "docs/v600_lifecycle_contract.md").read_text(encoding="utf-8")
    public = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    for text in (contract, public, app):
        _assert("FW-RT6-1b-A-LIFECYCLE-MODELS:BEGIN" in text, "lifecycle marker missing")
        _assert("__CONTROL_" not in text, "unresolved lifecycle placeholder")
    for phrase in (
        "cancelled` and `interrupted` are intentionally distinct",
        "terminal registry / exactly-once suppression: NOT IMPLEMENTED",
        "RealtimeTurnResult outcome adoption: Control B",
        "RealtimeSession phase adoption: Control C",
    ):
        _assert(phrase in contract, f"lifecycle contract phrase missing: {phrase}")
    print("[OK] docs lock semantics while current realtime runtime remains unchanged")


def check_import_safety() -> None:
    code = r"""
import sys
import framework
from framework import (
    LifecycleTransitionError, LifecycleTransitionErrorCode,
    RealtimePhase, RecoveryAction, TurnOutcome,
)
assert len(framework.__all__) == 104
assert RealtimePhase.IDLE.value == "idle"
assert TurnOutcome.CANCELLED.value == "cancelled"
assert RecoveryAction.RESET_SESSION.value == "reset_session"
assert issubclass(LifecycleTransitionError, ValueError)
assert LifecycleTransitionErrorCode.TERMINAL_REGRESSION.value == "terminal_regression"
forbidden = {
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "speech_recognition", "pyaudio", "google.genai", "xai_sdk",
}
loaded = sorted(forbidden & set(sys.modules))
if loaded:
    raise AssertionError(loaded)
print("lifecycle-import-safe")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(result.returncode == 0, result.stdout + result.stderr)
    _assert("lifecycle-import-safe" in result.stdout, "lifecycle import subprocess did not complete")
    print("[OK] root-public lifecycle import stays provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_root_public_manifest()
    check_enum_contracts()
    check_phase_matrix()
    check_terminal_validation()
    check_non_adoption_and_docs()
    check_import_safety()
    print("v600_lifecycle_models_status: implemented-awaiting-review")
    print("v600_legacy_root_public_prefix_count: 99")
    print("v600_lifecycle_public_name_count: 5")
    print("v600_root_public_name_count: 104")
    print("v600_transient_phase_terminal_outcome_separate: True")
    print("v600_invalid_transition_typed_failure: True")
    print("v600_duplicate_terminal_typed_failure: True")
    print("v600_terminal_regression_prohibited: True")
    print("v600_realtime_turn_result_adopted: False")
    print("v600_realtime_session_phase_adopted: False")
    print("v600_terminal_registry_implemented: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1b Control B")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1b Control A public lifecycle model smoke passed")


if __name__ == "__main__":
    main()
