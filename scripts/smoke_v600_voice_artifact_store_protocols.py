"""FW-RT6-6b Control A opaque voice artifact store protocol gate."""

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

EXPECTED_HEAD = "5318f89aeb524f91f7c388816058bb0e8a3e2fc0"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/voice_artifacts.py",
    "scripts/smoke_v600_voice_artifact_store_protocols.py",
}
EXPECTED_EXPORTS = (
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
        f"Control A exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact five-file FW-RT6-6b Control A surface conform")


def check_prior_acceptance() -> None:
    _run([sys.executable, "scripts/check_v600_realtime_voice_output_acceptance.py", "--source-only"])
    print("[OK] accepted FW-RT6-6a aggregate voice-output regression conforms")


def check_stable_package() -> None:
    import framework
    import framework.voice_artifacts as artifacts

    _assert(len(framework.__all__) == 127, "root-public count drift")
    _assert(tuple(artifacts.__all__) == EXPECTED_EXPORTS, "stable package export drift")
    _assert("VoiceArtifactStore" not in framework.__all__, "Control A must not root-reexport store")
    _assert("VoiceArtifactId" not in framework.__all__, "Control A must not root-reexport artifact ID")

    artifact_id = artifacts.VoiceArtifactId.new()
    _assert(
        re.fullmatch(r"fw_voice_artifact_[0-9a-f]{32}", str(artifact_id)) is not None,
        "artifact ID format drift",
    )
    _assert(artifacts.VoiceArtifactId.parse(str(artifact_id)) == artifact_id, "artifact ID parse drift")
    for invalid in (
        "voice_output.mp3",
        "C:\\private\\voice.mp3",
        "/tmp/voice.mp3",
        "artifact://voice/output",
        "fw_voice_artifact_NOT_HEX",
    ):
        try:
            artifacts.VoiceArtifactId(invalid)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"private/non-opaque artifact ID accepted: {invalid!r}")

    print("[OK] stable framework.voice_artifacts package and opaque ID conform")


def check_store_lifecycle() -> None:
    from framework.audio.voice_output import VoiceArtifactRef
    from framework.identity import GenerationId
    import framework.voice_artifacts as artifacts

    with tempfile.TemporaryDirectory() as temp_dir:
        store = artifacts.FileVoiceArtifactStore(Path(temp_dir) / "private-artifacts")
        _assert(isinstance(store, artifacts.VoiceArtifactStore), "reference store protocol mismatch")

        ref = store.store(
            [b"one", b"-", b"two"],
            audio_format=".MP3",
            content_type="audio/mpeg",
        )
        _assert(isinstance(ref, VoiceArtifactRef), "store must return VoiceArtifactRef")
        _assert(re.fullmatch(r"fw_voice_artifact_[0-9a-f]{32}", ref.artifact_id) is not None, "opaque ref drift")
        _assert("/" not in ref.artifact_id and "\\" not in ref.artifact_id, "artifact ref leaked path syntax")
        _assert(str(Path(temp_dir)) not in repr(ref), "artifact ref repr leaked store root")
        _assert(ref.audio_format == "mp3", "audio format normalization drift")

        record = store.resolve(ref)
        _assert(record is not None and record.is_playable, "stored artifact must resolve valid")
        _assert(record.state is artifacts.VoiceArtifactState.VALID, "new artifact state drift")
        _assert(record.generation_id is None, "provider-side store must not require generation identity")
        _assert("path" not in repr(record).lower(), "public-safe record leaked path vocabulary")
        _assert(str(Path(temp_dir)) not in repr(record), "public-safe record leaked store root")

        with store.open(ref) as stream:
            _assert(stream.read() == b"one-two", "artifact open bytes drift")

        generation_id = GenerationId.new()
        bound = store.bind_generation(ref, generation_id)
        _assert(bound.generation_id == generation_id, "generation binding drift")
        _assert(bound.is_playable, "generation binding must not invalidate artifact")
        _assert(store.bind_generation(ref, generation_id).generation_id == generation_id, "same-generation bind must be idempotent")
        try:
            store.bind_generation(ref, GenerationId.new())
        except ValueError:
            pass
        else:
            raise AssertionError("artifact rebound to a different generation")

        _assert(store.expire(ref), "valid artifact must expire")
        expired = store.resolve(ref)
        _assert(expired is not None and not expired.is_playable, "expired artifact remained playable")
        _assert(expired.state is artifacts.VoiceArtifactState.EXPIRED, "expired state drift")
        _assert(not store.expire(ref), "repeated expire must be deterministic false")
        try:
            store.open(ref)
        except FileNotFoundError as exc:
            _assert(str(Path(temp_dir)) not in str(exc), "open error leaked private path")
        else:
            raise AssertionError("expired artifact opened successfully")

        second = store.store(b"delete-me", audio_format="mp3")
        _assert(store.delete(second), "valid artifact must delete")
        deleted = store.resolve(second)
        _assert(deleted is not None and not deleted.is_playable, "deleted artifact remained playable")
        _assert(deleted.state is artifacts.VoiceArtifactState.DELETED, "deleted state drift")
        _assert(not store.delete(second), "repeated delete must be deterministic false")
        try:
            store.open(second)
        except FileNotFoundError as exc:
            _assert(str(Path(temp_dir)) not in str(exc), "delete error leaked private path")
        else:
            raise AssertionError("deleted artifact opened successfully")

        unknown = artifacts.VoiceArtifactId.new()
        _assert(store.resolve(unknown) is None, "unknown artifact must resolve None")

    print("[OK] store/resolve/open/delete/expire and generation binding primitives conform")


