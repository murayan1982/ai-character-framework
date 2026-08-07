"""FW-RT6-6b Control C aggregate opaque artifact-store acceptance gate."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "163ad7c7a611221148dd1bc5a902685615caaf16"
EXPECTED_SURFACE = {
    "docs/v600_realtime_voice_output_contract.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_voice_artifact_store_acceptance.py",
}
EXPECTED_ARTIFACT_EXPORTS = (
    "VoiceArtifactId",
    "VoiceArtifactState",
    "VoiceArtifactRecord",
    "VoiceArtifactStore",
)
EXPECTED_VOICE_EXPORTS = (
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
    print("[OK] baseline and exact three-file FW-RT6-6b Control C surface conform")


def check_prior_controls() -> None:
    _run(
        [
            sys.executable,
            "scripts/smoke_v600_voice_artifact_store_control_b.py",
            "--source-only",
        ]
    )
    _run([sys.executable, "scripts/smoke_voice_output_artifact_result_contract.py"])
    _run(
        [
            sys.executable,
            "scripts/check_v600_realtime_voice_output_acceptance.py",
            "--source-only",
        ]
    )
    print("[OK] accepted Control A+B artifact-store and FW-RT6-6a regressions conform")


def check_aggregate_store_contract() -> None:
    import framework
    import framework.realtime_voice_output as realtime_voice
    import framework.voice_artifacts as artifacts
    from framework import VoiceArtifactRef, VoiceOutputResult
    from framework.identity import GenerationId

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(
        tuple(artifacts.__all__) == EXPECTED_ARTIFACT_EXPORTS,
        "framework.voice_artifacts stable exports drift",
    )
    _assert(
        tuple(realtime_voice.__all__) == EXPECTED_VOICE_EXPORTS,
        "framework.realtime_voice_output stable exports drift",
    )
    _assert(
        "VoiceArtifactStore" not in framework.__all__,
        "VoiceArtifactStore must remain explicit-package only",
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
            "reference store protocol mismatch",
        )

        ref = store.store(
            [b"aggregate", b"-", b"audio"],
            audio_format=".MP3",
            content_type="audio/mpeg",
        )
        _assert(isinstance(ref, VoiceArtifactRef), "store did not return VoiceArtifactRef")
        _assert(
            re.fullmatch(r"fw_voice_artifact_[0-9a-f]{32}", ref.artifact_id) is not None,
            "stored artifact ref is not opaque",
        )
        _assert(
            "/" not in ref.artifact_id and "\\" not in ref.artifact_id,
            "public artifact ref leaked path syntax",
        )
        _assert(
            str(Path(directory)) not in repr(ref),
            "public artifact ref repr leaked internal storage root",
        )

        record = store.resolve(ref)
        _assert(record is not None and record.is_playable, "valid artifact did not resolve playable")
        _assert(
            record.state is artifacts.VoiceArtifactState.VALID,
            "new artifact validity state drift",
        )
        with store.open(ref) as stream:
            _assert(stream.read() == b"aggregate-audio", "artifact bytes drift")

        generation_id = GenerationId.new()
        bound = store.bind_generation(ref, generation_id)
        _assert(bound.generation_id == generation_id, "generation association drift")
        _assert(bound.is_playable, "generation association invalidated valid artifact")

        expiring = store.store(b"expire", audio_format="mp3")
        _assert(store.expire(expiring), "valid artifact did not expire")
        expired = store.resolve(expiring)
        _assert(
            expired is not None
            and expired.state is artifacts.VoiceArtifactState.EXPIRED
            and not expired.is_playable,
            "expired artifact remained playable",
        )
        try:
            store.open(expiring)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("expired artifact opened successfully")

        deleting = store.store(b"delete", audio_format="mp3")
        _assert(store.delete(deleting), "valid artifact did not delete")
        deleted = store.resolve(deleting)
        _assert(
            deleted is not None
            and deleted.state is artifacts.VoiceArtifactState.DELETED
            and not deleted.is_playable,
            "deleted artifact remained playable",
        )
        try:
            store.open(deleting)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("deleted artifact opened successfully")

    synthetic_ref = VoiceArtifactRef.from_id(
        "fw_voice_artifact_" + ("a" * 32),
        audio_format="mp3",
        content_type="audio/mpeg",
    )
    generated = VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_format="mp3",
        audio_artifact_ref=synthetic_ref,
    )
    _assert(generated.has_audio_handoff, "valid generated handoff not accepted")

    for kwargs in (
        {
            "request_state": "generated",
            "audio_ready": True,
            "audio_format": "mp3",
        },
        {
            "request_state": "generated",
            "audio_ready": True,
            "audio_format": "mp3",
            "audio_url": "https://example.invalid/audio.mp3",
            "audio_artifact_ref": synthetic_ref,
        },
    ):
        try:
            VoiceOutputResult(**kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError("generated exactly-one handoff invariant not enforced")

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
        raise AssertionError("raw local path artifact handoff accepted")

    print("[OK] opaque store lifecycle, path separation, handoff, and validity invariants conform")


def check_source_boundaries() -> None:
    adapter_source = (
        PROJECT_ROOT / "framework/audio/_provider_adapter.py"
    ).read_text(encoding="utf-8")
    stage_source = (
        PROJECT_ROOT / "framework/realtime_voice_output.py"
    ).read_text(encoding="utf-8")

    _assert(
        "audio_artifact_ref=str(artifact_path)" not in adapter_source,
        "real provider legacy local-path handoff remains",
    )
    _assert(
        "def _build_artifact_path" not in adapter_source,
        "legacy provider artifact path builder remains",
    )
    _assert(
        "artifact_ref = self._artifact_store.store(" in adapter_source,
        "provider artifact-store adoption missing",
    )

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
            f"provider protocol leaked Framework correlation/storage value: {forbidden}",
        )

    for marker in (
        "generation_cancel_supported=False",
        "provider_hard_cancel_supported=False",
        "pending_flush_supported=False",
        "active_audio_invalidation_supported=False",
    ):
        _assert(marker in adapter_source, f"deferred capability overclaim marker missing: {marker}")

    print("[OK] provider path leak is removed without overclaiming FW-RT6-6c/6d/6e capabilities")


def check_docs() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md"
    ).read_text(encoding="utf-8")
    roadmap = (
        PROJECT_ROOT / "docs/roadmap_feature_v6.0.0.md"
    ).read_text(encoding="utf-8")

    section_start = tasklist.index("## FW-RT6-6b — Opaque artifact store")
    section_end = tasklist.index("\n---\n", section_start)
    section = tasklist[section_start:section_end]
    _assert(section.count("- [x]") == 7, "FW-RT6-6b task count must be 7 / 7")
    _assert(section.count("- [ ]") == 0, "FW-RT6-6b aggregate task remains open")

    for marker in (
        "FW-RT6-6b-B-ACCEPTANCE-SYNC:BEGIN",
        "implementation commit: 0719880b0caab9c69038b50d000f17a128d5d062",
        "status: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED",
        "FW-RT6-6b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "exact Control C delta: 3 files",
        "FW-RT6-6b tasks: 7 / 7 ACCEPTED-CANDIDATE",
        "next checkpoint: FW-RT6-6c / NOT_AUTHORIZED",
    ):
        _assert(marker in tasklist, f"Control C tasklist marker missing: {marker}")

    for marker in (
        "FW-RT6-6b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        EXPECTED_HEAD,
        "VoiceArtifactStore protocol:\nTrue",
        "internal storage path exposed by VoiceArtifactRef:\nFalse",
        "generated audio handoff:\naudio_url XOR audio_artifact_ref / REQUIRED",
        "real provider local path in VoiceOutputResult:\nFalse",
        "expired/deleted artifact playable:\nFalse",
        "FW-RT6-6b tasks:\n7 / 7 ACCEPTED-CANDIDATE",
        "FW-RT6-6c / NOT_AUTHORIZED",
        "127 / UNCHANGED",
    ):
        _assert(marker in contract, f"Control C contract marker missing: {marker}")

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

    print("[OK] all seven FW-RT6-6b tasks and deferred P0-5 boundaries conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_prior_controls()
    check_aggregate_store_contract()
    check_source_boundaries()
    check_docs()

    print("v600_rt6_6b_control_a_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_6b_control_b_status: COMPLETED / VERIFIED / ACCEPTED")
    print("v600_rt6_6b_control_c_status: implemented-awaiting-review")
    print("v600_rt6_6b_control_c_exact_delta: 3 files")
    print("v600_rt6_6b_voice_artifact_store_protocol: True / PASS")
    print("v600_rt6_6b_opaque_artifact_id: True / PASS")
    print("v600_rt6_6b_internal_path_public_ref_separated: True / PASS")
    print("v600_rt6_6b_store_lifecycle: resolve / open / delete / expire / PASS")
    print("v600_rt6_6b_generated_exactly_one_handoff: True / PASS")
    print("v600_rt6_6b_raw_local_path_in_voice_output_result: False / PASS")
    print("v600_rt6_6b_stage_generation_binding: True / PASS")
    print("v600_rt6_6b_expired_deleted_artifact_playable: False / PASS")
    print("v600_rt6_6b_interrupt_driven_invalidation: DEFERRED / FW-RT6-6d")
    print("v600_rt6_6b_provider_adapter_receives_framework_ids: False / PASS")
    print("v600_rt6_6b_artifact_exports: 4 / UNCHANGED")
    print("v600_rt6_6b_realtime_voice_output_exports: 7 / UNCHANGED")
    print("v600_rt6_6b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6b_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_6b_pending_queue_changed: False")
    print("v600_rt6_6b_generation_cancel_or_interrupt_invalidation_changed: False")
    print("v600_rt6_6b_host_playback_changed: False")
    print("v600_rt6_6b_provider_execution: False")
    print("v600_rt6_6b_network_execution: False")
    print("v600_rt6_6b_microphone_access: False")
    print("v600_rt6_6b_playback_execution: False")
    print("v600_rt6_6b_real_vts_execution: False")
    print("v600_rt6_6b_next_checkpoint: FW-RT6-6c / NOT_AUTHORIZED")
    print("v600_rt6_6b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
