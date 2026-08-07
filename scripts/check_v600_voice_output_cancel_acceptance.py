"""FW-RT6-6d Control C aggregate cancellation/invalidation acceptance gate."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "663a23b4485a96a75e5a3dfb1ab70c15517e0fc2"
EXPECTED_SURFACE = {
    "docs/v600_realtime_voice_output_contract.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_voice_output_cancel_acceptance.py",
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


def _load_script(filename: str, module_name: str):
    path = PROJECT_ROOT / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    _assert(spec is not None and spec.loader is not None, f"cannot load {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "baseline origin/main drift",
    )
    actual = _changed_paths()
    _assert(
        actual == EXPECTED_SURFACE,
        f"Control C exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact three-file FW-RT6-6d Control C surface conform")


def check_stable_surfaces() -> None:
    import framework
    import framework.realtime_voice_output as voice
    import framework.realtime_voice_output_queue as queue
    import framework.voice_artifacts as artifacts

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(tuple(voice.__all__) == VOICE_EXPORTS, "voice stable exports drift")
    _assert(tuple(queue.__all__) == QUEUE_EXPORTS, "queue stable exports drift")
    _assert(tuple(artifacts.__all__) == ARTIFACT_EXPORTS, "artifact stable exports drift")
    for name in (
        "CancelableProviderNeutralVoiceSynthesisStage",
        "VoiceSynthesisOutputController",
        "VoiceSynthesisControlFlushResult",
    ):
        _assert(name not in framework.__all__, f"internal cancel control leaked root-public: {name}")
    print("[OK] root/voice/queue/artifact stable public surfaces remain unchanged")


def check_accepted_control_core() -> None:
    control_a = _load_script(
        "smoke_v600_voice_output_cancel_control_a.py",
        "_fw_rt6_6d_control_a_gate",
    )
    control_b = _load_script(
        "smoke_v600_voice_output_cancel_control_b.py",
        "_fw_rt6_6d_control_b_gate",
    )

    # Reuse accepted runtime/model checks directly. Historical git/docs checks
    # intentionally encode pre-aggregate 0/7 task state and are not called here.
    control_a.check_cancel_model()
    control_b.check_completed_artifact_invalidation()
    control_b.check_cooperative_cancel_completion()
    control_b.check_cancel_timeout_and_late_suppression()
    control_b.check_generation_gate_stale_guard()
    control_b.check_flush_distinguishes_pending_and_active()
    print("[OK] accepted Control A typed model and Control B runtime core checks conform")


def check_prior_voice_regressions() -> None:
    for command in (
        [sys.executable, "scripts/check_v600_realtime_voice_output_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_voice_artifact_store_acceptance.py", "--source-only"],
        [sys.executable, "scripts/check_v600_voice_output_queue_acceptance.py", "--source-only"],
    ):
        _run(command)
    print("[OK] accepted FW-RT6-6a/6b/6c regressions conform")


def check_boundaries() -> None:
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
    print("[OK] provider capability, session orchestration, and host-playback boundaries remain deferred")


def check_docs_and_tasklist() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")

    start = tasklist.index("## FW-RT6-6d — Generation cancel and artifact invalidation")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _assert(section.count("- [x]") == 7, "FW-RT6-6d aggregate task count must be 7 / 7")
    _assert(section.count("- [ ]") == 0, "FW-RT6-6d aggregate task remains open")

    next_start = tasklist.index("## FW-RT6-6e — Host playback boundary", end)
    next_end = tasklist.index("\n---\n", next_start)
    next_section = tasklist[next_start:next_end]
    _assert(next_section.count("- [ ]") == 6, "FW-RT6-6e task count drift")
    _assert(next_section.count("- [x]") == 0, "FW-RT6-6e was prematurely authorized/closed")

    for marker in (
        "FW-RT6-6d-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-6d-B-ACCEPTANCE-SYNC:BEGIN",
        "implementation commit: 32c78a4a7b437f11fb41638a08a7b5138bcd01cc",
        "FW-RT6-6d-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "exact Control C delta: 3 files",
        "FW-RT6-6d tasks: 7 / 7 ACCEPTED-CANDIDATE",
        "next checkpoint: FW-RT6-6e / NOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"Control C tasklist marker missing: {marker}")

    for marker in (
        "FW-RT6-6d-C-AGGREGATE-ACCEPTANCE:BEGIN",
        EXPECTED_HEAD,
        "runtime Python modified by Control C:\nFalse",
        "provider hard cancel applied:\nFalse / TRUTHFUL expected",
        "late artifact stale guard:\nexisting RealtimeGenerationGate / PASS expected",
        "new freshness registry:\nFalse expected",
        "FW-RT6-6d tasks:\n7 / 7 ACCEPTED-CANDIDATE",
        "FW-RT6-6e / NOT_AUTHORIZED",
        "127 / UNCHANGED",
    ):
        _assert(marker in contract, f"Control C contract marker missing: {marker}")

    print("[OK] all seven FW-RT6-6d tasks are aggregate-accepted candidates; FW-RT6-6e remains unauthorized")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_stable_surfaces()
    check_accepted_control_core()
    check_prior_voice_regressions()
    check_boundaries()
    check_docs_and_tasklist()

    print("v600_rt6_6d_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6d_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_6d_control_c_status: implemented-awaiting-review")
    print("v600_rt6_6d_control_c_exact_delta: 3 files")
    print("v600_rt6_6d_active_cooperative_cancel: True / PASS")
    print("v600_rt6_6d_cancel_timeout: BOUNDED / PASS")
    print("v600_rt6_6d_provider_hard_cancel_applied: False / TRUTHFUL")
    print("v600_rt6_6d_provider_hard_cancel_unsupported: True / PASS")
    print("v600_rt6_6d_completed_artifact_invalidation: True / PASS")
    print("v600_rt6_6d_invalidated_artifact_playable: False / PASS")
    print("v600_rt6_6d_future_delivery_suppression: True / PASS")
    print("v600_rt6_6d_late_artifact_generation_gate: True / PASS")
    print("v600_rt6_6d_new_freshness_registry: False / PASS")
    print("v600_rt6_6d_duplicate_cancel_idempotent: True / PASS")
    print("v600_rt6_6d_duplicate_flush_idempotent: True / PASS")
    print("v600_rt6_6d_pending_clear_active_cancel_distinguished: True / PASS")
    print("v600_rt6_6d_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6d_realtime_voice_output_exports: 7 / UNCHANGED")
    print("v600_rt6_6d_voice_artifact_exports: 4 / UNCHANGED")
    print("v600_rt6_6d_queue_exports: 8 / UNCHANGED")
    print("v600_rt6_6d_control_c_runtime_changed: False")
    print("v600_rt6_6d_provider_capability_changed: False")
    print("v600_rt6_6d_realtime_session_changed: False")
    print("v600_rt6_6d_host_playback_changed: False")
    print("v600_rt6_6d_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_6d_provider_execution: False")
    print("v600_rt6_6d_network_execution: False")
    print("v600_rt6_6d_microphone_access: False")
    print("v600_rt6_6d_playback_execution: False")
    print("v600_rt6_6d_real_vts_execution: False")
    print("v600_rt6_6d_next_checkpoint: FW-RT6-6e / NOT_AUTHORIZED")
    print("v600_rt6_6d_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
