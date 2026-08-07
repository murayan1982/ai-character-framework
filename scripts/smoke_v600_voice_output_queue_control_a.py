"""FW-RT6-6c Control A bounded pending voice-output queue gate."""

from __future__ import annotations

import argparse
import dataclasses
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "3bdd196c34d2ffd3eaa2dfc30cc39cf22aa34409"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/realtime_voice_output_queue.py",
    "scripts/smoke_v600_voice_output_queue_control_a.py",
}
EXPECTED_EXPORTS = (
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
        f"Control A exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact five-file FW-RT6-6c Control A surface conform")


def check_prior_acceptance() -> None:
    _run(
        [
            sys.executable,
            "scripts/check_v600_voice_artifact_store_acceptance.py",
            "--source-only",
        ]
    )
    print("[OK] accepted FW-RT6-6b aggregate regression conforms")


def _context():
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import RealtimeStageContext

    return RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )


def check_queue_contract() -> None:
    import framework
    import framework.realtime_voice_output as voice
    import framework.realtime_voice_output_queue as queue
    from framework.audio.voice_output import VoiceOutputRequest

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(tuple(queue.__all__) == EXPECTED_EXPORTS, "stable queue exports drift")
    for name in EXPECTED_EXPORTS:
        _assert(name not in framework.__all__, f"queue name leaked into root-public API: {name}")

    _assert(
        tuple(voice.__all__) == (
            "SynthesisWorkId",
            "VoiceSynthesisResultEnvelope",
            "VoiceSynthesisActiveGeneration",
            "VoiceSynthesisCancelOutcome",
            "VoiceSynthesisCancelResult",
            "VoiceSynthesisProviderAdapter",
            "VoiceSynthesisStage",
        ),
        "accepted realtime_voice_output seven-name surface drift",
    )

    fields = tuple(
        item.name
        for item in dataclasses.fields(queue.VoiceSynthesisPendingWork)
    )
    _assert(fields == ("context", "work_id"), "pending work public fields drift")

    try:
        queue.BoundedVoiceSynthesisPendingQueue(max_pending_depth=0)
    except ValueError:
        pass
    else:
        raise AssertionError("zero pending depth must be rejected")

    try:
        queue.BoundedVoiceSynthesisPendingQueue(max_pending_depth=True)
    except TypeError:
        pass
    else:
        raise AssertionError("boolean pending depth must be rejected")

    events = []
    pending = queue.BoundedVoiceSynthesisPendingQueue(
        max_pending_depth=2,
        on_event=events.append,
    )
    _assert(
        isinstance(pending, queue.VoiceSynthesisPendingQueue),
        "reference queue does not satisfy stable protocol",
    )
    _assert(pending.max_pending_depth == 2, "configured pending depth drift")
    _assert(pending.pending_count == 0, "new pending queue must be empty")
    _assert(pending.overflow_count == 0, "new pending queue overflow count drift")

    context_a = _context()
    context_b = _context()
    context_c = _context()

    first = pending.enqueue(
        context=context_a,
        request=VoiceOutputRequest(text="first pending synthesis"),
    )
    second = pending.enqueue(
        context=context_b,
        request=VoiceOutputRequest(text="second pending synthesis"),
    )
    rejected = pending.enqueue(
        context=context_c,
        request=VoiceOutputRequest(text="overflow pending synthesis"),
    )

    _assert(first.accepted and second.accepted, "valid pending work was not accepted")
    _assert(
        rejected.outcome is queue.VoiceSynthesisEnqueueOutcome.REJECTED_FULL,
        "full queue was not typed rejected",
    )
    _assert(not rejected.accepted, "full queue rejection reported accepted")
    _assert(pending.pending_count == 2, "full queue admission mutated bounded depth")
    _assert(pending.pending_work == (first.work, second.work), "pending FIFO identity drift")
    _assert(pending.overflow_count == 1, "overflow counter drift")
    _assert(len(events) == 1, "queue overflow must emit exactly one component event")
    event = events[0]
    _assert(
        event.type is queue.VoiceSynthesisQueueEventType.OVERFLOW,
        "overflow event type drift",
    )
    _assert(event.work == rejected.work, "overflow event work correlation drift")
    _assert(event.pending_count == 2 and event.max_pending_depth == 2, "overflow depth drift")
    _assert(event.overflow_count == 1, "overflow event count drift")
    _assert(
        event.public_metadata.get("reason") == "bounded_pending_capacity",
        "overflow public diagnostic reason drift",
    )
    _assert(
        "overflow_event_emitted" not in rejected.public_metadata,
        "enqueue rejection must not claim diagnostic callback delivery",
    )

    no_callback = queue.BoundedVoiceSynthesisPendingQueue(max_pending_depth=1)
    no_callback.enqueue(
        context=_context(),
        request=VoiceOutputRequest(text="no callback first"),
    )
    no_callback_rejected = no_callback.enqueue(
        context=_context(),
        request=VoiceOutputRequest(text="no callback overflow"),
    )
    _assert(
        no_callback_rejected.outcome is queue.VoiceSynthesisEnqueueOutcome.REJECTED_FULL,
        "overflow without callback must remain typed rejected",
    )
    _assert(
        "overflow_event_emitted" not in no_callback_rejected.public_metadata,
        "overflow without callback must not claim event delivery",
    )

    callback_attempts = []

    def raising_callback(event):
        callback_attempts.append(event)
        raise RuntimeError("diagnostic callback failure")

    failing_callback = queue.BoundedVoiceSynthesisPendingQueue(
        max_pending_depth=1,
        on_event=raising_callback,
    )
    failing_callback.enqueue(
        context=_context(),
        request=VoiceOutputRequest(text="failing callback first"),
    )
    callback_failure_rejected = failing_callback.enqueue(
        context=_context(),
        request=VoiceOutputRequest(text="failing callback overflow"),
    )
    _assert(
        callback_failure_rejected.outcome is queue.VoiceSynthesisEnqueueOutcome.REJECTED_FULL,
        "diagnostic callback failure must not change typed rejection",
    )
    _assert(len(callback_attempts) == 1, "overflow callback attempt count drift")
    _assert(
        "overflow_event_emitted" not in callback_failure_rejected.public_metadata,
        "callback failure path must not claim event delivery",
    )

    ids = (str(first.work.work_id), str(second.work.work_id), str(rejected.work.work_id))
    _assert(len(set(ids)) == 3, "synthesis work IDs must be unique")
    for value in ids:
        _assert(
            re.fullmatch(r"fw_synthesis_[0-9a-f]{32}", value) is not None,
            "pending synthesis work ID format drift",
        )

    _assert(first.work.context == context_a, "pending session/turn/generation context drift")
    _assert(second.work.context == context_b, "second pending context drift")
    _assert(rejected.work.context == context_c, "rejected attempt context drift")
    _assert(
        "request" not in repr(first.work).lower(),
        "pending public work repr leaked request vocabulary",
    )
    _assert(
        "first pending synthesis" not in repr(first.work),
        "pending public work repr leaked request text",
    )

    cleared_a = pending.clear_pending(context=context_a)
    _assert(
        cleared_a.outcome is queue.VoiceSynthesisPendingClearOutcome.CLEARED,
        "targeted pending clear classification drift",
    )
    _assert(cleared_a.cleared_work == (first.work,), "targeted pending clear identity drift")
    _assert(cleared_a.pending_count == 1, "targeted pending clear count drift")
    _assert(not cleared_a.active_generation_cancelled, "pending clear overclaimed active cancel")
    _assert(pending.pending_work == (second.work,), "targeted clear mutated unrelated pending work")

    nothing_matching = pending.clear_pending(context=context_c)
    _assert(
        nothing_matching.outcome is queue.VoiceSynthesisPendingClearOutcome.NOTHING_CLEARED,
        "targeted no-match clear must report nothing_cleared",
    )
    _assert(nothing_matching.cleared_count == 0, "targeted no-match clear reported cleared work")
    _assert(nothing_matching.pending_count == 1, "targeted no-match clear lost unrelated pending count")
    _assert(
        pending.pending_work == (second.work,),
        "targeted no-match clear mutated unrelated pending work",
    )
    _assert(
        not nothing_matching.active_generation_cancelled,
        "targeted no-match clear overclaimed active cancel",
    )

    cleared_rest = pending.clear_pending()
    _assert(cleared_rest.cleared_work == (second.work,), "full pending clear identity drift")
    _assert(cleared_rest.pending_count == 0, "full pending clear did not empty queue")
    _assert(not cleared_rest.active_generation_cancelled, "full pending clear overclaimed active cancel")

    nothing = pending.clear_pending()
    _assert(
        nothing.outcome is queue.VoiceSynthesisPendingClearOutcome.NOTHING_CLEARED,
        "empty pending clear must report nothing_cleared",
    )
    _assert(nothing.cleared_count == 0, "empty pending clear reported cleared work")
    _assert(not nothing.active_generation_cancelled, "empty pending clear overclaimed active cancel")

    print("[OK] bounded admission, truthful no-op clear, callback-isolated rejection, and overflow event conform")


