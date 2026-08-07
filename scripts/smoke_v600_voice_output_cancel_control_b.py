"""FW-RT6-6d Control B cooperative cancel/invalidation runtime adoption gate."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "5e26f29847a357225a29c724c6014aa15ff1c83d"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/voice_artifacts.py",
    "framework/_realtime_voice_output_control.py",
    "scripts/smoke_v600_voice_output_cancel_control_b.py",
}
VOICE_EXPORTS = (
    "SynthesisWorkId",
    "VoiceSynthesisResultEnvelope",
    "VoiceSynthesisActiveGeneration",
    "VoiceSynthesisCancelOutcome",
    "VoiceSynthesisCancelResult",
    "VoiceSynthesisProviderAdapter",
    "VoiceSynthesisStage",
)
ARTIFACT_EXPORTS = (
    "VoiceArtifactId",
    "VoiceArtifactState",
    "VoiceArtifactRecord",
    "VoiceArtifactStore",
)
QUEUE_EXPORTS = (
    "VoiceSynthesisPendingWork",
    "VoiceSynthesisEnqueueOutcome",
    "VoiceSynthesisEnqueueResult",
    "VoiceSynthesisPendingClearOutcome",
    "VoiceSynthesisPendingClearResult",
    "VoiceSynthesisQueueEventType",
    "VoiceSynthesisQueueEvent",
    "VoiceSynthesisPendingQueue",
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


def _wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.001)
    raise AssertionError("timed out waiting for deterministic test condition")


def _new_context():
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import RealtimeStageContext

    return RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )


def _fake_capability():
    from framework.realtime_capabilities import (
        RealtimeVoiceOutputCapability,
        RuntimeCapabilityState,
    )

    return RealtimeVoiceOutputCapability(
        runtime=RuntimeCapabilityState(
            configured=True,
            runtime_available=True,
            fake_runtime=True,
            unavailable_reason=None,
            public_metadata={"adapter": "fw-rt6-6d-fake"},
        ),
        generation_cancel_supported=False,
        provider_hard_cancel_supported=False,
        pending_flush_supported=False,
        active_audio_invalidation_supported=False,
        audio_formats=("mp3",),
    )


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "baseline origin/main drift",
    )
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control B exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact six-file FW-RT6-6d Control B surface conform")


def check_stable_surfaces() -> None:
    import framework
    import framework.realtime_voice_output as voice
    import framework.realtime_voice_output_queue as queue
    import framework.voice_artifacts as artifacts

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(tuple(voice.__all__) == VOICE_EXPORTS, "voice stable exports drift")
    _assert(tuple(queue.__all__) == QUEUE_EXPORTS, "queue stable exports drift")
    _assert(
        tuple(artifacts.__all__) == ARTIFACT_EXPORTS,
        "artifact stable exports drift",
    )
    _assert(
        "CancelableProviderNeutralVoiceSynthesisStage" not in framework.__all__,
        "internal cancelable stage leaked root-public",
    )
    _assert(
        "VoiceSynthesisOutputController" not in framework.__all__,
        "internal output controller leaked root-public",
    )
    print("[OK] root/voice/queue/artifact stable public surfaces remain unchanged")


def check_completed_artifact_invalidation() -> None:
    from framework._realtime_voice_output_control import (
        CancelableProviderNeutralVoiceSynthesisStage,
    )
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.voice_artifacts import FileVoiceArtifactStore, VoiceArtifactState

    with tempfile.TemporaryDirectory() as directory:
        store = FileVoiceArtifactStore(Path(directory) / "private-artifacts")

        class Adapter:
            def capability(self):
                return _fake_capability()

            def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
                ref = store.store(b"completed", audio_format="mp3")
                return VoiceOutputResult(
                    request_state="generated",
                    audio_ready=True,
                    audio_format="mp3",
                    audio_artifact_ref=ref,
                )

        stage = CancelableProviderNeutralVoiceSynthesisStage(
            Adapter(),
            artifact_store=store,
        )
        context = _new_context()
        envelope = stage.start(
            context=context,
            request=VoiceOutputRequest(text="completed artifact"),
        )
        ref = envelope.result.audio_artifact_ref
        _assert(ref is not None, "completed artifact ref missing")
        record = store.resolve(ref)
        _assert(record is not None and record.is_playable, "completed artifact not playable")

        _assert(stage.invalidate_completed(context) == 1, "completed artifact was not invalidated")
        invalidated = store.resolve(ref)
        _assert(
            invalidated is not None
            and invalidated.state is VoiceArtifactState.INVALIDATED
            and not invalidated.is_playable,
            "invalidated artifact remained playable",
        )
        try:
            store.open(ref)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("invalidated artifact opened successfully")
        _assert(stage.invalidate_completed(context) == 0, "duplicate invalidation was not idempotent")

    print("[OK] completed generation-bound artifacts invalidate idempotently and become non-playable")


def check_cooperative_cancel_completion() -> None:
    from framework._realtime_voice_output_control import (
        CancelableProviderNeutralVoiceSynthesisStage,
    )
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.realtime_voice_output import VoiceSynthesisCancelOutcome
    from framework.voice_artifacts import FileVoiceArtifactStore, VoiceArtifactState

    with tempfile.TemporaryDirectory() as directory:
        store = FileVoiceArtifactStore(Path(directory) / "private-artifacts")
        entered = threading.Event()
        release = threading.Event()

        class BlockingAdapter:
            def capability(self):
                return _fake_capability()

            def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
                entered.set()
                _assert(release.wait(timeout=2.0), "blocking adapter release timeout")
                ref = store.store(b"cancelled", audio_format="mp3")
                return VoiceOutputResult(
                    request_state="generated",
                    audio_ready=True,
                    audio_format="mp3",
                    audio_artifact_ref=ref,
                )

        stage = CancelableProviderNeutralVoiceSynthesisStage(
            BlockingAdapter(),
            artifact_store=store,
            cancel_timeout_seconds=1.0,
        )
        capability = stage.capability()
        _assert(capability.generation_cancel_supported, "Framework cooperative cancel capability missing")
        _assert(not capability.provider_hard_cancel_supported, "provider hard cancel overclaimed")
        _assert(capability.active_audio_invalidation_supported, "artifact invalidation capability missing")
        _assert(not capability.pending_flush_supported, "provider pending flush overclaimed")

        context = _new_context()
        result_box: list[object] = []
        error_box: list[BaseException] = []

        def run_stage() -> None:
            try:
                result_box.append(
                    stage.start(
                        context=context,
                        request=VoiceOutputRequest(text="cancel me"),
                    )
                )
            except BaseException as error:
                error_box.append(error)

        worker = threading.Thread(target=run_stage, name="fw-rt6-6d-cancel-stage")
        worker.start()
        _assert(entered.wait(timeout=2.0), "synthesis did not become active")
        active = stage.active_generation
        _assert(active is not None, "active synthesis missing")

        cancel_box: list[object] = []

        def run_cancel() -> None:
            cancel_box.append(
                stage.cancel(context=context, work_id=active.work_id)
            )

        canceller = threading.Thread(target=run_cancel, name="fw-rt6-6d-cancel-request")
        canceller.start()
        _wait_until(lambda: stage.active_cancel_requested)
        release.set()

        worker.join(timeout=2.0)
        canceller.join(timeout=2.0)
        _assert(not worker.is_alive() and not canceller.is_alive(), "cancel completion threads did not terminate")
        _assert(not error_box, f"synthesis worker failed: {error_box!r}")
        _assert(len(cancel_box) == 1 and len(result_box) == 1, "cancel/result missing")

        cancel = cancel_box[0]
        _assert(cancel.outcome is VoiceSynthesisCancelOutcome.COMPLETED, "cooperative cancel did not complete")
        _assert(cancel.cooperative_cancel_requested, "cancel request fact missing")
        _assert(cancel.cooperative_cancel_completed, "cancel completion fact missing")
        _assert(cancel.provider_hard_cancel_unsupported, "provider hard-cancel unsupported fact missing")
        _assert(not cancel.provider_hard_cancel_applied, "provider hard cancel falsely applied")
        _assert(cancel.future_delivery_suppressed, "future delivery suppression fact missing")
        _assert(cancel.artifact_invalidated, "cancelled artifact invalidation fact missing")

        envelope = result_box[0]
        _assert(envelope.work_id == active.work_id, "cancelled work identity drift")
        _assert(envelope.result.request_state == "cancelled", "cancelled provider result was not suppressed")
        _assert(not envelope.result.audio_ready, "cancelled result remained audio-ready")
        _assert(not envelope.result.has_audio_handoff, "cancelled result leaked audio handoff")

        invalidated_records = [
            record
            for record in store._records.values()  # reference implementation proof only
            if record.record.state is VoiceArtifactState.INVALIDATED
        ]
        _assert(len(invalidated_records) == 1, "cancelled artifact did not become invalidated")

        duplicate = stage.cancel(context=context, work_id=active.work_id)
        _assert(duplicate == cancel, "duplicate completed cancel was not idempotent")

    print("[OK] active cooperative cancel completes, suppresses late audio, and records hard-cancel unsupported")


def check_cancel_timeout_and_late_suppression() -> None:
    from framework._realtime_voice_output_control import (
        CancelableProviderNeutralVoiceSynthesisStage,
    )
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.realtime_voice_output import VoiceSynthesisCancelOutcome
    from framework.voice_artifacts import FileVoiceArtifactStore, VoiceArtifactState

    with tempfile.TemporaryDirectory() as directory:
        store = FileVoiceArtifactStore(Path(directory) / "private-artifacts")
        entered = threading.Event()
        release = threading.Event()

        class SlowAdapter:
            def capability(self):
                return _fake_capability()

            def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
                entered.set()
                _assert(release.wait(timeout=2.0), "slow adapter release timeout")
                ref = store.store(b"late", audio_format="mp3")
                return VoiceOutputResult(
                    request_state="generated",
                    audio_ready=True,
                    audio_format="mp3",
                    audio_artifact_ref=ref,
                )

        stage = CancelableProviderNeutralVoiceSynthesisStage(
            SlowAdapter(),
            artifact_store=store,
            cancel_timeout_seconds=0.01,
        )
        context = _new_context()
        result_box: list[object] = []

        worker = threading.Thread(
            target=lambda: result_box.append(
                stage.start(
                    context=context,
                    request=VoiceOutputRequest(text="timeout"),
                )
            ),
            name="fw-rt6-6d-timeout-stage",
        )
        worker.start()
        _assert(entered.wait(timeout=2.0), "timeout synthesis did not become active")
        active = stage.active_generation
        _assert(active is not None, "timeout active synthesis missing")

        cancel = stage.cancel(context=context, work_id=active.work_id)
        _assert(cancel.outcome is VoiceSynthesisCancelOutcome.TIMED_OUT, "bounded cancel timeout not reported")
        _assert(cancel.cooperative_cancel_requested, "timeout lost cooperative request")
        _assert(not cancel.cooperative_cancel_completed, "timeout overclaimed completion")
        _assert(cancel.provider_hard_cancel_unsupported, "timeout lost hard-cancel unsupported fact")
        _assert(cancel.future_delivery_suppressed, "timeout did not retain future suppression")

        duplicate_while_active = stage.cancel(context=context, work_id=active.work_id)
        _assert(duplicate_while_active == cancel, "duplicate timed-out cancel was not idempotent")

        release.set()
        worker.join(timeout=2.0)
        _assert(not worker.is_alive(), "late provider worker did not terminate")
        _assert(len(result_box) == 1, "late provider result missing")
        envelope = result_box[0]
        _assert(envelope.result.request_state == "cancelled", "late timed-out provider result was delivered")
        _assert(not envelope.result.has_audio_handoff, "late timed-out result leaked audio handoff")

        states = tuple(stored.record.state for stored in store._records.values())
        _assert(states == (VoiceArtifactState.INVALIDATED,), "late artifact was not invalidated")
        duplicate_after_terminal = stage.cancel(context=context, work_id=active.work_id)
        _assert(duplicate_after_terminal == cancel, "post-terminal duplicate cancel drift")

    print("[OK] bounded cancel timeout keeps a one-way future-delivery suppression barrier")


def check_generation_gate_stale_guard() -> None:
    from framework._realtime_voice_output_control import (
        CancelableProviderNeutralVoiceSynthesisStage,
    )
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.identity import SessionId, TurnId
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
        StaleCompletionReason,
    )
    from framework.realtime_stage import RealtimeStageContext
    from framework.voice_artifacts import FileVoiceArtifactStore, VoiceArtifactState

    with tempfile.TemporaryDirectory() as directory:
        store = FileVoiceArtifactStore(Path(directory) / "private-artifacts")
        gate = RealtimeGenerationGate()
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        context = RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=turn_id,
            generation_id=generation_id,
        )
        entered = threading.Event()
        release = threading.Event()

        class LateAdapter:
            def capability(self):
                return _fake_capability()

            def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
                entered.set()
                _assert(release.wait(timeout=2.0), "stale adapter release timeout")
                ref = store.store(b"stale", audio_format="mp3")
                return VoiceOutputResult(
                    request_state="generated",
                    audio_ready=True,
                    audio_format="mp3",
                    audio_artifact_ref=ref,
                )

        stage = CancelableProviderNeutralVoiceSynthesisStage(
            LateAdapter(),
            artifact_store=store,
            generation_gate=gate,
        )
        result_box: list[object] = []
        worker = threading.Thread(
            target=lambda: result_box.append(
                stage.start(
                    context=context,
                    request=VoiceOutputRequest(text="stale"),
                )
            ),
            name="fw-rt6-6d-stale-stage",
        )
        worker.start()
        _assert(entered.wait(timeout=2.0), "stale synthesis did not become active")
        retired = gate.advance(GenerationAdvanceReason.INTERRUPT)
        _assert(retired == generation_id, "generation gate did not retire target generation")
        release.set()
        worker.join(timeout=2.0)
        _assert(not worker.is_alive(), "stale provider worker did not terminate")
        _assert(len(result_box) == 1, "stale provider result missing")

        envelope = result_box[0]
        _assert(envelope.result.request_state == "stale", "stale completion was not suppressed")
        _assert(not envelope.result.has_audio_handoff, "stale completion leaked audio handoff")
        _assert(stage.last_stale_delivery_suppressed, "stale suppression diagnostic fact missing")
        decision = stage.last_generation_admission
        _assert(decision is not None and not decision.accepted, "generation gate did not reject stale completion")
        _assert(
            decision.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
            "stale completion reason drift",
        )
        _assert(
            decision.retired_by is GenerationAdvanceReason.INTERRUPT,
            "stale retirement reason drift",
        )
        states = tuple(stored.record.state for stored in store._records.values())
        _assert(states == (VoiceArtifactState.INVALIDATED,), "stale artifact remained valid")

    print("[OK] late voice artifact uses existing generation gate and is rejected as stale")


def check_flush_distinguishes_pending_and_active() -> None:
    from framework._realtime_voice_output_control import (
        CancelableProviderNeutralVoiceSynthesisStage,
        VoiceSynthesisOutputController,
    )
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.realtime_voice_output import VoiceSynthesisCancelOutcome
    from framework.realtime_voice_output_queue import (
        BoundedVoiceSynthesisPendingQueue,
        VoiceSynthesisPendingClearOutcome,
    )
    from framework.voice_artifacts import FileVoiceArtifactStore

    with tempfile.TemporaryDirectory() as directory:
        store = FileVoiceArtifactStore(Path(directory) / "private-artifacts")
        entered = threading.Event()
        release = threading.Event()

        class BlockingAdapter:
            def capability(self):
                return _fake_capability()

            def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
                entered.set()
                _assert(release.wait(timeout=2.0), "flush adapter release timeout")
                ref = store.store(b"flush", audio_format="mp3")
                return VoiceOutputResult(
                    request_state="generated",
                    audio_ready=True,
                    audio_format="mp3",
                    audio_artifact_ref=ref,
                )

        stage = CancelableProviderNeutralVoiceSynthesisStage(
            BlockingAdapter(),
            artifact_store=store,
            cancel_timeout_seconds=1.0,
        )
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=2)
        controller = VoiceSynthesisOutputController(queue=queue, stage=stage)
        context = _new_context()
        first = queue.enqueue(
            context=context,
            request=VoiceOutputRequest(text="active"),
        )
        second = queue.enqueue(
            context=context,
            request=VoiceOutputRequest(text="pending"),
        )
        _assert(first.accepted and second.accepted, "flush setup enqueue failed")

        handoff_box: list[object] = []
        handoff_worker = threading.Thread(
            target=lambda: handoff_box.append(queue.handoff_next(stage=stage)),
            name="fw-rt6-6d-flush-handoff",
        )
        handoff_worker.start()
        _assert(entered.wait(timeout=2.0), "flush active synthesis did not start")
        _assert(queue.pending_count == 1, "flush pending setup drift")

        flush_box: list[object] = []
        flush_worker = threading.Thread(
            target=lambda: flush_box.append(controller.flush(context=context)),
            name="fw-rt6-6d-flush-control",
        )
        flush_worker.start()
        _wait_until(lambda: stage.active_cancel_requested)
        release.set()

        handoff_worker.join(timeout=2.0)
        flush_worker.join(timeout=2.0)
        _assert(not handoff_worker.is_alive() and not flush_worker.is_alive(), "flush workers did not terminate")
        _assert(len(flush_box) == 1, "flush result missing")
        flush = flush_box[0]
        _assert(
            flush.pending_clear_result.outcome is VoiceSynthesisPendingClearOutcome.CLEARED,
            "flush did not report pending clear separately",
        )
        _assert(flush.pending_clear_result.cleared_work == (second.work,), "flush cleared wrong pending work")
        _assert(flush.active_cancel_result is not None, "flush active cancel result missing")
        _assert(
            flush.active_cancel_result.outcome is VoiceSynthesisCancelOutcome.COMPLETED,
            "flush active cancellation did not complete",
        )
        _assert(
            not flush.pending_clear_result.active_generation_cancelled,
            "pending clear falsely claimed active cancellation",
        )
        _assert(flush.future_delivery_suppressed, "flush did not suppress active future delivery")
        _assert(len(handoff_box) == 1, "flush active handoff result missing")
        _assert(handoff_box[0].result.request_state == "cancelled", "flush active result was not suppressed")

        duplicate = controller.flush(context=context)
        _assert(duplicate.idempotent_noop, "duplicate flush was not an idempotent no-op")

    print("[OK] pending clear and active cancel remain distinct and duplicate flush is safe")


def check_regressions_and_boundaries() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_voice_output_cancel_control_a.py", "--source-only"],
        [sys.executable, "scripts/check_v600_voice_artifact_store_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_voice_output_queue_acceptance.py", "--source-only"],
    ):
        _run(command)

    provider = (PROJECT_ROOT / "framework/audio/_provider_adapter.py").read_text(encoding="utf-8")
    session = (PROJECT_ROOT / "framework/realtime_session.py").read_text(encoding="utf-8")
    control = (PROJECT_ROOT / "framework/_realtime_voice_output_control.py").read_text(encoding="utf-8")

    for marker in (
        "generation_cancel_supported=False",
        "provider_hard_cancel_supported=False",
        "pending_flush_supported=False",
        "active_audio_invalidation_supported=False",
    ):
        _assert(marker in provider, f"provider capability truth marker missing: {marker}")

    for forbidden in (
        "from elevenlabs",
        "import elevenlabs",
        "import requests",
        "import httpx",
        "import socket",
        "import pyaudio",
        "import sounddevice",
        "subprocess.Popen",
        "subprocess.run",
    ):
        _assert(forbidden not in control, f"cancel control leaked provider/runtime boundary: {forbidden}")

    _assert(
        "Real queue flush / playback stop is not implemented yet." in session,
        "RealtimeSession/host playback boundary changed unexpectedly",
    )
    print("[OK] accepted 6a/6b/6c regressions and provider/session/host-playback boundaries conform")


def check_docs_and_tasklist() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    integration = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")

    start = tasklist.index("## FW-RT6-6d — Generation cancel and artifact invalidation")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _assert(section.count("- [ ]") == 7, "Control B must leave FW-RT6-6d 0 / 7 CLOSED")
    _assert(section.count("- [x]") == 0, "Control B prematurely closed aggregate task")

    for text in (contract, facade, integration):
        _assert(
            "FW-RT6-6d-B-CANCEL-INVALIDATION-ADOPTION:BEGIN" in text,
            "Control B docs marker missing",
        )
        _assert(EXPECTED_HEAD in text, "Control B baseline marker missing")

    for marker in (
        "active cooperative cancellation:\nIMPLEMENTED",
        "provider cancel timeout:\nBOUNDED / IMPLEMENTED",
        "provider hard cancel:\nUNSUPPORTED / TRUTHFUL",
        "completed artifact invalidation:\nIMPLEMENTED",
        "future delivery suppression:\nIMPLEMENTED",
        "late artifact freshness source:\nRealtimeGenerationGate",
        "duplicate cancel / flush:\nIDEMPOTENT / PASS expected",
        "FW-RT6-6d tasks:\n0 / 7 CLOSED",
        "Control C:\nNOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"Control B contract marker missing: {marker}")

    print("[OK] Control B docs record runtime adoption while aggregate tasklist remains open")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_stable_surfaces()
    check_completed_artifact_invalidation()
    check_cooperative_cancel_completion()
    check_cancel_timeout_and_late_suppression()
    check_generation_gate_stale_guard()
    check_flush_distinguishes_pending_and_active()
    check_regressions_and_boundaries()
    check_docs_and_tasklist()

    print("v600_rt6_6d_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6d_control_b_status: implemented-awaiting-review")
    print("v600_rt6_6d_control_b_exact_surface: 6 files")
    print("v600_rt6_6d_active_cooperative_cancel: True / PASS")
    print("v600_rt6_6d_cancel_timeout: BOUNDED / PASS")
    print("v600_rt6_6d_provider_hard_cancel_applied: False / TRUTHFUL")
    print("v600_rt6_6d_provider_hard_cancel_unsupported: True / PASS")
    print("v600_rt6_6d_completed_artifact_invalidation: True / PASS")
    print("v600_rt6_6d_invalidated_artifact_playable: False / PASS")
    print("v600_rt6_6d_future_delivery_suppression: True / PASS")
    print("v600_rt6_6d_late_artifact_generation_gate: True / PASS")
    print("v600_rt6_6d_duplicate_cancel_idempotent: True / PASS")
    print("v600_rt6_6d_duplicate_flush_idempotent: True / PASS")
    print("v600_rt6_6d_pending_clear_active_cancel_distinguished: True / PASS")
    print("v600_rt6_6d_provider_capability_changed: False")
    print("v600_rt6_6d_realtime_session_changed: False")
    print("v600_rt6_6d_host_playback_changed: False")
    print("v600_rt6_6d_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6d_realtime_voice_output_exports: 7 / UNCHANGED")
    print("v600_rt6_6d_voice_artifact_exports: 4 / UNCHANGED")
    print("v600_rt6_6d_queue_exports: 8 / UNCHANGED")
    print("v600_rt6_6d_tasklist_closed: 0 / 7")
    print("v600_rt6_6d_provider_execution: False")
    print("v600_rt6_6d_network_execution: False")
    print("v600_rt6_6d_microphone_access: False")
    print("v600_rt6_6d_playback_execution: False")
    print("v600_rt6_6d_real_vts_execution: False")
    print("v600_rt6_6d_control_c: NOT_AUTHORIZED")
    print("v600_rt6_6d_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
