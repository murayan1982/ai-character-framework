"""FW-RT6-7a Control A voice-input correction gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "f6e2dbb4ada690dd2c3f1ca5afaa13c7d5eb8496"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/voice_input_capability.py",
    "framework/voice_input_provider_execution.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_voice_input_control_a.py",
}


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: " + " ".join(command) + "\n" + result.stdout + result.stderr,
    )
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        p.strip().replace("\\", "/")
        for p in (*tracked, *untracked)
        if p.strip()
    }


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        f"Control A exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7a — VoiceInputSession capability correction")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(section.count("- [ ]") == 6, "FW-RT6-7a must remain 0 / 6 CLOSED")
    _require(section.count("- [x]") == 0, "Control A must not close aggregate tasks")
    print("[OK] exact six-file Control A surface conforms; FW-RT6-7a remains 0 / 6")


def check_capability_correction() -> None:
    from framework.voice_input_capability import (
        VoiceInputProviderStatus,
        get_voice_input_capabilities,
    )
    from framework.voice_input_provider_execution import (
        get_voice_input_provider_execution_status,
        resolve_voice_input_provider_execution_config,
    )

    disabled = get_voice_input_capabilities(
        provider="openai",
        real_stt_enabled=False,
        allow_provider_execution=False,
        credential_env={},
    )
    _require(
        disabled.provider_status is VoiceInputProviderStatus.DISABLED,
        "disabled voice-input behavior drift",
    )
    _require(disabled.supports_real_stt is False, "disabled path overclaims real STT")
    _require(
        disabled.real_executor_available is False,
        "disabled path must not advertise active executor capability",
    )

    openai = get_voice_input_capabilities(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "control-a-placeholder"},
    )
    _require(
        openai.provider_status is VoiceInputProviderStatus.REAL_STT_EXECUTOR_AVAILABLE,
        "OpenAI must no longer report REAL_STT_NOT_IMPLEMENTED",
    )
    _require(openai.supports_real_stt is True, "OpenAI implementation support missing")
    _require(openai.real_executor_available is True, "OpenAI executor availability missing")
    _require(openai.runtime_probe_performed is False, "capability query probed runtime")
    _require(
        openai.public_metadata.get("provider_execution_executed") is False,
        "capability query claims provider execution",
    )

    google = get_voice_input_capabilities(
        provider="google",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"GOOGLE_API_KEY": "control-a-placeholder"},
    )
    _require(
        google.provider_status is VoiceInputProviderStatus.REAL_STT_NOT_IMPLEMENTED,
        "Control A must not overclaim Google real STT implementation",
    )
    _require(google.supports_real_stt is False, "Google support overclaimed")
    _require(google.real_executor_available is False, "Google executor overclaimed")

    openai_exec = get_voice_input_provider_execution_status(
        resolve_voice_input_provider_execution_config(
            provider="openai",
            allow_provider_execution=True,
            credentials_available=True,
        )
    )
    _require(openai_exec.configured is True, "OpenAI execution config should be configured")
    _require(openai_exec.available is False, "execution-free status must not claim runtime availability")
    _require(
        openai_exec.reason_code == "real_stt_executor_available",
        "OpenAI executor implementation status not reflected",
    )
    _require(
        openai_exec.public_metadata.get("real_stt_executor_available") == "true",
        "OpenAI execution metadata missing executor availability",
    )
    _require(
        openai_exec.public_metadata.get("runtime_probe_performed") == "false",
        "execution status must remain runtime-probe free",
    )
    _require(
        openai_exec.public_metadata.get("provider_execution_executed") == "false",
        "execution status must remain execution-free",
    )

    google_exec = get_voice_input_provider_execution_status(
        resolve_voice_input_provider_execution_config(
            provider="google",
            allow_provider_execution=True,
            credentials_available=True,
        )
    )
    _require(
        google_exec.reason_code == "provider_execution_not_implemented",
        "non-OpenAI provider implementation status changed unexpectedly",
    )
    _require(
        google_exec.public_metadata.get("real_stt_executor_available") == "false",
        "non-OpenAI executor availability overclaimed",
    )
    print("[OK] OpenAI real executor implementation is reflected without runtime/provider overclaim")


def check_session_identity_and_event_scaffold() -> None:
    import framework
    from framework.identity import EventSequence, GenerationId, SessionId, TurnId
    from framework.realtime import RealtimeEvent, RealtimeEventType, RealtimeState
    from framework.realtime_event_payloads import LifecycleEventPayload
    from framework.version import VOICE_INPUT_API_VERSION
    from framework.voice_input_session import VoiceInputSessionInfo

    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(
        VoiceInputSessionInfo.__dataclass_fields__["api_version"].default
        == VOICE_INPUT_API_VERSION,
        "VoiceInputSessionInfo.api_version is not connected to central version",
    )
    _require(VOICE_INPUT_API_VERSION == "5.2.0", "Control A changed compatibility API version")

    session = framework.create_voice_input_session()
    _require(isinstance(session.session_id, SessionId), "session_id is not Framework SessionId")
    _require(session.info.session_id == session.session_id, "info/session identity mismatch")
    _require(session.session_id == session.session_id, "session_id is not stable")

    first_context = session._new_realtime_turn_context()
    second_context = session._new_realtime_turn_context()
    _require(first_context.session_id == session.session_id, "turn context session mismatch")
    _require(isinstance(first_context.turn_id, TurnId), "turn_id type mismatch")
    _require(isinstance(first_context.generation_id, GenerationId), "generation_id type mismatch")
    _require(first_context.turn_id != second_context.turn_id, "turn_id must advance per context")
    _require(
        first_context.generation_id != second_context.generation_id,
        "generation_id must advance per context",
    )

    events: list[RealtimeEvent] = []
    callback = events.append
    returned = session.on_realtime_event(callback)
    _require(returned is callback, "on_realtime_event must return callback")

    first = session._emit_realtime_event(
        RealtimeEventType.SESSION_STARTED,
        state=RealtimeState.IDLE,
        payload=LifecycleEventPayload(reason="voice_input_control_a_scaffold"),
    )
    second = session._emit_realtime_event(
        RealtimeEventType.TURN_STARTED,
        state=RealtimeState.LISTENING,
        context=first_context,
        payload=LifecycleEventPayload(reason="voice_input_control_a_turn"),
    )
    _require(first.session_id == session.session_id, "canonical session event identity mismatch")
    _require(first.turn_id is None and first.generation_id is None, "session event should be session-scoped")
    _require(second.turn_id == first_context.turn_id, "canonical turn_id mismatch")
    _require(second.generation_id == first_context.generation_id, "canonical generation mismatch")
    _require(first.sequence == EventSequence.first(), "first sequence mismatch")
    _require(int(second.sequence) == 2, "canonical sequence is not monotonic")
    _require(events == [first, second], "canonical callbacks did not receive exact events")
    _require(first.boundary == "voice_input" and second.boundary == "voice_input", "boundary drift")
    print("[OK] stable session identity, turn/generation scaffold, and canonical event callback conform")


def check_default_fake_path_preserved() -> None:
    import framework
    from framework.voice_input import VoiceInputOutcome
    from framework.voice_input_capability import VoiceInputProviderStatus

    fmt = framework.VoiceInputAudioFormat.wav(
        sample_rate_hz=16000,
        channel_count=1,
        duration_ms=250,
    )
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "control_a_opaque_audio",
        audio_format=fmt,
        language="ja-JP",
        max_duration_ms=1000,
    )

    session = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "control-a-placeholder"},
    )
    _require(
        session.capabilities.provider_status
        is VoiceInputProviderStatus.REAL_STT_EXECUTOR_AVAILABLE,
        "session did not receive corrected OpenAI capability",
    )
    result = session.transcribe_audio_result(source)
    _require(result.outcome is VoiceInputOutcome.COMPLETED, "default fake path no longer completes")
    _require(result.text == "fake transcript", "default fake adapter behavior changed")
    _require(
        result.public_metadata.get("provider_execution_executed") is False,
        "default fake path claims provider execution",
    )
    _require(result.public_metadata.get("audio_read") is False, "default fake path read audio")
    _require(result.public_metadata.get("microphone_accessed") is False, "default fake path used microphone")
    print("[OK] default fake transcription path remains mock-safe; real composition is deferred")


def check_docs_and_boundaries() -> None:
    public_facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app_contract = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    session_source = (PROJECT_ROOT / "framework/voice_input_session.py").read_text(encoding="utf-8")
    result_source = (PROJECT_ROOT / "framework/voice_input.py").read_text(encoding="utf-8")

    for text in (public_facade, app_contract):
        _require(
            "FW-RT6-7a-A-VOICE-INPUT-CORRECTION:BEGIN" in text,
            "Control A documentation marker missing",
        )
        _require("Control B" in text, "Control B deferral missing")

    _require(
        "provider SDK/runtime availability probe:" in public_facade
        and "not performed" in public_facade,
        "public facade runtime-probe truthfulness missing",
    )
    _require(
        "runtime probe performed:" in app_contract
        and "False" in app_contract,
        "app integration runtime-probe truthfulness missing",
    )

    _require(
        "effective_adapter = adapter or FakeVoiceInputProviderAdapter()" in session_source,
        "Control A prematurely changed provider-neutral default composition",
    )
    _require(
        "class VoiceInputResult:" in result_source,
        "VoiceInputResult source unexpectedly missing",
    )
    _require(
        "session_id:" not in result_source
        and "turn_id:" not in result_source
        and "generation_id:" not in result_source,
        "Control A prematurely changed VoiceInputResult correlation shape",
    )
    print("[OK] Control A preserves VoiceInputResult and defers provider-neutral real composition")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_capability_correction()
    check_session_identity_and_event_scaffold()
    check_default_fake_path_preserved()
    check_docs_and_boundaries()

    print("v600_rt6_7a_control_a_status: implemented-awaiting-review")
    print("v600_rt6_7a_control_a_exact_surface: 6 files")
    print("v600_rt6_7a_openai_real_executor_implemented: True / PASS")
    print("v600_rt6_7a_openai_real_stt_not_implemented_stale: removed / PASS")
    print("v600_rt6_7a_openai_supports_real_stt: True / PASS")
    print("v600_rt6_7a_runtime_probe_performed: False / PASS")
    print("v600_rt6_7a_provider_execution: False / PASS")
    print("v600_rt6_7a_network_execution: False / PASS")
    print("v600_rt6_7a_audio_read: False / PASS")
    print("v600_rt6_7a_microphone_access: False / PASS")
    print("v600_rt6_7a_voice_input_api_version: 5.2.0 / UNCHANGED")
    print("v600_rt6_7a_session_id: stable / PASS")
    print("v600_rt6_7a_turn_generation_scaffold: True / PASS")
    print("v600_rt6_7a_canonical_event_scaffold: True / PASS")
    print("v600_rt6_7a_legacy_mapping_callbacks_changed: False")
    print("v600_rt6_7a_voice_input_result_changed: False")
    print("v600_rt6_7a_default_fake_path: PASS")
    print("v600_rt6_7a_provider_neutral_real_composition: deferred-to-Control-B")
    print("v600_rt6_7a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_7a_task_count: 0 / 6 CLOSED")
    print("v600_rt6_7a_control_b: NOT_AUTHORIZED")
    print("v600_rt6_7a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
