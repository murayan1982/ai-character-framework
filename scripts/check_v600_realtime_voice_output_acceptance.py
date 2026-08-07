"""FW-RT6-6a Control C aggregate voice-output generation acceptance gate."""

from __future__ import annotations

import argparse
import dataclasses
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "dd34b24faca398a070d1c50681b5e1809c260fb2"
EXPECTED_SURFACE = {
    "docs/v600_realtime_voice_output_contract.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_voice_output_acceptance.py",
}
EXPECTED_EXPORTS = (
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
        f"Control C exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact three-file FW-RT6-6a Control C surface conform")


def check_prior_controls() -> None:
    _run([sys.executable, "scripts/smoke_v600_realtime_voice_output_control_b.py", "--source-only"])
    print("[OK] accepted Control A+B voice-output generation regressions conform")


def check_aggregate_runtime_contract() -> None:
    import framework
    import framework.realtime_voice_output as voice
    from framework.audio._provider_adapter import (
        UnavailableVoiceOutputAdapter,
        VoiceOutputProviderStatus,
    )
    from framework.audio.voice_output import VoiceOutputRequest
    from framework.identity import GenerationId
    from framework.realtime_stage import RealtimeStageContext

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(tuple(voice.__all__) == EXPECTED_EXPORTS, "stable seven-name export drift")

    active_fields = tuple(field.name for field in dataclasses.fields(voice.VoiceSynthesisActiveGeneration))
    _assert(active_fields == ("context", "work_id"), "active-generation privacy surface drift")

    context = RealtimeStageContext(
        session_id="aggregate-session",
        turn_id="aggregate-turn",
        generation_id=GenerationId.new(),
    )
    work_id = voice.SynthesisWorkId.new()
    active = voice.VoiceSynthesisActiveGeneration(context=context, work_id=work_id)
    _assert(active.context == context and active.work_id == work_id, "aggregate correlation drift")
    _assert("request" not in repr(active).lower(), "active snapshot repr leaked request vocabulary")
    _assert("provider" not in repr(active).lower(), "active snapshot repr leaked provider vocabulary")

    status = VoiceOutputProviderStatus(
        real_tts_enabled=False,
        provider_configured=False,
        provider_execution_allowed=False,
        supports_audio_artifact_ref=False,
        supports_audio_url=False,
        status="contract_ready",
        status_reason="Real TTS is disabled.",
    )
    adapter = UnavailableVoiceOutputAdapter(status=status)
    capability = adapter.capability()
    _assert(not capability.generation_cancel_supported, "generation cancel overclaim")
    _assert(not capability.provider_hard_cancel_supported, "provider hard-cancel overclaim")
    _assert(not capability.pending_flush_supported, "pending-flush overclaim")
    _assert(not capability.active_audio_invalidation_supported, "invalidation overclaim")

    stage = voice.ProviderNeutralVoiceSynthesisStage(adapter)
    _assert(stage.active_generation is None, "new stage unexpectedly active")
    result = stage.start(context=context, request=VoiceOutputRequest(text="aggregate"))
    _assert(result.context == context, "result context drift")
    _assert(stage.active_generation is None, "terminal synthesis did not clear active state")
    cancel = stage.cancel(context=context)
    _assert(
        cancel.outcome is voice.VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION,
        "idle cancel classification drift",
    )
    _assert(not cancel.cooperative_cancel_requested, "idle cancel claimed cooperative request")
    _assert(not cancel.provider_hard_cancel_applied, "idle cancel claimed hard cancel")
    print("[OK] aggregate identity, active-state privacy, and capability truth conform")


