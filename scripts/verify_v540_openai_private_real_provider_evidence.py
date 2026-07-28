\
"""Verify private REQ-5 operator evidence without printing private contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


EVIDENCE_SCHEMA = "ai-character-framework-v540-req5-private-evidence-v1"


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _sha256_text(path: Path) -> str:
    return hashlib.sha256(
        path.read_text(encoding="utf-8").encode("utf-8")
    ).hexdigest()


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-json", required=True)
    args = parser.parse_args()

    root = _repo_root()
    evidence_path = Path(args.evidence_json).expanduser().resolve(strict=True)
    _require(
        not _is_inside(evidence_path, root),
        "Private evidence must remain outside the repository.",
    )
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    _require(isinstance(payload, Mapping), "Evidence must be a JSON object.")

    _require(payload.get("schema") == EVIDENCE_SCHEMA, "Evidence schema mismatch.")
    _require(payload.get("repo_clean_before") is True, "Repo was not clean before run.")
    _require(payload.get("repo_clean_after") is True, "Repo was not clean after run.")
    _require(
        payload.get("audio_source_outside_repo") is True,
        "Audio source outside-repo marker missing.",
    )
    _require(
        payload.get("evidence_outside_repo") is True,
        "Evidence outside-repo marker missing.",
    )
    _require(
        payload.get("private_staged_audio_cleanup_verified") is True,
        "Private staged audio cleanup was not verified.",
    )
    _require(
        payload.get("actual_openai_sdk_imported") is True,
        "Actual OpenAI SDK import was not verified.",
    )
    _require(
        payload.get("actual_provider_client_created") is True,
        "Actual provider client creation was not verified.",
    )
    _require(
        payload.get("real_provider_execution_executed") is True,
        "Real provider execution was not verified.",
    )
    _require(
        payload.get("real_transcript_present") is True,
        "Real transcript presence was not verified.",
    )
    _require(
        payload.get("provider_neutral_result_type") == "VoiceInputResult",
        "Provider-neutral result type mismatch.",
    )
    _require(payload.get("outcome") == "completed", "Outcome is not completed.")
    _require(
        int(payload.get("transcript_char_count", 0)) > 0,
        "Transcript character count must be positive.",
    )

    public_metadata = payload.get("public_result_metadata")
    _require(
        isinstance(public_metadata, Mapping),
        "Public result metadata must be an object.",
    )
    for key, expected in (
        ("provider_sdk_imported", True),
        ("provider_client_created", True),
        ("provider_protocol_call_executed", True),
        ("real_provider_execution_executed", True),
        ("private_auth_value_exposed", False),
        ("audio_path_exposed", False),
        ("raw_audio_exposed", False),
        ("provider_payload_exposed", False),
        ("microphone_accessed", False),
    ):
        _require(
            public_metadata.get(key) is expected,
            f"Public metadata mismatch: {key}",
        )

    transcript_filename = payload.get("private_transcript_filename")
    _require(
        isinstance(transcript_filename, str) and transcript_filename,
        "Private transcript filename missing.",
    )
    _require(
        Path(transcript_filename).name == transcript_filename,
        "Private transcript filename must be relative and basename-only.",
    )
    transcript_path = evidence_path.parent / transcript_filename
    _require(transcript_path.is_file(), "Private transcript file is missing.")
    _require(
        not _is_inside(transcript_path, root),
        "Private transcript must remain outside the repository.",
    )
    _require(
        _sha256_text(transcript_path) == payload.get("transcript_sha256"),
        "Private transcript hash mismatch.",
    )

    evidence_text = evidence_path.read_text(encoding="utf-8")
    transcript_text = transcript_path.read_text(encoding="utf-8")
    _require(
        transcript_text not in evidence_text,
        "Evidence JSON must not contain the full transcript.",
    )
    _require(
        payload.get("private_credential_exposed") is False,
        "Private credential exposure marker mismatch.",
    )
    _require(
        payload.get("private_audio_path_exposed") is False,
        "Private audio-path exposure marker mismatch.",
    )
    _require(
        payload.get("raw_audio_exposed") is False,
        "Raw-audio exposure marker mismatch.",
    )
    _require(
        payload.get("provider_payload_exposed") is False,
        "Provider-payload exposure marker mismatch.",
    )
    _require(
        payload.get("transcript_text_exposed_in_console") is False,
        "Console transcript exposure marker mismatch.",
    )
    _require(payload.get("microphone_accessed") is False, "Microphone marker mismatch.")
    _require(payload.get("drc_repo_changed") is False, "DRC marker mismatch.")

    print("v540_req5_private_evidence_status: accepted-by-validator")
    print("v540_actual_openai_sdk_imported: True")
    print("v540_actual_provider_client_created: True")
    print("v540_real_provider_execution_executed: True")
    print("v540_real_transcript_present: True")
    print("v540_provider_neutral_result_present: True")
    print("v540_private_credential_exposed: False")
    print("v540_private_audio_path_exposed: False")
    print("v540_raw_audio_exposed: False")
    print("v540_provider_payload_exposed: False")
    print("v540_transcript_text_exposed_in_console: False")
    print("v540_private_evidence_outside_repo: True")
    print("v540_private_staged_audio_cleanup_verified: True")
    print("v540_repo_clean_before_operator_run: True")
    print("v540_repo_clean_after_operator_run: True")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_req5_acceptance_sync_authorization: ready")
    print("[OK] v5.4.0 REQ-5 private real-provider evidence passed")


if __name__ == "__main__":
    main()
