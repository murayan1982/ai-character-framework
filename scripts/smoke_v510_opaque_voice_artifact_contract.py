"""Mock-safe opaque voice artifact contract smoke for FW v5.1.0."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


FORBIDDEN_MODULE_MARKERS = (
    "elevenlabs",
    "openai",
    "tts.voice_engine",
    "framework.tts.voice_engine",
)

REAL_PROVIDER_ENV_KEYS = (
    "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
    "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
)


class ContractFailure(AssertionError):
    pass


def ok(message: str) -> None:
    print(f"[OK] {message}")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


@contextmanager
def disabled_real_provider_execution() -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in REAL_PROVIDER_ENV_KEYS}
    try:
        for key in REAL_PROVIDER_ENV_KEYS:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _assert_import_safe() -> None:
    loaded = set(sys.modules)
    for marker in FORBIDDEN_MODULE_MARKERS:
        _require(
            not any(module == marker or module.startswith(marker + ".") for module in loaded),
            f"provider/internal module was loaded unexpectedly: {marker}",
        )
    ok("opaque artifact import stays provider/internal safe")


def _assert_doc(root: Path) -> None:
    doc = root / "docs" / "v510_opaque_voice_artifact_contract.md"
    _require(doc.exists(), "opaque voice artifact contract doc is missing")
    text = doc.read_text(encoding="utf-8", errors="replace")
    for phrase in (
        "VoiceArtifactRef",
        "artifact ref must not expose raw local paths",
        "Playable generated audio should expose exactly one public handoff",
        "This checkpoint does not add real artifact storage or resolver behavior",
    ):
        _require(phrase in text, f"opaque artifact doc missing phrase: {phrase}")
    ok("opaque voice artifact contract doc is documented")


def _assert_public_type(framework: object) -> None:
    exported = getattr(framework, "__all__", ())
    _require("VoiceArtifactRef" in exported, "VoiceArtifactRef must be exported from framework.__all__")
    ref_type = getattr(framework, "VoiceArtifactRef", None)
    _require(ref_type is not None, "framework.VoiceArtifactRef is missing")

    ref = ref_type.from_id(
        "voice_artifact_abc123",
        audio_format="mp3",
        content_type="audio/mpeg",
        public_metadata={"boundary": "voice_output"},
    )
    _require(str(ref) == "voice_artifact_abc123", "VoiceArtifactRef string form must be opaque ID")
    public_dict = ref.to_public_dict()
    _require(public_dict["artifact_id"] == "voice_artifact_abc123", "VoiceArtifactRef public dict lost artifact_id")
    _require(public_dict["artifact_kind"] == "audio", "VoiceArtifactRef kind should be audio")
    _require(public_dict["audio_format"] == "mp3", "VoiceArtifactRef should preserve audio format")
    _require("/" not in str(ref) and "\\" not in str(ref), "VoiceArtifactRef must not look like a local path")

    for invalid in ("C:" + chr(92) + "private" + chr(92) + "audio.mp3", "/tmp/private/audio.mp3"):
        try:
            ref_type.from_id(invalid)
        except ValueError:
            continue
        raise ContractFailure(f"VoiceArtifactRef accepted private path-like ID: {invalid}")

    ok("VoiceArtifactRef public type is opaque and secret-free")


def _assert_result_handoff(framework: object) -> None:
    ref = framework.VoiceArtifactRef.from_id("voice_artifact_result_001", audio_format="mp3")
    result = framework.VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_format="mp3",
        audio_url=None,
        audio_artifact_ref=ref,
        message="Generated audio is ready.",
        public_metadata={"boundary": "voice_output"},
    )

    _require(result.audio_ready is True, "generated artifact result should be audio_ready")
    _require(result.audio_artifact_ref is ref, "VoiceOutputResult should preserve VoiceArtifactRef")
    _require(result.audio_url is None, "artifact handoff result should not also expose audio_url")
    _require(result.has_audio_handoff is True, "artifact handoff result should report handoff")
    _require(result.audio_handoff_kind == "audio_artifact_ref", "artifact result should report audio_artifact_ref handoff")
    _require(result.is_generated is True, "generated artifact result should report generated")

    non_playable = framework.VoiceOutputResult(
        request_state="unavailable",
        audio_ready=False,
        audio_format="mp3",
        audio_url=None,
        audio_artifact_ref=None,
        message="Voice output is unavailable.",
        public_metadata={"boundary": "voice_output"},
    )
    _require(non_playable.has_audio_handoff is False, "non-playable result should not expose handoff")
    _require(non_playable.audio_handoff_kind == "none", "non-playable result should report no handoff")
    ok("VoiceOutputResult accepts opaque artifact refs without exposing local paths")


def main() -> None:
    root = Path.cwd()
    _require((root / "framework").exists(), "run this smoke from the FW repository root")
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    import framework  # noqa: PLC0415

    _assert_import_safe()
    _assert_doc(root)
    with disabled_real_provider_execution():
        _assert_public_type(framework)
        _assert_result_handoff(framework)
    _assert_import_safe()
    ok("v5.1.0 opaque voice artifact contract is mock-safe")


if __name__ == "__main__":
    main()
