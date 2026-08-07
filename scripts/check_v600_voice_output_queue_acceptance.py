"""FW-RT6-6c Control C aggregate bounded voice-output queue acceptance gate."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import subprocess
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "647191b7b939587c9977279dd446e16e90bfb4b3"
EXPECTED_SURFACE = {
    "docs/v600_realtime_voice_output_contract.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_voice_output_queue_acceptance.py",
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


def _load_script(module_name: str, relative_path: str):
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    _assert(spec is not None and spec.loader is not None, f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control C exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact three-file FW-RT6-6c Control C surface conform")


def check_stable_surfaces() -> None:
    import framework
    import framework.realtime_voice_output as voice
    import framework.realtime_voice_output_queue as queue

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(tuple(voice.__all__) == VOICE_EXPORTS, "voice stable exports drift")
    _assert(tuple(queue.__all__) == QUEUE_EXPORTS, "queue stable exports drift")
    _assert(
        "ProviderNeutralVoiceSynthesisStage" not in voice.__all__,
        "concrete synthesis stage became stable public API",
    )
    _assert(
        "BoundedVoiceSynthesisPendingQueue" not in queue.__all__,
        "concrete pending queue became stable public API",
    )
    stage_sig = inspect.signature(voice.VoiceSynthesisStage.start)
    _assert(tuple(stage_sig.parameters) == ("self", "context", "request"), "stable stage start signature drift")
    _assert("work_id" not in stage_sig.parameters, "stable stage protocol gained handoff work_id")
    _assert(
        "handoff_next" not in queue.VoiceSynthesisPendingQueue.__dict__,
        "stable pending protocol gained execution responsibility",
    )
    print("[OK] root/voice/queue stable surfaces remain unchanged")


def check_control_a_and_b_regressions() -> None:
    control_a = _load_script(
        "fw_rt6_6c_control_a_gate",
        "scripts/smoke_v600_voice_output_queue_control_a.py",
    )
    control_b = _load_script(
        "fw_rt6_6c_control_b_gate",
        "scripts/smoke_v600_voice_output_queue_control_b.py",
    )

    # Do not call historical docs/git-surface checks: Control C intentionally
    # closes the aggregate tasklist while runtime behavior must stay unchanged.
    control_a.check_queue_contract()
    control_a.check_source_boundaries()
    control_b.check_stable_surfaces()
    control_b.check_same_work_id_handoff()
    control_b.check_claim_rejection_preserves_pending()
    control_b.check_execution_failure_is_not_requeued()
    print("[OK] accepted Control A bounded-queue and Control B handoff regressions conform")



def check_aggregate_active_pending_capacity() -> None:
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_capabilities import RealtimeVoiceOutputCapability, RuntimeCapabilityState
    from framework.realtime_stage import RealtimeStageContext
    from framework.realtime_voice_output import ProviderNeutralVoiceSynthesisStage
    from framework.realtime_voice_output_queue import (
        BoundedVoiceSynthesisPendingQueue,
        VoiceSynthesisEnqueueOutcome,
        VoiceSynthesisPendingClearOutcome,
    )

    def context() -> RealtimeStageContext:
        return RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
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
                    public_metadata={"adapter": "aggregate-fake"},
                ),
                audio_formats=("mp3",),
            )

        def synthesize(self, request: VoiceOutputRequest) -> VoiceOutputResult:
            entered.set()
            _assert(release.wait(timeout=5.0), "aggregate blocking adapter release timeout")
            return VoiceOutputResult(request_state="unavailable")

    events = []
    queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=1, on_event=events.append)
    stage = ProviderNeutralVoiceSynthesisStage(BlockingAdapter())
    first_context = context()
    second_context = context()
    third_context = context()
    first = queue.enqueue(
        context=first_context,
        request=VoiceOutputRequest(text="aggregate active first"),
    )

    results = []
    errors = []

    def run_handoff() -> None:
        try:
            results.append(queue.handoff_next(stage=stage))
        except BaseException as error:  # pragma: no cover - surfaced below
            errors.append(error)

    worker = threading.Thread(target=run_handoff, name="fw-rt6-6c-control-c-active")
    worker.start()
    _assert(entered.wait(timeout=5.0), "aggregate handoff did not become active")
    active = stage.active_generation
    _assert(active is not None and active.work_id == first.work.work_id, "aggregate active identity drift")
    _assert(queue.pending_count == 0, "active item still counted against pending depth")

    second = queue.enqueue(
        context=second_context,
        request=VoiceOutputRequest(text="aggregate pending second"),
    )
    _assert(second.accepted and queue.pending_count == 1, "active work incorrectly consumed pending capacity")
    rejected = queue.enqueue(
        context=third_context,
        request=VoiceOutputRequest(text="aggregate overflow third"),
    )
    _assert(
        rejected.outcome is VoiceSynthesisEnqueueOutcome.REJECTED_FULL,
        "aggregate pending capacity did not reject full queue",
    )
    _assert(len(events) == 1 and events[0].work == rejected.work, "aggregate overflow event drift")

    cleared = queue.clear_pending()
    _assert(cleared.outcome is VoiceSynthesisPendingClearOutcome.CLEARED, "aggregate pending clear drift")
    _assert(cleared.cleared_work == (second.work,), "aggregate clear touched wrong pending work")
    _assert(not cleared.active_generation_cancelled, "aggregate pending clear overclaimed active cancellation")
    _assert(stage.active_generation == active, "aggregate pending clear changed active stage state")

    release.set()
    worker.join(timeout=5.0)
    _assert(not worker.is_alive(), "aggregate active worker did not complete")
    _assert(not errors, f"aggregate active worker failed: {errors!r}")
    _assert(len(results) == 1 and results[0].work_id == first.work.work_id, "aggregate active result identity drift")
    _assert(stage.active_generation is None, "aggregate active state did not clear")
    print("[OK] active synthesis is excluded from pending capacity and pending clear remains queue-only")

def check_prior_voice_and_artifact_regressions() -> None:
    voice = _load_script(
        "fw_rt6_6a_active_stage_gate",
        "scripts/smoke_v600_realtime_voice_output_control_b.py",
    )
    voice.check_stable_surface()
    voice.check_existing_adapter_capability_adoption()
    voice.check_active_generation_reference_stage()
    voice.check_cancel_capability_guard()
    voice.check_legacy_session_compatibility()

    artifacts = _load_script(
        "fw_rt6_6b_artifact_aggregate_gate",
        "scripts/check_v600_voice_artifact_store_acceptance.py",
    )
    artifacts.check_aggregate_store_contract()
    artifacts.check_source_boundaries()
    artifacts.check_docs()
    print("[OK] accepted FW-RT6-6a active-stage and FW-RT6-6b artifact-store regressions conform")


def check_deferred_boundaries() -> None:
    provider_source = (PROJECT_ROOT / "framework/audio/_provider_adapter.py").read_text(encoding="utf-8")
    queue_source = (PROJECT_ROOT / "framework/realtime_voice_output_queue.py").read_text(encoding="utf-8")
    voice_source = (PROJECT_ROOT / "framework/realtime_voice_output.py").read_text(encoding="utf-8")

    for marker in (
        "generation_cancel_supported=False",
        "provider_hard_cancel_supported=False",
        "pending_flush_supported=False",
        "active_audio_invalidation_supported=False",
    ):
        _assert(marker in provider_source, f"deferred provider capability drift: {marker}")

    for forbidden in (
        "from elevenlabs",
        "import elevenlabs",
        "import requests",
        "import urllib",
        "import socket",
        "import pyaudio",
        "import sounddevice",
        "subprocess.Popen",
        "subprocess.run",
    ):
        _assert(forbidden not in queue_source, f"queue source leaked direct provider/runtime boundary: {forbidden}")

    _assert("def handoff_next(" in queue_source, "accepted pending-to-active handoff missing")
    _assert("stage._claim_generation(" in queue_source, "same-work-ID claim marker missing")
    _assert("stage._run_claimed(" in queue_source, "claimed execution marker missing")
    _assert("work_id = SynthesisWorkId.new()" in voice_source, "legacy/direct start identity allocation drift")
    _assert("def _claim_generation(" in voice_source, "Control B internal identity claim missing")
    _assert("def _run_claimed(" in voice_source, "Control B claimed execution boundary missing")
    print("[OK] deferred 6d/6e capabilities remain unclaimed")


def check_docs() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    roadmap = (PROJECT_ROOT / "docs/roadmap_feature_v6.0.0.md").read_text(encoding="utf-8")

    section_start = tasklist.index("## FW-RT6-6c — Bounded voice-output work queue")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    _assert(section.count("- [x]") == 7, "FW-RT6-6c task count must be 7 / 7")
    _assert(section.count("- [ ]") == 0, "FW-RT6-6c aggregate task remains open")

    for marker in (
        "FW-RT6-6c-A-ACCEPTANCE-SYNC:BEGIN",
        "implementation commit: b2b516afd1f5102047594e698f3ad9ebc011575c",
        "FW-RT6-6c-B-ACCEPTANCE-SYNC:BEGIN",
        "implementation commit: ae456c2f8ed4ed27c835907ab5f71f495cd5c395",
        "FW-RT6-6c-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "exact Control C delta: 3 files",
        "FW-RT6-6c tasks: 7 / 7 ACCEPTED-CANDIDATE",
        "next checkpoint: FW-RT6-6d / NOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"Control C tasklist marker missing: {marker}")

    for marker in (
        "FW-RT6-6c-C-AGGREGATE-ACCEPTANCE:BEGIN",
        EXPECTED_HEAD,
        "bounded pending queue:\nTrue",
        "enqueue work ID == active work ID == result work ID:\nTrue",
        "pending clear changes active generation:\nFalse",
        "FW-RT6-6c tasks:\n7 / 7 ACCEPTED-CANDIDATE",
        "FW-RT6-6d / NOT_AUTHORIZED",
        "127 / UNCHANGED",
    ):
        _assert(marker in contract, f"Control C contract marker missing: {marker}")

    for marker in (
        "pending work",
        "pending clear",
        "generation cancel",
        "artifact invalidation",
        "future delivery suppression",
        "Host playback boundary",
    ):
        _assert(marker in roadmap, f"P0-5 roadmap marker missing: {marker}")

    print("[OK] all seven FW-RT6-6c tasks and deferred P0-5 boundaries conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_stable_surfaces()
    check_control_a_and_b_regressions()
    check_aggregate_active_pending_capacity()
    check_prior_voice_and_artifact_regressions()
    check_deferred_boundaries()
    check_docs()

    print("v600_rt6_6c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6c_control_c_status: implemented-awaiting-review")
    print("v600_rt6_6c_control_c_exact_delta: 3 files")
    print("v600_rt6_6c_bounded_pending_queue: True / PASS")
    print("v600_rt6_6c_configurable_max_pending_depth: True / PASS")
    print("v600_rt6_6c_pending_item_correlation: session / turn / generation / work / PASS")
    print("v600_rt6_6c_enqueue_typed_result: True / PASS")
    print("v600_rt6_6c_silent_drop: False / PASS")
    print("v600_rt6_6c_pending_clear: True / PASS")
    print("v600_rt6_6c_pending_active_separate: True / PASS")
    print("v600_rt6_6c_overflow_event: True / PASS")
    print("v600_rt6_6c_same_work_id_handoff: True / PASS")
    print("v600_rt6_6c_pending_clear_changes_active: False / PASS")
    print("v600_rt6_6c_active_cancel_overclaim: False / PASS")
    print("v600_rt6_6c_provider_adapter_receives_framework_ids: False / PASS")
    print("v600_rt6_6c_queue_exports: 8 / UNCHANGED")
    print("v600_rt6_6c_realtime_voice_output_exports: 7 / UNCHANGED")
    print("v600_rt6_6c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6c_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_6c_provider_pending_flush_changed: False")
    print("v600_rt6_6c_generation_cancel_changed: False")
    print("v600_rt6_6c_artifact_invalidation_changed: False")
    print("v600_rt6_6c_future_delivery_suppression_changed: False")
    print("v600_rt6_6c_host_playback_changed: False")
    print("v600_rt6_6c_provider_execution: False")
    print("v600_rt6_6c_network_execution: False")
    print("v600_rt6_6c_microphone_access: False")
    print("v600_rt6_6c_playback_execution: False")
    print("v600_rt6_6c_real_vts_execution: False")
    print("v600_rt6_6c_next_checkpoint: FW-RT6-6d / NOT_AUTHORIZED")
    print("v600_rt6_6c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