def check_control_boundaries() -> None:
    source = (PROJECT_ROOT / "framework/voice_artifacts.py").read_text(encoding="utf-8")
    _assert("provider_hard_cancel" not in source, "Control A must not change provider hard cancel")
    _assert("pending_flush" not in source, "Control A must not implement pending queue flush")
    _assert("playback_stop" not in source, "Control A must not implement host playback stop")
    _assert("requests." not in source and "httpx" not in source, "Control A must not add network execution")
    _assert("elevenlabs" not in source.lower(), "Control A store must remain provider-neutral")
    _assert("GenerationId" in source and "bind_generation" in source, "generation validity association primitive missing")
    _assert("FileVoiceArtifactStore" not in EXPECTED_EXPORTS, "concrete local store must not enter stable package exports")

    provider_source = (PROJECT_ROOT / "framework/audio/_provider_adapter.py").read_text(encoding="utf-8")
    _assert("audio_artifact_ref=str(artifact_path)" in provider_source, "Control A must not silently adopt provider adapter")

    print("[OK] Control A remains provider-neutral and does not cross Control B/6c/6d/6e boundaries")


def check_docs() -> None:
    paths = {
        "app": PROJECT_ROOT / "docs/app_integration_contract.md",
        "facade": PROJECT_ROOT / "docs/public_facade.md",
        "contract": PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md",
    }
    texts = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}

    required_contract = (
        "FW-RT6-6b-A-ARTIFACT-STORE-PROTOCOL:BEGIN",
        EXPECTED_HEAD,
        "framework.voice_artifacts",
        "fw_voice_artifact_<32 lowercase hex>",
        "VoiceArtifactStore",
        "resolve / open / delete / expire",
        "provider adapter receives GenerationId:\nFalse",
        "Control B:\nNOT_AUTHORIZED",
    )
    for marker in required_contract:
        _assert(marker in texts["contract"], f"v600 voice-output contract missing: {marker}")

    for name in ("app", "facade"):
        for marker in (
            "FW-RT6-6b-A-OPAQUE-ARTIFACT-STORE:BEGIN",
            "framework.voice_artifacts",
            "fw_voice_artifact_<32 lowercase hex>",
            "root-public names: 127 / UNCHANGED",
        ):
            _assert(marker in texts[name], f"{name} doc missing: {marker}")

    print("[OK] Control A artifact-store public integration docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_prior_acceptance()
    check_stable_package()
    check_store_lifecycle()
    check_control_boundaries()
    check_docs()

    print("v600_rt6_6b_control_a_status: implemented-awaiting-review")
    print("v600_rt6_6b_control_a_exact_surface: 5 files")
    print(f"v600_rt6_6b_control_a_baseline_head: {EXPECTED_HEAD}")
    print("v600_rt6_6b_stable_package: framework.voice_artifacts")
    print("v600_rt6_6b_artifact_id_format: fw_voice_artifact_<32 lowercase hex>")
    print("v600_rt6_6b_store_protocol: VoiceArtifactStore")
    print("v600_rt6_6b_store_lifecycle: resolve / open / delete / expire")
    print("v600_rt6_6b_generation_binding_primitive: True")
    print("v600_rt6_6b_provider_adapter_receives_generation_id: False")
    print("v600_rt6_6b_raw_local_path_public: False / FOUNDATION")
    print("v600_rt6_6b_real_provider_path_leak_corrected: False / CONTROL B")
    print("v600_rt6_6b_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6b_pending_queue_changed: False")
    print("v600_rt6_6b_generation_cancel_changed: False")
    print("v600_rt6_6b_host_playback_changed: False")
    print("v600_rt6_6b_provider_execution: False")
    print("v600_rt6_6b_network_execution: False")
    print("v600_rt6_6b_microphone_access: False")
    print("v600_rt6_6b_playback_execution: False")
    print("v600_rt6_6b_real_vts_execution: False")
    print("v600_rt6_6b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_6b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
