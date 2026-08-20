"""Operator-only FW-RT6-13c real-stage acceptance runner.

This command is deliberately outside ``framework``.  It coordinates the
already accepted host-owned STT, streaming LLM, TTS, playback handoff, and
VTube Studio boundaries without enabling unified real ``RealtimeSession``
orchestration.  Importing the module is provider-free.  Actual SDK imports,
network calls, private-file reads, audio access, and VTS connection occur only
after every explicit operator guard passes.

Console output is a fixed set of bounded public markers.  Credential values,
private paths, transcript/LLM text, raw audio, provider payloads, raw exception
text, model names, hotkey names, and selector values are never printed or
written to the repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CONFIG_SCHEMA = "ai-character-framework-v600-rt6-13c-private-config-v1"
EVIDENCE_SCHEMA = "ai-character-framework-v600-rt6-13c-private-evidence-v1"
REAL_CONFIRMATION = (
    "I_ACCEPT_REAL_STT_LLM_TTS_AND_VTS_EXECUTION_AND_POSSIBLE_CHARGES"
)
PRIVATE_CONFIRMATION = (
    "I_WILL_KEEP_CONFIG_AUDIO_TEXT_ARTIFACTS_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY"
)
PLAYBACK_CONFIRMATION = "I_OBSERVED_HOST_PLAYBACK_AND_STOPPED_IT"
EXPECTED_DEPENDENCIES = {
    "openai": "2.31.0",
    "elevenlabs": "2.41.0",
    "pyvts": "0.3.3",
}
_HEAD_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_ENV_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()).resolve()


def _status_paths(root: Path) -> set[str]:
    output = _git(root, "status", "--porcelain=v1", "-z")
    paths: set[str] = set()
    for record in output.split("\0"):
        if not record:
            continue
        value = record[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.add(value.replace("\\", "/"))
    return paths


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _absolute_outside_repo(
    raw: object,
    *,
    root: Path,
    label: str,
    must_exist: bool,
) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{label} must be an absolute path.")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{label} must be an absolute path.")
    resolved = candidate.resolve(strict=must_exist)
    if _is_inside(resolved, root):
        raise ValueError(f"{label} must remain outside the repository.")
    return resolved


def _bounded_private_text(
    value: object,
    *,
    label: str,
    maximum: int = 4096,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be non-empty.")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{label} is too large.")
    return normalized


def _positive_int(value: object, *, label: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer.")
    if not 1 <= value <= maximum:
        raise ValueError(f"{label} is outside the accepted range.")
    return value


def _environment_name(value: object, *, label: str) -> str:
    normalized = _bounded_private_text(value, label=label, maximum=128)
    if not _ENV_PATTERN.fullmatch(normalized):
        raise ValueError(f"{label} is invalid.")
    return normalized


def _exact_mapping(
    value: object,
    *,
    label: str,
    keys: set[str],
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object.")
    if set(value) != keys:
        raise ValueError(f"{label} contains unexpected fields.")
    return value


def _load_private_config(path: Path, *, root: Path) -> dict[str, Any]:
    if not path.is_file() or not 0 < path.stat().st_size <= 128 * 1024:
        raise ValueError("Private configuration is unavailable or too large.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    top = _exact_mapping(
        payload,
        label="Private configuration",
        keys={
            "schema",
            "accepted_framework_head",
            "voice_input",
            "text_generation",
            "voice_output",
            "motion",
        },
    )
    if top.get("schema") != CONFIG_SCHEMA:
        raise ValueError("Private configuration schema mismatch.")
    accepted_head = str(top.get("accepted_framework_head", "")).strip()
    if not _HEAD_PATTERN.fullmatch(accepted_head):
        raise ValueError("Accepted Framework head is invalid.")

    voice_input = _exact_mapping(
        top["voice_input"],
        label="Voice-input configuration",
        keys={
            "audio_file",
            "duration_ms",
            "max_duration_ms",
            "language",
            "model",
            "credential_env",
        },
    )
    audio_file = _absolute_outside_repo(
        voice_input["audio_file"],
        root=root,
        label="Private audio",
        must_exist=True,
    )
    if not audio_file.is_file() or audio_file.suffix.casefold() != ".wav":
        raise ValueError("Private audio must be a regular WAV file.")
    if not 0 < audio_file.stat().st_size <= 25 * 1024 * 1024:
        raise ValueError("Private audio size is outside the accepted range.")

    text_generation = _exact_mapping(
        top["text_generation"],
        label="Text-generation configuration",
        keys={
            "model",
            "system_instruction",
            "interrupt_prompt",
            "recovery_prompt",
            "credential_env",
            "max_tokens",
        },
    )
    voice_output = _exact_mapping(
        top["voice_output"],
        label="Voice-output configuration",
        keys={"voice_profile_id", "artifact_dir", "credential_env"},
    )
    artifact_dir = _absolute_outside_repo(
        voice_output["artifact_dir"],
        root=root,
        label="Private voice artifact directory",
        must_exist=False,
    )
    motion = _exact_mapping(
        top["motion"],
        label="Motion configuration",
        keys={"private_vts_config_file"},
    )
    vts_config = _absolute_outside_repo(
        motion["private_vts_config_file"],
        root=root,
        label="Private VTube Studio configuration",
        must_exist=True,
    )
    if not vts_config.is_file():
        raise ValueError("Private VTube Studio configuration is unavailable.")
    if not 0 < vts_config.stat().st_size <= 64 * 1024:
        raise ValueError(
            "Private VTube Studio configuration is empty or too large."
        )

    duration_ms = _positive_int(
        voice_input["duration_ms"],
        label="Audio duration",
        maximum=120_000,
    )
    max_duration_ms = _positive_int(
        voice_input["max_duration_ms"],
        label="Maximum audio duration",
        maximum=120_000,
    )
    if duration_ms > max_duration_ms:
        raise ValueError("Audio duration exceeds its accepted maximum.")

    return {
        "accepted_framework_head": accepted_head,
        "voice_input": {
            "audio_file": audio_file,
            "duration_ms": duration_ms,
            "max_duration_ms": max_duration_ms,
            "language": _bounded_private_text(
                voice_input["language"], label="Voice-input language", maximum=32
            ),
            "model": _bounded_private_text(
                voice_input["model"], label="Voice-input model", maximum=256
            ),
            "credential_env": _environment_name(
                voice_input["credential_env"], label="Voice-input credential environment"
            ),
        },
        "text_generation": {
            "model": _bounded_private_text(
                text_generation["model"], label="Text-generation model", maximum=256
            ),
            "system_instruction": _bounded_private_text(
                text_generation["system_instruction"],
                label="System instruction",
                maximum=8192,
            ),
            "interrupt_prompt": _bounded_private_text(
                text_generation["interrupt_prompt"],
                label="Interrupt prompt",
                maximum=4096,
            ),
            "recovery_prompt": _bounded_private_text(
                text_generation["recovery_prompt"],
                label="Recovery prompt",
                maximum=4096,
            ),
            "credential_env": _environment_name(
                text_generation["credential_env"],
                label="Text-generation credential environment",
            ),
            "max_tokens": _positive_int(
                text_generation["max_tokens"],
                label="Text-generation max tokens",
                maximum=4096,
            ),
        },
        "voice_output": {
            "voice_profile_id": _bounded_private_text(
                voice_output["voice_profile_id"],
                label="Voice profile",
                maximum=256,
            ),
            "artifact_dir": artifact_dir,
            "credential_env": _environment_name(
                voice_output["credential_env"],
                label="Voice-output credential environment",
            ),
        },
        "motion": {"private_vts_config_file": vts_config},
    }


def _dependency_versions() -> dict[str, str]:
    resolved: dict[str, str] = {}
    for package, expected in EXPECTED_DEPENDENCIES.items():
        try:
            actual = version(package)
        except PackageNotFoundError as error:
            raise RuntimeError("accepted_provider_runtime_not_installed") from error
        if actual != expected:
            raise RuntimeError("accepted_provider_runtime_version_mismatch")
        resolved[package] = actual
    return resolved


def _context_for(*, session_id: object, turn_id: object) -> object:
    from framework.identity import GenerationId
    from framework.realtime_stage import RealtimeStageContext

    return RealtimeStageContext(
        session_id=session_id,
        turn_id=turn_id,
        generation_id=GenerationId.new(),
    )


def _observe_host_playback() -> bool:
    print("v600_13c_host_playback_observation_required: True")
    response = input(f"Type {PLAYBACK_CONFIRMATION}: ").strip()
    return response == PLAYBACK_CONFIRMATION


def _bridge_threads_alive() -> bool:
    return any(
        thread.is_alive() and thread.name == "framework-vts-motion-bridge"
        for thread in threading.enumerate()
    )


def _execute_real_scenarios(
    private: Mapping[str, Any],
    *,
    root: Path,
    playback_observer: Callable[[], bool] = _observe_host_playback,
) -> dict[str, Any]:
    """Execute the accepted real stages after all outer guards have passed."""

    # All provider-aware imports are intentionally inside this explicit path.
    from openai import OpenAI

    import framework
    from framework._realtime_voice_output_control import (
        CancelableProviderNeutralVoiceSynthesisStage,
    )
    from framework.audio._provider_adapter import ElevenLabsVoiceOutputAdapter
    from framework.audio.voice_output import VoiceOutputRequest
    from framework.identity import SessionId, TurnId
    from framework.realtime import RealtimeTurn
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
    )
    from framework.realtime_stage import RealtimeStageContext
    from framework.realtime_text_generation import (
        TextGenerationCancelReason,
        TextGenerationCancellationToken,
    )
    from framework.realtime_text_generation_provider_adapters import (
        OpenAITextGenerationAdapter,
    )
    from framework.realtime_voice_output_queue import (
        BoundedVoiceSynthesisPendingQueue,
    )
    from framework.voice_artifacts import FileVoiceArtifactStore, VoiceArtifactState
    from scripts import operator_v550_vtube_studio_real_motion_acceptance as v550

    values: dict[str, Any] = {
        "configured_real_voice_input": False,
        "configured_real_llm_streaming": False,
        "cooperative_interrupt": False,
        "future_llm_delivery_suppressed": False,
        "provider_hard_cancel_claimed": False,
        "real_tts_generation": False,
        "pending_clear": False,
        "late_artifact_rejection": False,
        "host_playback_owned": True,
        "host_playback_stop_requested": False,
        "host_playback_stop_acknowledged": False,
        "framework_physical_playback_stop_claimed": False,
        "configured_real_motion": False,
        "operator_visual_confirmation": False,
        "interrupt_recovery_next_turn": False,
        "close_cleanup": False,
        "actual_openai_sdk_imported": True,
        "actual_openai_client_created": False,
        "actual_openai_network_execution": False,
        "actual_elevenlabs_sdk_imported": False,
        "actual_elevenlabs_client_created": False,
        "actual_elevenlabs_provider_execution": False,
        "actual_pyvts_imported": False,
        "actual_vts_websocket_connected": False,
        "actual_vts_authenticated": False,
        "actual_vts_protocol_execution": False,
        "stt_transcript_char_count": 0,
        "llm_delta_count": 0,
        "recovery_delta_count": 0,
        "tts_artifact_count": 0,
        "pending_cleared_count": 0,
        "late_artifact_invalidated_count": 0,
        "motion_intent_count": 0,
    }
    text_adapter = None
    tts_stage = None
    motion_session = None
    openai_client = None
    original_tts_env = {
        name: os.environ.get(name)
        for name in (
            "ELEVENLABS_API_KEY",
            "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
            "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
            "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
        )
    }
    try:
        voice = private["voice_input"]
        text = private["text_generation"]
        output = private["voice_output"]

        stt_key = os.environ.get(voice["credential_env"], "").strip()
        llm_key = os.environ.get(text["credential_env"], "").strip()
        tts_key = os.environ.get(output["credential_env"], "").strip()
        if not stt_key or not llm_key or not tts_key:
            raise RuntimeError("accepted_private_credential_unavailable")

        openai_client = OpenAI(api_key=llm_key)
        values["actual_openai_client_created"] = True

        execution_config = framework.resolve_voice_input_provider_execution_config(
            provider="openai",
            allow_provider_execution=True,
            credentials_available=True,
        )
        credential = framework.OpenAIVoiceInputPrivateCredential(stt_key)
        policy = framework.OpenAIVoiceInputRealProviderPolicy(
            max_audio_bytes=25 * 1024 * 1024,
            timeout_seconds=120.0,
            max_retries=0,
            allow_provider_sdk_import=True,
            allow_provider_client_creation=True,
            allow_real_provider_execution=True,
            runtime_mode=framework.OpenAIVoiceInputRuntimeMode.REAL,
        )
        adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=execution_config,
            model=voice["model"],
            client_factory=framework.OpenAIVoiceInputRealClientFactory(
                credential=credential,
                policy=policy,
            ),
        )
        audio_source = framework.VoiceInputAudioSource.from_file_path(
            str(voice["audio_file"]),
            audio_format=framework.VoiceInputAudioFormat.wav(
                duration_ms=voice["duration_ms"]
            ),
            language=voice["language"],
            max_duration_ms=voice["max_duration_ms"],
        )
        stt_result = framework.OpenAIVoiceInputRealProviderExecutor(
            adapter=adapter
        ).execute(
            audio_source=audio_source,
            request=framework.VoiceInputRequest(
                language=voice["language"],
                timeout_ms=120_000,
                max_duration_ms=voice["max_duration_ms"],
            ),
        )
        transcript = stt_result.text if stt_result.is_completed else ""
        stt_metadata = dict(stt_result.public_metadata)
        if not transcript.strip() or not all(
            stt_metadata.get(key) is True
            for key in (
                "provider_sdk_imported",
                "provider_client_created",
                "provider_protocol_call_executed",
                "real_provider_execution_executed",
            )
        ):
            raise RuntimeError("configured_real_voice_input_not_verified")
        values["configured_real_voice_input"] = True
        values["actual_openai_network_execution"] = True
        values["stt_transcript_char_count"] = len(transcript)

        session_id = SessionId.new()
        first_turn_id = TurnId.new()
        first_context = _context_for(
            session_id=session_id,
            turn_id=first_turn_id,
        )
        text_adapter = OpenAITextGenerationAdapter(
            client=openai_client,
            model=text["model"],
            system_instruction=text["system_instruction"],
            max_tokens=text["max_tokens"],
        )
        first_stream = text_adapter.open_stream(
            context=first_context,
            request=RealtimeTurn(
                session_id=session_id,
                turn_id=first_turn_id,
                input_text=transcript,
            ),
            cancellation_token=TextGenerationCancellationToken(),
        )
        first_deltas = list(first_stream)
        first_text = "".join(delta.text for delta in first_deltas)
        if not first_deltas or not first_text.strip():
            raise RuntimeError("configured_real_llm_streaming_not_verified")
        values["configured_real_llm_streaming"] = True
        values["llm_delta_count"] = len(first_deltas)

        interrupt_turn_id = TurnId.new()
        interrupt_context = _context_for(
            session_id=session_id,
            turn_id=interrupt_turn_id,
        )
        interrupt_stream = text_adapter.open_stream(
            context=interrupt_context,
            request=RealtimeTurn(
                session_id=session_id,
                turn_id=interrupt_turn_id,
                input_text=text["interrupt_prompt"],
            ),
            cancellation_token=TextGenerationCancellationToken(),
        )
        next(interrupt_stream)
        cancel_accepted = interrupt_stream.request_cancel(
            TextGenerationCancelReason.INTERRUPT
        )
        suppressed = list(interrupt_stream) == []
        hard_cancel_claimed = bool(
            text_adapter.capability().provider_hard_cancel_supported
        )
        if not cancel_accepted or not suppressed or hard_cancel_claimed:
            raise RuntimeError("cooperative_interrupt_not_verified")
        values["cooperative_interrupt"] = True
        values["future_llm_delivery_suppressed"] = True
        values["provider_hard_cancel_claimed"] = False

        recovery_turn_id = TurnId.new()
        recovery_context = _context_for(
            session_id=session_id,
            turn_id=recovery_turn_id,
        )
        recovery_stream = text_adapter.open_stream(
            context=recovery_context,
            request=RealtimeTurn(
                session_id=session_id,
                turn_id=recovery_turn_id,
                input_text=text["recovery_prompt"],
            ),
            cancellation_token=TextGenerationCancellationToken(),
        )
        recovery_deltas = list(recovery_stream)
        recovery_text = "".join(delta.text for delta in recovery_deltas)
        if not recovery_deltas or not recovery_text.strip():
            raise RuntimeError("interrupt_recovery_not_verified")
        values["interrupt_recovery_next_turn"] = True
        values["recovery_delta_count"] = len(recovery_deltas)

        artifact_dir = output["artifact_dir"]
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if not artifact_dir.is_dir() or _is_inside(artifact_dir, root):
            raise RuntimeError("private_voice_artifact_directory_invalid")
        os.environ["ELEVENLABS_API_KEY"] = tts_key
        os.environ["FRAMEWORK_VOICE_OUTPUT_REAL_TTS"] = "1"
        os.environ["FRAMEWORK_VOICE_OUTPUT_PROVIDER"] = "elevenlabs"
        os.environ["FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION"] = "1"

        store = FileVoiceArtifactStore(artifact_dir)
        tts_adapter = ElevenLabsVoiceOutputAdapter(
            project_root=root,
            artifact_dir=artifact_dir,
            artifact_store=store,
        )
        gate = RealtimeGenerationGate()
        tts_turn_id = TurnId.new()
        tts_generation_id = gate.start_generation(tts_turn_id)
        tts_context = RealtimeStageContext(
            session_id=session_id,
            turn_id=tts_turn_id,
            generation_id=tts_generation_id,
        )
        tts_stage = CancelableProviderNeutralVoiceSynthesisStage(
            tts_adapter,
            artifact_store=store,
            generation_gate=gate,
        )
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=2)
        tts_request = VoiceOutputRequest(
            text=recovery_text,
            voice_profile_id=output["voice_profile_id"],
            requested_audio_format="mp3",
        )
        enqueued = queue.enqueue(context=tts_context, request=tts_request)
        cleared = queue.clear_pending(context=tts_context)
        if not enqueued.accepted or cleared.cleared_count != 1:
            raise RuntimeError("pending_clear_not_verified")
        values["pending_clear"] = True
        values["pending_cleared_count"] = cleared.cleared_count

        tts_envelope = tts_stage.start(context=tts_context, request=tts_request)
        if not tts_envelope.result.is_generated:
            raise RuntimeError("real_tts_generation_not_verified")
        values["real_tts_generation"] = True
        values["actual_elevenlabs_sdk_imported"] = "elevenlabs" in sys.modules
        values["actual_elevenlabs_client_created"] = True
        values["actual_elevenlabs_provider_execution"] = True
        values["tts_artifact_count"] = 1

        values["host_playback_stop_requested"] = True
        if not playback_observer():
            raise RuntimeError("host_playback_stop_observation_missing")
        values["host_playback_stop_acknowledged"] = True

        gate.advance(GenerationAdvanceReason.INTERRUPT)
        late_envelope = tts_stage.start(context=tts_context, request=tts_request)
        invalidated_count = sum(
            stored.record.state is VoiceArtifactState.INVALIDATED
            for stored in store._records.values()
        )
        if (
            late_envelope.result.has_audio_handoff
            or late_envelope.result.request_state != "stale"
            or not tts_stage.last_stale_delivery_suppressed
            or invalidated_count < 1
        ):
            raise RuntimeError("late_artifact_rejection_not_verified")
        values["late_artifact_rejection"] = True
        values["late_artifact_invalidated_count"] = invalidated_count

        motion_private = v550._load_private_config(
            private["motion"]["private_vts_config_file"],
            root=root,
        )
        token = motion_private["token_path"].read_text(encoding="utf-8").strip()
        if not token or len(token) > 256:
            raise RuntimeError("private_vts_authentication_unavailable")
        motion_session = framework.create_motion_session(
            adapter="vts",
            real_adapter_enabled=True,
            allow_provider_execution=True,
            runtime_available=True,
            model_selected=True,
            vts_endpoint_host=motion_private["host"],
            vts_endpoint_port=motion_private["port"],
            vts_authentication_token=token,
            vts_hotkey_bindings=motion_private["bindings"],
            vts_connect_timeout_seconds=10.0,
            vts_authenticate_timeout_seconds=10.0,
            vts_request_timeout_seconds=10.0,
            vts_close_timeout_seconds=5.0,
        )
        token = ""
        capability = motion_session.preflight()
        motion_metadata = dict(capability.public_metadata)
        motion_facts = {
            "private_config_outside_repo": True,
            "private_token_outside_repo": True,
            "private_evidence_outside_repo": True,
            "actual_pyvts_imported": motion_metadata.get("provider_sdk_imported")
            is True,
            "actual_websocket_connected": motion_metadata.get("connected") is True,
            "actual_vts_authenticated": motion_metadata.get("authenticated") is True,
            "actual_model_loaded": motion_metadata.get("model_loaded") is True,
            "actual_hotkey_inventory_loaded": motion_metadata.get(
                "hotkey_inventory_loaded"
            )
            is True,
        }
        if not v550._capability_matches_private(
            capability, motion_private, motion_facts
        ):
            raise RuntimeError("configured_real_motion_preflight_not_verified")
        motion_results, motion_verified = v550._run_intents(
            motion_session, motion_private
        )
        if not motion_results or not all(
            motion_verified[name] for name in v550.REQUIRED_INTENTS
        ):
            raise RuntimeError("configured_real_motion_not_verified")
        values["configured_real_motion"] = True
        values["operator_visual_confirmation"] = True
        values["actual_pyvts_imported"] = True
        values["actual_vts_websocket_connected"] = True
        values["actual_vts_authenticated"] = True
        values["actual_vts_protocol_execution"] = all(
            result["provider_protocol_call_executed"]
            for result in motion_results.values()
        )
        values["motion_intent_count"] = len(motion_results)

        text_adapter.close()
        tts_stage.close()
        motion_session.close()
        openai_client.close()
        values["close_cleanup"] = bool(
            motion_session.is_closed and not _bridge_threads_alive()
        )
        return values
    finally:
        for resource in (text_adapter, tts_stage, motion_session, openai_client):
            if resource is None:
                continue
            try:
                resource.close()
            except Exception:
                pass
        for name, previous in original_tts_env.items():
            if previous is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = previous


def _build_evidence(
    *,
    run_id: str,
    framework_head: str,
    dependencies: Mapping[str, str],
    scenario_values: Mapping[str, Any],
    repo_clean_after: bool,
) -> dict[str, Any]:
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "framework_head": framework_head,
        "dependency_versions": dict(dependencies),
        "repo_clean_before": True,
        "repo_clean_after": bool(repo_clean_after),
        "private_config_outside_repo": True,
        "private_audio_outside_repo": True,
        "private_artifacts_outside_repo": True,
        "private_evidence_outside_repo": True,
        **dict(scenario_values),
        "credential_value_exposed": False,
        "private_path_exposed": False,
        "raw_audio_exposed": False,
        "raw_provider_payload_exposed": False,
        "raw_exception_exposed": False,
        "transcript_text_exposed": False,
        "llm_text_exposed": False,
        "private_model_exposed": False,
        "private_hotkey_exposed": False,
        "private_selector_exposed": False,
        "microphone_accessed": False,
        "framework_realtime_session_real_orchestration_used": False,
        "drc_repo_changed": False,
    }
    return evidence


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run FW-RT6-13c host-owned real-stage operator acceptance. "
            "This does not enable real RealtimeSession orchestration."
        )
    )
    parser.add_argument("--private-config", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--confirm-real-provider-execution", required=True)
    parser.add_argument("--confirm-private-artifacts-outside-repo", required=True)
    return parser


def _print_markers(
    *,
    status: str,
    stage: str,
    values: Mapping[str, Any],
) -> None:
    print(f"v600_13c_operator_run_status: {status}")
    print(f"v600_13c_operator_run_stage: {stage}")
    for key in (
        "configured_real_voice_input",
        "configured_real_llm_streaming",
        "cooperative_interrupt",
        "future_llm_delivery_suppressed",
        "real_tts_generation",
        "pending_clear",
        "late_artifact_rejection",
        "host_playback_owned",
        "host_playback_stop_requested",
        "host_playback_stop_acknowledged",
        "configured_real_motion",
        "operator_visual_confirmation",
        "interrupt_recovery_next_turn",
        "close_cleanup",
        "repo_clean_after",
    ):
        print(f"v600_13c_{key}: {bool(values.get(key, False))}")
    print("v600_13c_provider_hard_cancel_claimed: False")
    print("v600_13c_framework_physical_playback_stop_claimed: False")
    print("v600_13c_credential_value_exposed: False")
    print("v600_13c_private_path_exposed: False")
    print("v600_13c_raw_audio_exposed: False")
    print("v600_13c_raw_provider_payload_exposed: False")
    print("v600_13c_raw_exception_exposed: False")
    print("v600_13c_transcript_text_exposed: False")
    print("v600_13c_llm_text_exposed: False")
    print("v600_13c_private_model_hotkey_selector_exposed: False")
    print("v600_13c_framework_realtime_session_real_orchestration_used: False")


def main() -> int:
    args = _build_parser().parse_args()
    stage = "validation"
    values: dict[str, Any] = {}
    try:
        root = _repo_root()
        if root != REPO_ROOT.resolve() or Path.cwd().resolve() != root:
            raise RuntimeError("operator_must_run_from_repository_root")
        if args.confirm_real_provider_execution != REAL_CONFIRMATION:
            raise RuntimeError("real_provider_confirmation_mismatch")
        if args.confirm_private_artifacts_outside_repo != PRIVATE_CONFIRMATION:
            raise RuntimeError("private_artifact_confirmation_mismatch")
        if os.environ.get("OPENAI_LOG", "").strip().casefold() == "debug":
            raise RuntimeError("provider_debug_logging_forbidden")
        if _git(root, "branch", "--show-current") != "main":
            raise RuntimeError("accepted_main_branch_required")
        if _status_paths(root) - {".vscode/settings.json"}:
            raise RuntimeError("clean_worktree_required")

        config_path = _absolute_outside_repo(
            args.private_config,
            root=root,
            label="Private configuration",
            must_exist=True,
        )
        private = _load_private_config(config_path, root=root)
        head = _git(root, "rev-parse", "HEAD")
        if head != private["accepted_framework_head"]:
            raise RuntimeError("accepted_framework_head_mismatch")
        if _git(root, "rev-parse", "origin/main") != head:
            raise RuntimeError("origin_main_must_match_head")

        evidence_root = _absolute_outside_repo(
            args.evidence_root,
            root=root,
            label="Private evidence root",
            must_exist=False,
        )
        evidence_root.mkdir(parents=True, exist_ok=True)
        if not evidence_root.is_dir():
            raise RuntimeError("private_evidence_root_unavailable")

        dependencies = _dependency_versions()
        stage = "real_stages"
        values = _execute_real_scenarios(private, root=root)
        stage = "cleanup"
        repo_clean_after = not (
            _status_paths(root) - {".vscode/settings.json"}
        )
        values["repo_clean_after"] = repo_clean_after
        if not repo_clean_after or not values.get("close_cleanup"):
            raise RuntimeError("operator_cleanup_not_verified")

        run_id = uuid.uuid4().hex
        run_dir = evidence_root / f"v600_rt6_13c_{run_id}"
        run_dir.mkdir(parents=False, exist_ok=False)
        evidence = _build_evidence(
            run_id=run_id,
            framework_head=head,
            dependencies=dependencies,
            scenario_values=values,
            repo_clean_after=repo_clean_after,
        )
        _write_json_atomic(run_dir / "operator_evidence.json", evidence)
        _print_markers(status="completed", stage="completed", values=values)
        print(f"v600_13c_private_evidence_run_id: {run_id}")
        print("v600_13c_private_evidence_validation: run-private-verifier")
        return 0
    except Exception:
        try:
            root = _repo_root()
            values["repo_clean_after"] = not (
                _status_paths(root) - {".vscode/settings.json"}
            )
        except Exception:
            values["repo_clean_after"] = False
        _print_markers(status="failed", stage=stage, values=values)
        print("v600_13c_operator_safe_message: operator acceptance did not complete")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
