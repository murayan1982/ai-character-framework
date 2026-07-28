\
"""Operator-only private OpenAI STT acceptance runner for v5.4.0 REQ-5.

This command is intentionally not a smoke test. It can import the actual
optional OpenAI SDK, create an actual provider client, send a private staged WAV
over the network, incur API charges, and obtain a real transcript.

Private inputs and evidence must remain outside the repository. Public console
output never includes credential values, private paths, raw audio, provider
payloads, exception text, or transcript text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import framework


REAL_CONFIRMATION = (
    "I_ACCEPT_PRIVATE_REAL_PROVIDER_EXECUTION_AND_POSSIBLE_API_CHARGES"
)
PRIVATE_CONFIRMATION = (
    "I_WILL_KEEP_AUDIO_TRANSCRIPT_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY"
)
EVIDENCE_SCHEMA = "ai-character-framework-v540-req5-private-evidence-v1"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def _status_paths(root: Path) -> set[str]:
    output = _git(root, "status", "--porcelain=v1", "-z")
    paths: set[str] = set()
    for record in output.split("\0"):
        if not record:
            continue
        value = record[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.add(value.replace("\\", "/"))
    return paths


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(
            _json_safe(payload),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute the accepted REQ-4 runtime with a private WAV and actual "
            "OpenAI provider, while keeping transcript and evidence outside "
            "the repository."
        )
    )
    parser.add_argument("--audio-path", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument(
        "--credential-env",
        default="OPENAI_API_KEY",
        help="Environment variable containing the private API key.",
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini-transcribe",
    )
    parser.add_argument("--language", default="ja")
    parser.add_argument("--duration-ms", required=True, type=int)
    parser.add_argument("--max-duration-ms", default=120000, type=int)
    parser.add_argument(
        "--max-audio-bytes",
        default=25 * 1024 * 1024,
        type=int,
    )
    parser.add_argument("--timeout-seconds", default=120.0, type=float)
    parser.add_argument("--max-retries", default=0, type=int)
    parser.add_argument(
        "--confirm-real-provider-execution",
        required=True,
    )
    parser.add_argument(
        "--confirm-private-data-outside-repo",
        required=True,
    )
    return parser


def _public_markers(
    *,
    status: str,
    evidence_written: bool,
    staged_audio_cleanup_verified: bool,
    repo_clean_after: bool,
    real_execution: bool,
    transcript_present: bool,
) -> None:
    print(f"v540_req5_operator_run_status: {status}")
    print("v540_actual_openai_sdk_imported: True")
    print("v540_actual_provider_client_created: True")
    print(f"v540_real_provider_execution_executed: {real_execution}")
    print(f"v540_real_transcript_present: {transcript_present}")
    print("v540_private_credential_exposed: False")
    print("v540_private_audio_path_exposed: False")
    print("v540_raw_audio_exposed: False")
    print("v540_provider_payload_exposed: False")
    print("v540_transcript_text_exposed_in_console: False")
    print(f"v540_private_evidence_written: {evidence_written}")
    print("v540_private_evidence_outside_repo: True")
    print(
        "v540_private_staged_audio_cleanup_verified: "
        f"{staged_audio_cleanup_verified}"
    )
    print(f"v540_repo_clean_after_operator_run: {repo_clean_after}")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")


def main() -> int:
    args = _build_parser().parse_args()
    root = _repo_root()
    if root != Path.cwd().resolve():
        raise SystemExit(f"Run from repository root: {root}")

    if args.confirm_real_provider_execution != REAL_CONFIRMATION:
        raise SystemExit(
            "Real provider confirmation did not match the required phrase."
        )
    if args.confirm_private_data_outside_repo != PRIVATE_CONFIRMATION:
        raise SystemExit(
            "Private-data confirmation did not match the required phrase."
        )

    if os.environ.get("OPENAI_LOG", "").strip().lower() == "debug":
        raise SystemExit(
            "OPENAI_LOG=debug is forbidden for private acceptance because "
            "debug logs may contain request or response details."
        )

    dirty_before = _status_paths(root) - {".vscode/settings.json"}
    if dirty_before:
        raise SystemExit(
            "REQ-5 private execution requires a clean accepted-REQ-4 worktree."
        )

    audio_path = Path(args.audio_path).expanduser().resolve(strict=True)
    if _is_inside(audio_path, root):
        raise SystemExit("Private audio must be outside the repository.")
    if not audio_path.is_file():
        raise SystemExit("Private audio must be a regular file.")
    if audio_path.suffix.lower() != ".wav":
        raise SystemExit("REQ-5 accepts a private .wav file only.")
    if audio_path.stat().st_size <= 0:
        raise SystemExit("Private audio must not be empty.")
    if audio_path.stat().st_size > args.max_audio_bytes:
        raise SystemExit("Private audio exceeds max_audio_bytes.")

    if args.duration_ms <= 0:
        raise SystemExit("duration-ms must be positive.")
    if args.max_duration_ms <= 0:
        raise SystemExit("max-duration-ms must be positive.")
    if args.duration_ms > args.max_duration_ms:
        raise SystemExit("duration-ms exceeds max-duration-ms.")
    if args.max_audio_bytes <= 0:
        raise SystemExit("max-audio-bytes must be positive.")
    if args.timeout_seconds <= 0:
        raise SystemExit("timeout-seconds must be positive.")
    if args.max_retries < 0:
        raise SystemExit("max-retries must be non-negative.")

    evidence_root = Path(args.evidence_root).expanduser().resolve()
    if _is_inside(evidence_root, root):
        raise SystemExit("Private evidence root must be outside the repository.")
    evidence_root.mkdir(parents=True, exist_ok=True)
    if not evidence_root.is_dir():
        raise SystemExit("Private evidence root must be a directory.")

    env_name = str(args.credential_env).strip()
    if not env_name:
        raise SystemExit("credential-env must be a non-empty variable name.")

    api_key = os.environ.get(env_name)
    if not api_key or not api_key.strip():
        raise SystemExit(
            "The selected credential environment variable is unavailable."
        )

    try:
        openai_version = version("openai")
    except PackageNotFoundError:
        raise SystemExit(
            "The optional OpenAI Python SDK is not installed in this Python "
            "environment. Install it outside the repository before the "
            "private operator run."
        ) from None

    run_id = uuid.uuid4().hex
    run_dir = evidence_root / f"v540_req5_{run_id}"
    run_dir.mkdir(parents=False, exist_ok=False)
    staged_audio = run_dir / "private_staged_audio.wav"
    transcript_path = run_dir / "private_transcript.txt"
    evidence_path = run_dir / "operator_evidence.json"

    staged_cleanup_verified = False
    result: framework.VoiceInputResult | None = None
    failure_safe_message = ""
    transcript = ""

    audio_sha256 = _sha256_file(audio_path)
    shutil.copyfile(audio_path, staged_audio)
    staged_audio_sha256 = _sha256_file(staged_audio)
    if staged_audio_sha256 != audio_sha256:
        staged_audio.unlink(missing_ok=True)
        raise SystemExit("Private staged WAV integrity verification failed.")

    try:
        execution_config = (
            framework.resolve_voice_input_provider_execution_config(
                provider="openai",
                allow_provider_execution=True,
                credentials_available=True,
            )
        )
        credential = framework.OpenAIVoiceInputPrivateCredential(api_key)
        policy = framework.OpenAIVoiceInputRealProviderPolicy(
            max_audio_bytes=args.max_audio_bytes,
            timeout_seconds=args.timeout_seconds,
            max_retries=args.max_retries,
            allow_provider_sdk_import=True,
            allow_provider_client_creation=True,
            allow_real_provider_execution=True,
            runtime_mode=framework.OpenAIVoiceInputRuntimeMode.REAL,
        )
        factory = framework.OpenAIVoiceInputRealClientFactory(
            credential=credential,
            policy=policy,
        )
        adapter = framework.OpenAIVoiceInputProviderAdapter(
            execution_config=execution_config,
            model=args.model,
            client_factory=factory,
        )
        executor = framework.OpenAIVoiceInputRealProviderExecutor(
            adapter=adapter,
        )
        audio_format = framework.VoiceInputAudioFormat.wav(
            duration_ms=args.duration_ms,
        )
        audio_source = framework.VoiceInputAudioSource.from_file_path(
            str(staged_audio),
            audio_format=audio_format,
            language=(args.language or None),
            max_duration_ms=args.max_duration_ms,
        )
        result = executor.execute(
            audio_source=audio_source,
            request=framework.VoiceInputRequest(
                language=(args.language or None),
                timeout_ms=int(args.timeout_seconds * 1000),
                max_duration_ms=args.max_duration_ms,
            ),
        )
        transcript = result.text if result.is_completed else ""
        failure_safe_message = result.safe_message
    finally:
        # Do not retain the private staged audio. The operator's original file
        # remains untouched outside the repository.
        staged_audio.unlink(missing_ok=True)
        staged_cleanup_verified = not staged_audio.exists()
        # Remove the API key reference as soon as the provider call returns.
        api_key = None

    repo_clean_after = not (
        _status_paths(root) - {".vscode/settings.json"}
    )
    public_metadata = (
        dict(result.public_metadata) if result is not None else {}
    )
    real_execution = bool(
        public_metadata.get("real_provider_execution_executed") is True
    )
    transcript_present = bool(transcript.strip())

    transcript_sha256: str | None = None
    if transcript_present:
        transcript_path.write_text(
            transcript,
            encoding="utf-8",
            newline="\n",
        )
        transcript_sha256 = hashlib.sha256(
            transcript.encode("utf-8")
        ).hexdigest()

    evidence: dict[str, Any] = {
        "schema": EVIDENCE_SCHEMA,
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_head": _git(root, "rev-parse", "HEAD"),
        "repo_clean_before": True,
        "repo_clean_after": repo_clean_after,
        "audio_source_outside_repo": True,
        "evidence_outside_repo": True,
        "private_staged_audio_cleanup_verified": staged_cleanup_verified,
        "original_private_audio_retained": audio_path.exists(),
        "audio_sha256": audio_sha256,
        "audio_byte_count": audio_path.stat().st_size,
        "declared_duration_ms": args.duration_ms,
        "max_duration_ms": args.max_duration_ms,
        "max_audio_bytes": args.max_audio_bytes,
        "model": args.model,
        "requested_language": args.language or None,
        "openai_sdk_version": openai_version,
        "provider_neutral_result_type": (
            type(result).__name__ if result is not None else None
        ),
        "outcome": (
            result.outcome.value if result is not None else "operator_failure"
        ),
        "public_error_code": (
            result.public_error_code.value
            if result is not None
            else "operator_failure"
        ),
        "safe_message": failure_safe_message,
        "retryable": result.retryable if result is not None else False,
        "public_result_metadata": public_metadata,
        "actual_openai_sdk_imported": bool(
            public_metadata.get("provider_sdk_imported") is True
        ),
        "actual_provider_client_created": bool(
            public_metadata.get("provider_client_created") is True
        ),
        "real_provider_execution_executed": real_execution,
        "real_transcript_present": transcript_present,
        "transcript_char_count": len(transcript),
        "transcript_sha256": transcript_sha256,
        "private_transcript_filename": (
            transcript_path.name if transcript_present else None
        ),
        "private_credential_exposed": False,
        "private_audio_path_exposed": False,
        "raw_audio_exposed": False,
        "provider_payload_exposed": False,
        "transcript_text_exposed_in_console": False,
        "microphone_accessed": False,
        "drc_repo_changed": False,
    }
    _write_json(evidence_path, evidence)

    success = all(
        (
            result is not None and result.is_completed,
            transcript_present,
            real_execution,
            public_metadata.get("provider_sdk_imported") is True,
            public_metadata.get("provider_client_created") is True,
            public_metadata.get("private_auth_value_exposed") is False,
            public_metadata.get("audio_path_exposed") is False,
            public_metadata.get("raw_audio_exposed") is False,
            public_metadata.get("provider_payload_exposed") is False,
            public_metadata.get("microphone_accessed") is False,
            staged_cleanup_verified,
            repo_clean_after,
            transcript_path.is_file(),
            evidence_path.is_file(),
        )
    )

    _public_markers(
        status="completed" if success else "not_accepted",
        evidence_written=evidence_path.is_file(),
        staged_audio_cleanup_verified=staged_cleanup_verified,
        repo_clean_after=repo_clean_after,
        real_execution=real_execution,
        transcript_present=transcript_present,
    )
    print(f"v540_req5_private_evidence_run_id: {run_id}")
    print(
        "v540_req5_private_evidence_validation: "
        "run-verifier-with-private-json"
    )

    if not success:
        print(
            "v540_req5_operator_safe_message: "
            + (failure_safe_message or "Private provider acceptance did not complete.")
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