def check_source_boundaries() -> None:
    queue_source = (
        PROJECT_ROOT / "framework/realtime_voice_output_queue.py"
    ).read_text(encoding="utf-8")
    provider_source = (
        PROJECT_ROOT / "framework/audio/_provider_adapter.py"
    ).read_text(encoding="utf-8")
    voice_source = (
        PROJECT_ROOT / "framework/realtime_voice_output.py"
    ).read_text(encoding="utf-8")

    control_b_adopted = "def handoff_next(" in queue_source
    for forbidden in (
        ".synthesize(",
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
        _assert(forbidden not in queue_source, f"queue source leaked provider/direct execution/import: {forbidden}")

    if control_b_adopted:
        _assert(
            "ProviderNeutralVoiceSynthesisStage" in queue_source,
            "Control B concrete stage composition marker missing",
        )
        _assert(
            "stage._claim_generation(" in queue_source
            and "stage._run_claimed(" in queue_source,
            "Control B same-work-ID handoff markers missing",
        )
    else:
        _assert(
            "ProviderNeutralVoiceSynthesisStage" not in queue_source,
            "Control A queue source leaked deferred stage composition",
        )

    _assert(
        "active_generation" not in queue_source.split("class VoiceSynthesisPendingQueue", 1)[1].split("@dataclass", 1)[0],
        "stable pending queue protocol must not own active generation",
    )
    _assert(
        "pending_flush_supported=False" in provider_source,
        "provider pending-flush capability truth marker drift",
    )
    _assert(
        "generation_cancel_supported=False" in provider_source,
        "provider generation-cancel capability truth marker drift",
    )
    _assert(
        "def start(" in voice_source and "work_id = SynthesisWorkId.new()" in voice_source,
        "accepted synthesis stage identity baseline drift",
    )
    if control_b_adopted:
        print("[OK] accepted Control A pending protocol remains intact under Control B concrete handoff adoption")
    else:
        print("[OK] Control A remains pending-only and does not overclaim active/provider control")


def check_docs() -> None:
    app_doc = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    facade_doc = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md"
    ).read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    roadmap = (
        PROJECT_ROOT / "docs/roadmap_feature_v6.0.0.md"
    ).read_text(encoding="utf-8")

    for doc, marker in (
        (app_doc, "FW-RT6-6c-A-BOUNDED-PENDING-QUEUE:BEGIN"),
        (facade_doc, "FW-RT6-6c-A-BOUNDED-PENDING-QUEUE:BEGIN"),
        (contract, "FW-RT6-6c-A-BOUNDED-PENDING-QUEUE:BEGIN"),
    ):
        _assert(marker in doc, f"Control A documentation marker missing: {marker}")

    for marker in (
        EXPECTED_HEAD,
        "FW-RT6-6c exact contract review:\nCOMPLETED",
        "Control A:\nAUTHORIZED",
        "framework.realtime_voice_output_queue",
        "max_pending_depth",
        "REJECTED_FULL",
        "active generation cancellation:\nFalse / DEFERRED FW-RT6-6d",
        "Control B:\nNOT_AUTHORIZED",
        "root-public names:\n127 / UNCHANGED",
    ):
        _assert(marker in contract, f"Control A contract marker missing: {marker}")

    section_start = tasklist.index("## FW-RT6-6c — Bounded voice-output work queue")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    _assert(section.count("- [ ]") == 7, "FW-RT6-6c task count must remain 7 open in Control A implementation")
    _assert(section.count("- [x]") == 0, "Control A implementation must not close aggregate tasklist items")

    for marker in (
        "pending work",
        "pending clear",
        "generation cancel",
        "artifact invalidation",
        "future delivery suppression",
        "Host playback boundary",
    ):
        _assert(marker in roadmap, f"P0-5 roadmap marker missing: {marker}")

    print("[OK] Control A exact review/docs and deferred P0-5 boundaries conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_prior_acceptance()
    check_queue_contract()
    check_source_boundaries()
    check_docs()

    print("v600_rt6_6c_exact_contract_review: COMPLETED")
    print("v600_rt6_6c_control_a_status: implemented-awaiting-review")
    print("v600_rt6_6c_control_a_exact_surface: 5 files")
    print("v600_rt6_6c_stable_package: framework.realtime_voice_output_queue")
    print("v600_rt6_6c_stable_exports: 8")
    print("v600_rt6_6c_bounded_pending_queue: True / PASS")
    print("v600_rt6_6c_configurable_max_pending_depth: True / PASS")
    print("v600_rt6_6c_pending_item_correlation: session / turn / generation / work / PASS")
    print("v600_rt6_6c_enqueue_typed_result: True / PASS")
    print("v600_rt6_6c_silent_drop: False / PASS")
    print("v600_rt6_6c_pending_clear: True / PASS")
    print("v600_rt6_6c_active_generation_cancelled_by_clear: False / PASS")
    print("v600_rt6_6c_overflow_event: True / PASS")
    print("v600_rt6_6c_provider_pending_flush_supported_changed: False")
    print("v600_rt6_6c_generation_cancel_changed: False")
    print("v600_rt6_6c_artifact_invalidation_changed: False")
    print("v600_rt6_6c_host_playback_changed: False")
    print("v600_rt6_6c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6c_tasklist_closed: 0 / 7")
    print("v600_rt6_6c_control_b: NOT_AUTHORIZED")
    print("v600_rt6_6c_provider_execution: False")
    print("v600_rt6_6c_network_execution: False")
    print("v600_rt6_6c_microphone_access: False")
    print("v600_rt6_6c_playback_execution: False")
    print("v600_rt6_6c_real_vts_execution: False")
    print("v600_rt6_6c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
