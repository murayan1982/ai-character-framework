\
"""Regression check for committed REQ-5 private operator tooling.

This smoke is source-only and network-free. It does not require an uncommitted
twelve-file worktree; it validates the committed operator boundary plus any
subsequent focused repair worktree.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"Missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="replace")


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _section(
    text: str,
    start_marker: str,
    end_marker: str | None = None,
) -> str:
    start = text.find(start_marker)
    _require(start >= 0, f"Missing section marker: {start_marker}")
    if end_marker is None:
        return text[start:]
    end = text.find(end_marker, start + len(start_marker))
    _require(end >= 0, f"Missing section end marker: {end_marker}")
    return text[start:end]


def _validate_docs() -> None:
    readme = _read("README.md")
    operator_doc = _read(
        "docs/v540_openai_private_real_provider_operator_acceptance.md"
    )
    runtime_doc = _read("docs/v540_openai_real_provider_runtime.md")
    requirements = _read(
        "docs/v540_real_stt_provider_execution_requirements.md"
    )
    checklist = _read(
        "docs/v540_real_stt_provider_execution_small_commit_checklist.md"
    )
    combined = "\n".join(
        (readme, operator_doc, runtime_doc, requirements, checklist)
    )

    for marker in (
        "REQ-4: ACCEPTED",
        "REQ-5: IMPLEMENTED / NOT_ACCEPTED",
        "release readiness: BLOCKED pending REQ-5 acceptance",
        "private WAV",
        "private credential",
        "real transcript",
        "private evidence outside the repository",
        "provider_error_type",
        "provider_http_status",
        "operator_v540_openai_private_real_provider_acceptance.py",
        "verify_v540_openai_private_real_provider_evidence.py",
    ):
        _require(marker in combined, f"REQ-5 docs missing marker: {marker}")

    readme_req5 = _section(
        readme,
        "## v5.4.0 candidate REQ-5 private real-provider operator acceptance",
    )
    requirements_req5 = _section(
        requirements,
        "## REQ-5 private operator acceptance checkpoint",
    )
    checklist_req5 = _section(
        checklist,
        "## REQ-5 - Private real-provider operator acceptance",
        "## REQ-6 - DRC released-FW adoption gate",
    )

    for label, text in (
        ("README REQ-5 section", readme_req5),
        ("operator document", operator_doc),
        ("requirements REQ-5 checkpoint", requirements_req5),
        ("checklist REQ-5 section", checklist_req5),
    ):
        _require(
            "REQ-5: IMPLEMENTED / NOT_ACCEPTED" in text,
            f"REQ-5 current marker missing from {label}",
        )
        _require(
            "release readiness: BLOCKED pending REQ-5 acceptance" in text,
            f"REQ-5 release block missing from {label}",
        )
        _require(
            "REQ-5: ACCEPTED" not in text,
            f"REQ-5 premature acceptance marker in {label}",
        )

    _ok("REQ-5 committed operator-tooling documentation remains valid")


def _validate_operator_source() -> None:
    source = _read(
        "scripts/operator_v540_openai_private_real_provider_acceptance.py"
    )
    tree = ast.parse(source)
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)

    _require("openai" not in imported_modules, "operator imported OpenAI eagerly")
    for marker in (
        "REPO_ROOT = Path(__file__).resolve().parents[1]",
        "REAL_CONFIRMATION",
        "PRIVATE_CONFIRMATION",
        "OPENAI_LOG",
        "private_staged_audio.wav",
        "private_transcript.txt",
        "operator_evidence.json",
        "staged_audio.unlink",
        "provider_error_type",
        "provider_http_status",
        "v540_req5_provider_runtime_status",
        "v540_req5_provider_error_type",
        "v540_req5_provider_http_status",
    ):
        _require(marker in source, f"operator source missing marker: {marker}")

    for forbidden in (
        "print(api_key",
        "print(transcript",
        "print(audio_path",
        "print(evidence_root",
        "print(exc",
        "print(response",
    ):
        _require(
            forbidden not in source,
            f"operator may print private/provider data: {forbidden}",
        )
    _ok("REQ-5 operator source keeps diagnostics public-safe")


def _validate_no_execution_help() -> None:
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_LOG", None)
    result = subprocess.run(
        [
            sys.executable,
            "scripts/operator_v540_openai_private_real_provider_acceptance.py",
            "--help",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    _require(
        "--confirm-real-provider-execution" in result.stdout,
        "operator help missing real-execution confirmation",
    )
    _require(
        "--confirm-private-data-outside-repo" in result.stdout,
        "operator help missing private-data confirmation",
    )
    _require("sk-" not in result.stdout, "operator help exposed credential-like data")
    _require("openai" not in sys.modules, "smoke imported actual OpenAI SDK")
    _ok("REQ-5 operator help remains network-free and credential-free")


def main() -> None:
    _validate_docs()
    _validate_operator_source()
    _validate_no_execution_help()

    print("v540_req5_operator_tooling_status: implemented-not-accepted")
    print("v540_req5_committed_source_regression_status: accepted")
    print("v540_req5_safe_api_status_diagnostics_present: True")
    print("v540_req5_private_real_provider_execution_performed_in_smoke: False")
    print("v540_req5_actual_openai_sdk_imported_in_smoke: False")
    print("v540_req5_actual_provider_client_created_in_smoke: False")
    print("v540_req5_private_credential_read_in_smoke: False")
    print("v540_req5_private_audio_read_in_smoke: False")
    print("v540_req5_network_request_executed_in_smoke: False")
    print("v540_req5_private_evidence_written_in_smoke: False")
    print("v540_req5_provider_error_body_exposed: False")
    print("v540_req5_provider_response_exposed: False")
    print("v540_req5_request_id_exposed: False")
    print("v540_req5_transcript_text_exposed: False")
    print("v540_req5_microphone_accessed: False")
    print("v540_req5_drc_repo_changed: False")
    print("v540_req5_private_retry_authorization: ready-after-repair-commit")
    print("[OK] v5.4.0 REQ-5 committed operator tooling regression passed")


if __name__ == "__main__":
    main()
