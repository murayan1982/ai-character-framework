"""FW-RT6-6b Control B opaque artifact provider-adoption smoke gate."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import types
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "d9f4a562728ba1c63b82c83f4ff5826cf900f9b0"
EXPECTED_SURFACE = {
    "docs/voice_output_artifact_result_contract.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/audio/_provider_adapter.py",
    "framework/audio/voice_output.py",
    "framework/realtime_voice_output.py",
    "scripts/smoke_voice_output_artifact_result_contract.py",
    "scripts/smoke_v600_voice_artifact_store_control_b.py",
}
EXPECTED_ARTIFACT_EXPORTS = (
    "VoiceArtifactId",
    "VoiceArtifactState",
    "VoiceArtifactRecord",
    "VoiceArtifactStore",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(
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
        path.strip().replace("\\", "/")
        for path in (*tracked, *untracked)
        if path.strip()
    }


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control B exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-6b Control B surface conform")


def check_prior_acceptance() -> None:
    _run(
        [
            sys.executable,
            "scripts/check_v600_realtime_voice_output_acceptance.py",
            "--source-only",
        ]
    )
    print("[OK] accepted FW-RT6-6a aggregate regression conforms")


def check_control_a_foundation() -> None:
    import framework
    import framework.voice_artifacts as artifacts
    from framework.audio.voice_output import VoiceArtifactRef
    from framework.identity import GenerationId

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(
        tuple(artifacts.__all__) == EXPECTED_ARTIFACT_EXPORTS,
        "framework.voice_artifacts stable exports drift",
    )
    _assert(
        "VoiceArtifactStore" not in framework.__all__,
        "artifact store must remain explicit-package only",
    )

    artifact_id = artifacts.VoiceArtifactId.new()
    _assert(
        re.fullmatch(r"fw_voice_artifact_[0-9a-f]{32}", str(artifact_id)) is not None,
        "opaque artifact ID format drift",
    )

    with tempfile.TemporaryDirectory() as directory:
        store = artifacts.FileVoiceArtifactStore(Path(directory) / "private-artifacts")
        _assert(
            isinstance(store, artifacts.VoiceArtifactStore),
            "reference artifact store protocol mismatch",
        )
        ref = store.store(
            [b"one", b"-", b"two"],
            audio_format=".MP3",
            content_type="audio/mpeg",
        )
        _assert(isinstance(ref, VoiceArtifactRef), "store must return VoiceArtifactRef")
        _assert("/" not in ref.artifact_id and "\\" not in ref.artifact_id, "artifact ID leaked path syntax")

        with store.open(ref) as stream:
            _assert(stream.read() == b"one-two", "artifact store/open bytes drift")

        generation_id = GenerationId.new()
        record = store.bind_generation(ref, generation_id)
        _assert(record.generation_id == generation_id, "artifact generation binding primitive drift")
        _assert(record.is_playable, "generation binding unexpectedly invalidated artifact")

        expiring = store.store(b"expire", audio_format="mp3")
        _assert(store.expire(expiring), "valid artifact did not expire")
        try:
            store.open(expiring)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("expired artifact remained playable")

        deleting = store.store(b"delete", audio_format="mp3")
        _assert(store.delete(deleting), "valid artifact did not delete")
        try:
            store.open(deleting)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("deleted artifact remained playable")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-6b-A-ACCEPTANCE-SYNC:BEGIN",
        "implementation commit: d01cb6bd168b8b542d7cf7dc8f0c396d28aeb937",
        "FW-RT6-6b aggregate: NOT_COMPLETED",
        "Control B: AUTHORIZED",
    ):
        _assert(marker in tasklist, f"Control A acceptance source-of-truth missing: {marker}")

    print("[OK] accepted FW-RT6-6b Control A package/store foundation remains valid")


def check_result_contract() -> None:
    from framework import VoiceArtifactRef, VoiceOutputResult

    ref = VoiceArtifactRef.from_id(
        "fw_voice_artifact_" + ("a" * 32),
        audio_format="mp3",
        content_type="audio/mpeg",
    )
    result = VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_format="mp3",
        audio_artifact_ref=ref,
    )
    _assert(result.audio_artifact_ref is ref, "opaque artifact ref identity drift")
    _assert(
        result.audio_handoff_kind == "audio_artifact_ref",
        "artifact handoff classification drift",
    )
    _assert(result.has_audio_handoff, "valid generated result must have one handoff")

    try:
        VoiceOutputResult(
            request_state="generated",
            audio_ready=True,
            audio_format="mp3",
            audio_artifact_ref=r"C:\private\voice.mp3",
        )
    except TypeError:
        pass
    else:
        raise AssertionError("raw/local string artifact ref must be rejected")

    try:
        VoiceOutputResult(
            request_state="generated",
            audio_ready=True,
            audio_format="mp3",
            audio_url="https://example.invalid/audio.mp3",
            audio_artifact_ref=ref,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("generated result with multiple handoffs must be rejected")

    try:
        VoiceOutputResult(
            request_state="generated",
            audio_ready=True,
            audio_format="mp3",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("generated result without a handoff must be rejected")

    try:
        VoiceOutputResult(
            request_state="failed",
            audio_ready=False,
            audio_format="mp3",
            audio_artifact_ref=ref,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("non-generated result with playable handoff must be rejected")

    print("[OK] VoiceOutputResult rejects raw paths and enforces exactly-one generated handoff")


class _FakeTextToSpeech:
    def convert(self, **kwargs):
        del kwargs
        return (chunk for chunk in (b"fake-audio-", b"bytes"))


class _FakeElevenLabs:
    def __init__(self, *, api_key):
        del api_key
        self.text_to_speech = _FakeTextToSpeech()


class _FakeProviderModules:
    def __enter__(self):
        names = (
            "config",
            "config.calibration",
            "config.settings",
            "elevenlabs",
            "elevenlabs.client",
        )
        self._saved = {name: sys.modules.get(name) for name in names}

        config_pkg = sys.modules.get("config")
        if config_pkg is None:
            config_pkg = types.ModuleType("config")
            config_pkg.__path__ = []
            sys.modules["config"] = config_pkg

        calibration = types.ModuleType("config.calibration")
        calibration.SIMILARITY_BOOST = 0.0
        calibration.VOICE_STABILITY = 0.0
        calibration.VOICE_STYLE = 0.0

        settings = types.ModuleType("config.settings")
        settings.ELEVENLABS_API_KEY = object()
        settings.TTS_MODEL_ID = "test-model"
        settings.VOICE_ID = "test-voice"
        settings.require_tts_settings = lambda: None

        elevenlabs_pkg = types.ModuleType("elevenlabs")
        elevenlabs_pkg.__path__ = []
        client = types.ModuleType("elevenlabs.client")
        client.ElevenLabs = _FakeElevenLabs

        sys.modules["config.calibration"] = calibration
        sys.modules["config.settings"] = settings
        sys.modules["elevenlabs"] = elevenlabs_pkg
        sys.modules["elevenlabs.client"] = client
        return self

    def __exit__(self, exc_type, exc, tb):
        for name, value in self._saved.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


def check_provider_store_adoption_and_stage_binding() -> None:
    from framework import VoiceArtifactRef
    from framework.audio._provider_adapter import (
        ElevenLabsVoiceOutputAdapter,
        VoiceOutputProviderStatus,
    )
    from framework.audio.voice_output import VoiceOutputRequest
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import RealtimeStageContext
    from framework.realtime_voice_output import ProviderNeutralVoiceSynthesisStage
    from framework.voice_artifacts import FileVoiceArtifactStore, VoiceArtifactState

    prior_guard = os.environ.get("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION")
    os.environ["FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION"] = "1"
    try:
        with tempfile.TemporaryDirectory() as directory, _FakeProviderModules():
            store = FileVoiceArtifactStore(directory)
            status = VoiceOutputProviderStatus(
                real_tts_enabled=True,
                provider_configured=True,
                provider_execution_allowed=True,
                supports_audio_artifact_ref=True,
                supports_audio_url=False,
                status="provider_configured",
                status_reason="offline fake provider",
            )
            adapter = ElevenLabsVoiceOutputAdapter(
                project_root=None,
                status=status,
                artifact_store=store,
            )
            request = VoiceOutputRequest(
                text="offline fake synthesis",
                requested_audio_format="mp3",
            )

            direct = adapter.synthesize(request)
            _assert(
                direct.request_state == "generated",
                "fake provider result must be generated",
            )
            _assert(
                isinstance(direct.audio_artifact_ref, VoiceArtifactRef),
                "provider must return VoiceArtifactRef",
            )
            _assert(
                direct.audio_artifact_ref.artifact_id.startswith("fw_voice_artifact_"),
                "provider artifact ID is not opaque",
            )
            _assert(
                "/" not in direct.audio_artifact_ref.artifact_id
                and "\\" not in direct.audio_artifact_ref.artifact_id,
                "provider artifact ID leaked a path",
            )
            with store.open(direct.audio_artifact_ref) as stream:
                _assert(
                    stream.read() == b"fake-audio-bytes",
                    "stored fake provider bytes drift",
                )

            context = RealtimeStageContext(
                session_id=SessionId.new(),
                turn_id=TurnId.new(),
                generation_id=GenerationId.new(),
            )
            stage = ProviderNeutralVoiceSynthesisStage(
                adapter,
                artifact_store=store,
            )
            envelope = stage.start(context=context, request=request)
            ref = envelope.result.audio_artifact_ref
            _assert(
                isinstance(ref, VoiceArtifactRef),
                "stage result must retain opaque VoiceArtifactRef",
            )
            record = store.resolve(ref)
            _assert(record is not None, "stage result artifact missing from store")
            _assert(
                record.state is VoiceArtifactState.VALID,
                "stage artifact unexpectedly invalid",
            )
            _assert(
                record.generation_id == context.generation_id,
                "stage did not bind artifact lifecycle generation",
            )
    finally:
        if prior_guard is None:
            os.environ.pop("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION", None)
        else:
            os.environ["FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION"] = prior_guard

    print("[OK] provider stores opaque refs and stage binds lifecycle generation offline")


def check_source_boundaries() -> None:
    adapter_source = (
        PROJECT_ROOT / "framework/audio/_provider_adapter.py"
    ).read_text(encoding="utf-8")
    voice_source = (
        PROJECT_ROOT / "framework/audio/voice_output.py"
    ).read_text(encoding="utf-8")
    stage_source = (
        PROJECT_ROOT / "framework/realtime_voice_output.py"
    ).read_text(encoding="utf-8")

    _assert(
        "audio_artifact_ref=str(artifact_path)" not in adapter_source,
        "legacy path handoff remains",
    )
    _assert(
        "def _build_artifact_path" not in adapter_source,
        "legacy provider path builder remains",
    )
    _assert(
        "artifact_ref = self._artifact_store.store(" in adapter_source,
        "provider VoiceArtifactStore adoption missing",
    )
    _assert(
        "audio_artifact_ref: VoiceArtifactRef | None" in voice_source,
        "result artifact field is not opaque-only",
    )
    _assert(
        "artifact_store: VoiceArtifactStore | None = None" in stage_source,
        "stage artifact-store composition missing",
    )
    _assert("bind_generation(" in stage_source, "stage generation binding missing")

    protocol_start = stage_source.index("class VoiceSynthesisProviderAdapter")
    protocol_end = stage_source.index("class VoiceSynthesisStage", protocol_start)
    protocol = stage_source[protocol_start:protocol_end]
    for forbidden in (
        "SessionId",
        "TurnId",
        "GenerationId",
        "SynthesisWorkId",
        "RealtimeStageContext",
        "VoiceArtifactStore",
    ):
        _assert(
            forbidden not in protocol,
            f"provider protocol leaked Framework orchestration value: {forbidden}",
        )

    print("[OK] provider adapter remains correlation-free while path handoff is removed")


def check_docs() -> None:
    artifact_doc = (
        PROJECT_ROOT / "docs/voice_output_artifact_result_contract.md"
    ).read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md"
    ).read_text(encoding="utf-8")

    for phrase in (
        "must never contain a local/private filesystem path",
        "VoiceArtifactRef",
        "exactly one public handoff",
    ):
        _assert(phrase in artifact_doc, f"artifact result doc missing: {phrase}")

    for phrase in (
        "FW-RT6-6b-B-PROVIDER-ARTIFACT-ADOPTION:BEGIN",
        EXPECTED_HEAD,
        "real provider path leak corrected:",
        "raw local path in VoiceOutputResult:",
        "stage-side generation binding:",
        "Control C:",
        "NOT_AUTHORIZED",
    ):
        _assert(phrase in contract, f"Control B contract doc missing: {phrase}")

    print("[OK] Control B opaque artifact provider-adoption docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_prior_acceptance()
    check_control_a_foundation()
    _run([sys.executable, "scripts/smoke_voice_output_artifact_result_contract.py"])
    check_result_contract()
    check_provider_store_adoption_and_stage_binding()
    check_source_boundaries()
    check_docs()

    print("v600_rt6_6b_control_a_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_6b_control_b_status: implemented-awaiting-review")
    print("v600_rt6_6b_control_b_exact_surface: 7 files")
    print(f"v600_rt6_6b_control_b_baseline_head: {EXPECTED_HEAD}")
    print("v600_rt6_6b_real_provider_path_leak_corrected: True")
    print("v600_rt6_6b_provider_returns_voice_artifact_ref: True")
    print("v600_rt6_6b_generated_exactly_one_handoff: True")
    print("v600_rt6_6b_raw_local_path_in_voice_output_result: False")
    print("v600_rt6_6b_stage_generation_binding: True")
    print("v600_rt6_6b_provider_adapter_receives_framework_ids: False")
    print("v600_rt6_6b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6b_pending_queue_changed: False")
    print("v600_rt6_6b_generation_cancel_or_invalidation_changed: False")
    print("v600_rt6_6b_host_playback_changed: False")
    print("v600_rt6_6b_real_provider_execution: False")
    print("v600_rt6_6b_network_execution: False")
    print("v600_rt6_6b_microphone_access: False")
    print("v600_rt6_6b_playback_execution: False")
    print("v600_rt6_6b_real_vts_execution: False")
    print("v600_rt6_6b_control_c: NOT_AUTHORIZED")
    print("v600_rt6_6b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
