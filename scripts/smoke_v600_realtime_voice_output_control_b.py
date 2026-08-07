"""FW-RT6-6a Control B provider-adapter / active-generation adoption smoke.

Offline/mock-safe. Verifies the exact Control B surface, adoption of the stable
``VoiceSynthesisProviderAdapter`` capability contract by the existing internal
voice-output adapters, and the thread-safe provider-neutral active-generation
reference stage. No real provider, network, microphone, playback, private
configuration, artifact write, or VTube Studio execution is performed.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "5a509c9ddc18cd55dc84b264193bab973c176ee6"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/audio/_provider_adapter.py",
    "framework/realtime_voice_output.py",
    "scripts/smoke_v600_realtime_voice_output_control_b.py",
}
CONTROL_A_EXPORTS = (
    "SynthesisWorkId",
    "VoiceSynthesisResultEnvelope",
    "VoiceSynthesisActiveGeneration",
    "VoiceSynthesisCancelOutcome",
    "VoiceSynthesisCancelResult",
    "VoiceSynthesisProviderAdapter",
    "VoiceSynthesisStage",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _assert(
        completed.returncode == 0,
        "command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
    )
    return completed.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {p.strip().replace("\\", "/") for p in (*tracked, *untracked) if p.strip()}


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_BASELINE, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(actual == EXPECTED_SURFACE, f"Control B surface drift: {sorted(actual)!r}")
    print("[OK] baseline and exact six-file FW-RT6-6a Control B surface conform")


def check_stable_surface() -> None:
    import framework
    import framework.realtime_voice_output as module

    _assert(len(framework.__all__) == 127, "root-public name count drift")
    _assert(tuple(module.__all__) == CONTROL_A_EXPORTS, "Control A stable exports drift")
    _assert(
        "ProviderNeutralVoiceSynthesisStage" not in module.__all__,
        "Control B reference implementation became stable public API",
    )
    _assert(
        hasattr(module, "ProviderNeutralVoiceSynthesisStage"),
        "Control B reference stage implementation missing",
    )
    print("[OK] root 127 names and accepted seven-name stable package remain unchanged")


def check_existing_adapter_capability_adoption() -> None:
    from framework.audio._provider_adapter import (
        create_voice_output_adapter,
        resolve_provider_status,
        UnavailableVoiceOutputAdapter,
    )
    from framework.realtime_voice_output import VoiceSynthesisProviderAdapter

    status = resolve_provider_status(real_tts_enabled=False)
    unavailable = UnavailableVoiceOutputAdapter(status=status)
    _assert(isinstance(unavailable, VoiceSynthesisProviderAdapter), "unavailable adapter protocol drift")
    capability = unavailable.capability()
    _assert(not capability.runtime.configured, "disabled adapter reported configured")
    _assert(not capability.runtime.runtime_available, "disabled adapter runtime overclaim")
    _assert(not capability.generation_cancel_supported, "generation cancel overclaim")
    _assert(not capability.provider_hard_cancel_supported, "provider hard cancel overclaim")
    _assert(not capability.pending_flush_supported, "pending flush overclaim")
    _assert(not capability.active_audio_invalidation_supported, "invalidation overclaim")

    env_names = (
        "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
        "FRAMEWORK_VOICE_OUTPUT_PROVIDER",
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
    )
    saved = {name: os.environ.get(name) for name in env_names}
    before_elevenlabs = {name for name in sys.modules if name == "elevenlabs" or name.startswith("elevenlabs.")}
    try:
        os.environ["FRAMEWORK_VOICE_OUTPUT_REAL_TTS"] = "1"
        os.environ["FRAMEWORK_VOICE_OUTPUT_PROVIDER"] = "elevenlabs"
        os.environ.pop("FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION", None)
        adapter = create_voice_output_adapter(
            real_tts_enabled=None,
            project_root=None,
            artifact_dir=None,
        )
        _assert(isinstance(adapter, VoiceSynthesisProviderAdapter), "real adapter protocol drift")
        capability = adapter.capability()
        _assert(capability.runtime.configured, "configured provider lost configured fact")
        _assert(capability.runtime.guarded, "execution-guarded provider lost guarded fact")
        _assert(not capability.runtime.runtime_available, "unprobed provider runtime overclaim")
        _assert(not capability.runtime.real_runtime, "unprobed provider claimed real runtime")
        _assert(capability.audio_formats == ("mp3",), "adapter audio format capability drift")
        _assert(not capability.generation_cancel_supported, "generation cancel overclaim")
        _assert(not capability.provider_hard_cancel_supported, "hard cancel overclaim")
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    after_elevenlabs = {name for name in sys.modules if name == "elevenlabs" or name.startswith("elevenlabs.")}
    _assert(after_elevenlabs == before_elevenlabs, "capability preflight imported ElevenLabs SDK")
    print("[OK] existing voice-output adapters adopt capability() without provider execution or overclaim")


def _new_context():
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import RealtimeStageContext

    return RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )


def check_active_generation_reference_stage() -> None:
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.realtime_capabilities import RealtimeVoiceOutputCapability, RuntimeCapabilityState
    from framework.realtime_voice_output import (
        ProviderNeutralVoiceSynthesisStage,
        SynthesisWorkId,
        VoiceSynthesisCancelOutcome,
    )

    entered = threading.Event()
    release = threading.Event()

    class BlockingAdapter:
        def capability(self) -> RealtimeVoiceOutputCapability:
            return RealtimeVoiceOutputCapability(
                runtime=RuntimeCapabilityState(
                    configured=True,
                    runtime_available=True,
                    fake_runtime=True,
                    unavailable_reason=None,
                    public_metadata={"adapter": "fake"},
                ),
                audio_formats=("mp3",),
            )

        def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
            entered.set()
            _assert(release.wait(timeout=5.0), "blocking adapter was not released")
            return VoiceOutputResult(
                request_state="generated",
                audio_ready=True,
                audio_url="https://example.invalid/control-b-audio",
            )

    stage = ProviderNeutralVoiceSynthesisStage(BlockingAdapter())
    context = _new_context()
    request = VoiceOutputRequest(text="private synthesis text")
    result_box: list[object] = []
    error_box: list[BaseException] = []

    def run() -> None:
        try:
            result_box.append(stage.start(context=context, request=request))
        except BaseException as error:  # pragma: no cover - surfaced below
            error_box.append(error)

    worker = threading.Thread(target=run, name="fw-rt6-6a-control-b-smoke")
    worker.start()
    _assert(entered.wait(timeout=5.0), "synthesis did not become active")

    active = stage.active_generation
    _assert(active is not None, "active generation is not observable")
    _assert(active.context == context, "active generation context drift")
    _assert(re.fullmatch(r"fw_synthesis_[0-9a-f]{32}", str(active.work_id)) is not None, "work ID drift")
    active_repr = repr(active).lower()
    for forbidden in ("private synthesis text", "voiceoutputrequest", "artifact", "provider", "audio"):
        _assert(forbidden not in active_repr, f"active generation leaked {forbidden}")

    mismatch = stage.cancel(context=context, work_id=SynthesisWorkId.new())
    _assert(mismatch.outcome is VoiceSynthesisCancelOutcome.WORK_MISMATCH, "work mismatch drift")
    _assert(not mismatch.cooperative_cancel_requested, "work mismatch claimed cancel")
    _assert(not mismatch.provider_hard_cancel_applied, "work mismatch claimed hard cancel")

    unsupported = stage.cancel(context=context, work_id=active.work_id)
    _assert(unsupported.outcome is VoiceSynthesisCancelOutcome.UNSUPPORTED, "Control B cancel must remain unsupported")
    _assert(not unsupported.cooperative_cancel_requested, "unsupported cancel claimed cooperative request")
    _assert(not unsupported.provider_hard_cancel_applied, "unsupported cancel claimed provider hard cancel")

    try:
        stage.start(context=_new_context(), request=VoiceOutputRequest(text="second"))
    except RuntimeError as error:
        _assert("already active" in str(error).lower(), "concurrent start error drift")
    else:
        raise AssertionError("concurrent synthesis start was accepted")

    release.set()
    worker.join(timeout=5.0)
    _assert(not worker.is_alive(), "synthesis thread did not complete")
    _assert(not error_box, f"synthesis worker failed: {error_box!r}")
    _assert(len(result_box) == 1, "synthesis result missing")
    envelope = result_box[0]
    _assert(envelope.context == context, "result context drift")
    _assert(envelope.work_id == active.work_id, "result work identity drift")
    _assert(stage.active_generation is None, "active generation did not clear after completion")

    no_active = stage.cancel(context=context)
    _assert(no_active.outcome is VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION, "idle cancel drift")
    stage.close()
    stage.close()
    closed = stage.cancel(context=context)
    _assert(closed.outcome is VoiceSynthesisCancelOutcome.ALREADY_CLOSED, "closed cancel drift")
    try:
        stage.start(context=context, request=request)
    except RuntimeError as error:
        _assert("closed" in str(error).lower(), "closed start error drift")
    else:
        raise AssertionError("closed stage accepted synthesis start")

    print("[OK] thread-safe active generation is observable and clears deterministically")


def check_cancel_capability_guard() -> None:
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.realtime_capabilities import RealtimeVoiceOutputCapability
    from framework.realtime_voice_output import ProviderNeutralVoiceSynthesisStage

    class OverclaimingAdapter:
        def capability(self) -> RealtimeVoiceOutputCapability:
            return RealtimeVoiceOutputCapability(generation_cancel_supported=True)

        def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
            return VoiceOutputResult(request_state="unavailable")

    try:
        ProviderNeutralVoiceSynthesisStage(OverclaimingAdapter())
    except ValueError as error:
        _assert("does not adopt generation cancellation" in str(error), "capability guard error drift")
    else:
        raise AssertionError("Control B accepted unimplemented generation cancellation capability")
    print("[OK] Control B rejects cancellation/hard-cancel capability overclaim")


def check_legacy_session_compatibility() -> None:
    from framework import VoiceOutputRequest, create_voice_output_session

    session = create_voice_output_session(real_tts_enabled=False)
    result = session.create_output(VoiceOutputRequest(text="compatibility"))
    _assert(result.request_state == "unavailable", "legacy disabled synthesis behavior drift")
    _assert(not result.audio_ready, "legacy disabled synthesis became playable")
    session.close()
    print("[OK] existing VoiceOutputSession create_output compatibility remains unchanged")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_realtime_voice_output_protocols.py", "--source-only"],
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
        [sys.executable, "scripts/check_v600_text_chat_compatibility_acceptance.py", "--source-only"],
    ):
        _run(command)
    print("[OK] Control A/root-public/version/app SDK/FW-RT6-5c regressions conform")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    integration = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-6a-B-PROVIDER-ACTIVE-ADOPTION:BEGIN",
        EXPECTED_BASELINE,
        "ProviderNeutralVoiceSynthesisStage",
        "VoiceSynthesisProviderAdapter",
        "active_generation",
        "generation_cancel_supported = False",
        "provider_hard_cancel_supported = False",
        "FW-RT6-6d",
        "127 / UNCHANGED",
        "exact change surface: 6 files",
    ):
        _assert(marker in contract, f"Control B contract marker missing: {marker}")
    for text in (facade, integration):
        _assert("FW-RT6-6a-B-PROVIDER-ACTIVE-ADOPTION:BEGIN" in text, "Control B integration marker missing")
        _assert("active_generation" in text, "active generation documentation missing")
        _assert("127 / UNCHANGED" in text, "root-public compatibility docs missing")
    print("[OK] Control B provider-adoption/active-generation docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_stable_surface()
    check_existing_adapter_capability_adoption()
    check_active_generation_reference_stage()
    check_cancel_capability_guard()
    check_legacy_session_compatibility()
    check_regressions()
    check_docs()

    print("v600_rt6_6a_control_b_status: implemented-awaiting-review")
    print("v600_rt6_6a_control_b_exact_surface: 6 files")
    print("v600_rt6_6a_control_b_baseline_head: " + EXPECTED_BASELINE)
    print("v600_rt6_6a_control_b_provider_adapter_adoption: True")
    print("v600_rt6_6a_control_b_active_generation_observable: True")
    print("v600_rt6_6a_control_b_active_generation_thread_safe: True")
    print("v600_rt6_6a_control_b_stable_exports_changed: False")
    print("v600_rt6_6a_control_b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6a_control_b_generation_cancel_supported: False")
    print("v600_rt6_6a_control_b_provider_hard_cancel_supported: False")
    print("v600_rt6_6a_control_b_pending_queue_changed: False")
    print("v600_rt6_6a_control_b_artifact_invalidation_changed: False")
    print("v600_rt6_6a_control_b_provider_execution: False")
    print("v600_rt6_6a_control_b_network_execution: False")
    print("v600_rt6_6a_control_b_microphone_access: False")
    print("v600_rt6_6a_control_b_playback_execution: False")
    print("v600_rt6_6a_control_b_real_vts_execution: False")
    print("v600_rt6_6a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_6a_control_b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