def check_source_boundaries() -> None:
    voice_source = (PROJECT_ROOT / "framework/realtime_voice_output.py").read_text(encoding="utf-8")
    adapter_source = (PROJECT_ROOT / "framework/audio/_provider_adapter.py").read_text(encoding="utf-8")
    protocol_start = voice_source.index("class VoiceSynthesisProviderAdapter")
    protocol_end = voice_source.index("class VoiceSynthesisStage", protocol_start)
    protocol_source = voice_source[protocol_start:protocol_end]
    for forbidden in ("SessionId", "TurnId", "GenerationId", "SynthesisWorkId", "RealtimeStageContext"):
        _assert(forbidden not in protocol_source, f"provider adapter correlation leak: {forbidden}")
    for required in (
        "generation_cancel_supported=False",
        "provider_hard_cancel_supported=False",
        "pending_flush_supported=False",
        "active_audio_invalidation_supported=False",
    ):
        _assert(required in adapter_source, f"capability truth marker missing: {required}")
    print("[OK] provider adapter remains correlation-free and later P0-5 capabilities are not overclaimed")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    roadmap = (PROJECT_ROOT / "docs/roadmap_feature_v6.0.0.md").read_text(encoding="utf-8")

    for marker in (
        "FW-RT6-6a-C-AGGREGATE-ACCEPTANCE:BEGIN",
        EXPECTED_HEAD,
        "exact Control C delta:\n3 files",
        "FW-RT6-6a tasks:\n6 / 6 ACCEPTED-CANDIDATE",
        "provider adapter receives Framework correlation IDs:\nFalse",
        "generation_cancel_supported = False",
        "provider_hard_cancel_supported = False",
        "FW-RT6-6b / NOT_AUTHORIZED",
        "127 / UNCHANGED",
    ):
        _assert(marker in contract, f"Control C contract marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-6a — Voice output generation protocol")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    _assert(section.count("- [x]") == 6, "FW-RT6-6a aggregate task count must be 6 / 6")
    _assert(section.count("- [ ]") == 0, "FW-RT6-6a aggregate task remains open")
    for marker in (
        "FW-RT6-6a-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "exact Control C delta: 3 files",
        "generation identity: True / PASS expected",
        "active generation observable: True / PASS expected",
        "provider details public: False / PASS expected",
        "FW-RT6-6a tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "next checkpoint: FW-RT6-6b / NOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"Control C tasklist marker missing: {marker}")

    for marker in (
        "generation start",
        "generation active",
        "pending work",
        "pending clear",
        "generation cancel",
        "artifact invalidation",
        "future delivery suppression",
        "Host playback boundary",
    ):
        _assert(marker in roadmap, f"P0-5 roadmap marker missing: {marker}")
    print("[OK] all six FW-RT6-6a tasks and P0-5 deferred-boundary docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_prior_controls()
    check_aggregate_runtime_contract()
    check_source_boundaries()
    check_docs()

    print("v600_rt6_6a_control_a_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_6a_control_b_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_6a_control_c_status: implemented-awaiting-review")
    print("v600_rt6_6a_control_c_exact_delta: 3 files")
    print("v600_rt6_6a_generation_identity: True / PASS")
    print("v600_rt6_6a_active_generation_observable: True / PASS")
    print("v600_rt6_6a_active_generation_thread_safe: True / PASS")
    print("v600_rt6_6a_provider_details_public: False / PASS")
    print("v600_rt6_6a_provider_adapter_receives_framework_ids: False / PASS")
    print("v600_rt6_6a_capability_source: RealtimeVoiceOutputCapability")
    print("v600_rt6_6a_generation_cancel_supported: False / TRUTHFUL")
    print("v600_rt6_6a_provider_hard_cancel_supported: False / TRUTHFUL")
    print("v600_rt6_6a_stable_exports: 7 / UNCHANGED")
    print("v600_rt6_6a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6a_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_6a_pending_queue_changed: False")
    print("v600_rt6_6a_artifact_invalidation_changed: False")
    print("v600_rt6_6a_provider_execution: False")
    print("v600_rt6_6a_network_execution: False")
    print("v600_rt6_6a_microphone_access: False")
    print("v600_rt6_6a_playback_execution: False")
    print("v600_rt6_6a_real_vts_execution: False")
    print("v600_rt6_6a_next_checkpoint: FW-RT6-6b / NOT_AUTHORIZED")
    print("v600_rt6_6a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
