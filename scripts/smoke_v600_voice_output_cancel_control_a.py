"""FW-RT6-6d Control A typed voice-synthesis cancellation-result gate."""

from __future__ import annotations

import argparse
from dataclasses import fields
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "3613056b798bd0a46ecee87a252ed5f36156a67d"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/realtime_voice_output.py",
    "scripts/smoke_v600_realtime_voice_output_protocols.py",
    "scripts/smoke_v600_voice_output_cancel_control_a.py",
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
        text=True,
        capture_output=True,
        check=False,
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


def _new_context():
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import RealtimeStageContext

    return RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control A exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact six-file FW-RT6-6d Control A surface conform")


def check_stable_surface() -> None:
    import framework
    import framework.realtime_voice_output as voice

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(tuple(voice.__all__) == EXPECTED_EXPORTS, "stable voice export drift")
    for name in EXPECTED_EXPORTS:
        _assert(name not in framework.__all__, f"voice synthesis name leaked root-public: {name}")
    print("[OK] root 127 and seven-name stable voice package remain unchanged")


def check_cancel_model() -> None:
    from framework.realtime_voice_output import (
        SynthesisWorkId,
        VoiceSynthesisCancelOutcome,
        VoiceSynthesisCancelResult,
    )

    expected_outcomes = (
        "REQUESTED",
        "COMPLETED",
        "TIMED_OUT",
        "NO_ACTIVE_GENERATION",
        "WORK_MISMATCH",
        "ALREADY_TERMINAL",
        "UNSUPPORTED",
        "ALREADY_CLOSED",
        "FAILED",
    )
    _assert(
        tuple(item.name for item in VoiceSynthesisCancelOutcome) == expected_outcomes,
        "cancel outcome vocabulary drift",
    )
    expected_fields = (
        "outcome",
        "context",
        "work_id",
        "cooperative_cancel_requested",
        "cooperative_cancel_completed",
        "provider_hard_cancel_applied",
        "provider_hard_cancel_unsupported",
        "artifact_invalidated",
        "future_delivery_suppressed",
        "safe_message",
        "retryable",
        "public_metadata",
    )
    _assert(
        tuple(field.name for field in fields(VoiceSynthesisCancelResult)) == expected_fields,
        "cancel result field surface drift",
    )

    context = _new_context()
    work_id = SynthesisWorkId.new()

    requested = VoiceSynthesisCancelResult(
        outcome=VoiceSynthesisCancelOutcome.REQUESTED,
        context=context,
        work_id=work_id,
        cooperative_cancel_requested=True,
    )
    _assert(requested.cooperative_cancel_requested, "REQUESTED lost request fact")
    _assert(not requested.cooperative_cancel_completed, "REQUESTED overclaimed completion")

    completed = VoiceSynthesisCancelResult(
        outcome=VoiceSynthesisCancelOutcome.COMPLETED,
        context=context,
        work_id=work_id,
        cooperative_cancel_requested=True,
        cooperative_cancel_completed=True,
        provider_hard_cancel_unsupported=True,
        artifact_invalidated=True,
        future_delivery_suppressed=True,
        public_metadata={"api_key": "private-secret", "reason": "safe"},
    )
    _assert(completed.cooperative_cancel_completed, "COMPLETED lost completion fact")
    _assert(completed.provider_hard_cancel_unsupported, "unsupported hard cancel fact lost")
    _assert(completed.artifact_invalidated, "artifact invalidation fact lost")
    _assert(completed.future_delivery_suppressed, "future suppression fact lost")
    _assert("private-secret" not in repr(dict(completed.public_metadata)), "cancel metadata leaked secret")

    timed_out = VoiceSynthesisCancelResult(
        outcome=VoiceSynthesisCancelOutcome.TIMED_OUT,
        context=context,
        work_id=work_id,
        cooperative_cancel_requested=True,
        provider_hard_cancel_unsupported=True,
        future_delivery_suppressed=True,
    )
    _assert(not timed_out.cooperative_cancel_completed, "TIMED_OUT overclaimed completion")

    valid_hard_cancel = VoiceSynthesisCancelResult(
        outcome=VoiceSynthesisCancelOutcome.COMPLETED,
        context=context,
        work_id=work_id,
        cooperative_cancel_requested=True,
        cooperative_cancel_completed=True,
        provider_hard_cancel_applied=True,
        future_delivery_suppressed=True,
    )
    _assert(valid_hard_cancel.provider_hard_cancel_applied, "hard-cancel applied fact lost")
    _assert(
        not valid_hard_cancel.provider_hard_cancel_unsupported,
        "hard-cancel applied also claimed unsupported",
    )

    invalid_kwargs = (
        {
            "outcome": VoiceSynthesisCancelOutcome.REQUESTED,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.REQUESTED,
            "cooperative_cancel_requested": True,
            "cooperative_cancel_completed": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.COMPLETED,
            "cooperative_cancel_requested": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.TIMED_OUT,
            "cooperative_cancel_requested": True,
            "cooperative_cancel_completed": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.FAILED,
            "provider_hard_cancel_applied": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.FAILED,
            "provider_hard_cancel_unsupported": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.FAILED,
            "cooperative_cancel_requested": True,
            "provider_hard_cancel_applied": True,
            "provider_hard_cancel_unsupported": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.FAILED,
            "cooperative_cancel_requested": True,
            "artifact_invalidated": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.UNSUPPORTED,
            "cooperative_cancel_requested": True,
        },
        {
            "outcome": VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION,
            "future_delivery_suppressed": True,
        },
    )
    for kwargs in invalid_kwargs:
        try:
            VoiceSynthesisCancelResult(
                context=context,
                work_id=work_id,
                **kwargs,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid cancel-result combination accepted: {kwargs!r}")

    print("[OK] REQUESTED/COMPLETED/TIMED_OUT and cancellation-effect invariants conform")


def check_control_a_non_adoption() -> None:
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.realtime_capabilities import RealtimeVoiceOutputCapability
    from framework.realtime_voice_output import (
        ProviderNeutralVoiceSynthesisStage,
        VoiceSynthesisCancelOutcome,
    )

    class NoExecutionAdapter:
        def capability(self) -> RealtimeVoiceOutputCapability:
            return RealtimeVoiceOutputCapability()

        def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
            raise AssertionError("Control A gate must not execute synthesis")

    stage = ProviderNeutralVoiceSynthesisStage(NoExecutionAdapter())
    context = _new_context()
    idle = stage.cancel(context=context)
    _assert(
        idle.outcome is VoiceSynthesisCancelOutcome.NO_ACTIVE_GENERATION,
        "idle cancel classification drift",
    )

    active = stage._claim_generation(  # reference-only proof; no provider execution
        context=context,
        work_id="fw_synthesis_" + ("a" * 32),
    )
    unsupported = stage.cancel(context=context, work_id=active.work_id)
    _assert(
        unsupported.outcome is VoiceSynthesisCancelOutcome.UNSUPPORTED,
        "Control A adopted active cancellation execution",
    )
    for field_name in (
        "cooperative_cancel_requested",
        "cooperative_cancel_completed",
        "provider_hard_cancel_applied",
        "provider_hard_cancel_unsupported",
        "artifact_invalidated",
        "future_delivery_suppressed",
    ):
        _assert(not getattr(unsupported, field_name), f"UNSUPPORTED overclaimed {field_name}")
    stage._release_generation(active.work_id)

    capability = stage.capability()
    _assert(not capability.generation_cancel_supported, "generation cancel capability changed")
    _assert(not capability.provider_hard_cancel_supported, "provider hard-cancel capability changed")
    _assert(not capability.active_audio_invalidation_supported, "artifact invalidation capability changed")
    _assert(not capability.pending_flush_supported, "provider pending flush capability changed")
    print("[OK] concrete stage/provider capability remain non-adopted in Control A")


def check_tasklist_and_docs() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    integration = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")

    start = tasklist.index("## FW-RT6-6d — Generation cancel and artifact invalidation")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _assert(section.count("- [ ]") == 7, "FW-RT6-6d must remain 0 / 7 CLOSED in Control A")
    _assert(section.count("- [x]") == 0, "Control A closed FW-RT6-6d aggregate task")

    for text in (contract, facade, integration):
        _assert(
            "FW-RT6-6d-A-TYPED-CANCEL-RESULT:BEGIN" in text,
            "Control A docs marker missing",
        )
        _assert(EXPECTED_HEAD in text, "Control A baseline marker missing")

    for marker in (
        "VoiceSynthesisCancelOutcome additions:",
        "COMPLETED",
        "TIMED_OUT",
        "provider_hard_cancel_unsupported",
        "artifact_invalidated",
        "future_delivery_suppressed",
        "FW-RT6-6d tasklist:\n0 / 7 CLOSED",
        "Control B:\nNOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"Control A contract marker missing: {marker}")

    print("[OK] Control A docs record typed foundation while tasklist stays 0 / 7")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_realtime_voice_output_protocols.py", "--source-only"],
        [sys.executable, "scripts/check_v600_realtime_voice_output_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_voice_output_queue_acceptance.py", "--source-only"],
    ):
        _run(command)
    print("[OK] accepted FW-RT6-6a and FW-RT6-6c regressions conform")


def check_source_boundaries() -> None:
    provider = (PROJECT_ROOT / "framework/audio/_provider_adapter.py").read_text(encoding="utf-8")
    queue = (PROJECT_ROOT / "framework/realtime_voice_output_queue.py").read_text(encoding="utf-8")
    artifacts = (PROJECT_ROOT / "framework/voice_artifacts.py").read_text(encoding="utf-8")
    session = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")

    for marker in (
        "generation_cancel_supported=False",
        "provider_hard_cancel_supported=False",
        "pending_flush_supported=False",
        "active_audio_invalidation_supported=False",
    ):
        _assert(marker in provider, f"provider capability truth marker missing: {marker}")

    _assert("class VoiceSynthesisPendingQueue" in queue, "accepted queue source missing")
    _assert("class VoiceArtifactStore" in artifacts, "accepted artifact store missing")
    _assert("def _interrupt_serialized(" in session, "accepted realtime interrupt boundary missing")
    print("[OK] provider/queue/artifact/session runtime boundaries remain source-unchanged")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_stable_surface()
    check_cancel_model()
    check_control_a_non_adoption()
    check_tasklist_and_docs()
    check_regressions()
    check_source_boundaries()

    print("v600_rt6_6d_control_a_status: implemented-awaiting-review")
    print("v600_rt6_6d_control_a_exact_surface: 6 files")
    print("v600_rt6_6d_cancel_outcomes: REQUESTED / COMPLETED / TIMED_OUT / typed non-cancel outcomes")
    print("v600_rt6_6d_cooperative_cancel_completed_model: True / PASS")
    print("v600_rt6_6d_provider_hard_cancel_applied_unsupported_distinguished: True / PASS")
    print("v600_rt6_6d_artifact_invalidation_result_fact: True / PASS")
    print("v600_rt6_6d_future_delivery_suppression_result_fact: True / PASS")
    print("v600_rt6_6d_active_cancel_execution_changed: False")
    print("v600_rt6_6d_provider_cancel_timeout_execution_changed: False")
    print("v600_rt6_6d_provider_hard_cancel_execution_changed: False")
    print("v600_rt6_6d_artifact_invalidation_execution_changed: False")
    print("v600_rt6_6d_future_delivery_suppression_execution_changed: False")
    print("v600_rt6_6d_realtime_session_changed: False")
    print("v600_rt6_6d_pending_queue_changed: False")
    print("v600_rt6_6d_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6d_realtime_voice_output_exports: 7 / UNCHANGED")
    print("v600_rt6_6d_tasklist_closed: 0 / 7")
    print("v600_rt6_6d_provider_execution: False")
    print("v600_rt6_6d_network_execution: False")
    print("v600_rt6_6d_microphone_access: False")
    print("v600_rt6_6d_playback_execution: False")
    print("v600_rt6_6d_real_vts_execution: False")
    print("v600_rt6_6d_control_b: NOT_AUTHORIZED")
    print("v600_rt6_6d_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
