\
"""Validate REQ-5 operator tooling without private or network execution."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHANGED_PATHS = {
    "README.md",
    "docs/v540_openai_adapter_client_injection_contract.md",
    "docs/v540_openai_fake_execution_boundary.md",
    "docs/v540_openai_private_real_provider_operator_acceptance.md",
    "docs/v540_openai_real_provider_runtime.md",
    "docs/v540_provider_execution_configuration_status.md",
    "docs/v540_real_stt_provider_execution_requirements.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "scripts/operator_v540_openai_private_real_provider_acceptance.py",
    "scripts/smoke_v540_openai_private_real_provider_operator_acceptance.py",
    "scripts/smoke_v540_openai_real_provider_runtime.py",
    "scripts/verify_v540_openai_private_real_provider_evidence.py",
}


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


def _git_lines(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }


def _changed_paths() -> set[str]:
    return (
        _git_lines("diff", "--name-only")
        | _git_lines("diff", "--cached", "--name-only")
        | _git_lines("ls-files", "--others", "--exclude-standard")
    ) - {".vscode/settings.json"}


def _validate_surface() -> None:
    actual = _changed_paths()
    _require(
        actual == EXPECTED_CHANGED_PATHS,
        "REQ-5 changed surface mismatch:\n"
        f"expected={sorted(EXPECTED_CHANGED_PATHS)}\n"
        f"actual={sorted(actual)}",
    )
    _ok("REQ-5 worktree contains the exact twelve-file operator-tooling surface")


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
    adapter_doc = _read(
        "docs/v540_openai_adapter_client_injection_contract.md"
    )
    fake_doc = _read("docs/v540_openai_fake_execution_boundary.md")
    operator_doc = _read(
        "docs/v540_openai_private_real_provider_operator_acceptance.md"
    )
    runtime_doc = _read("docs/v540_openai_real_provider_runtime.md")
    status_doc = _read(
        "docs/v540_provider_execution_configuration_status.md"
    )
    requirements = _read(
        "docs/v540_real_stt_provider_execution_requirements.md"
    )
    checklist = _read(
        "docs/v540_real_stt_provider_execution_small_commit_checklist.md"
    )

    combined = "\n".join(
        (
            readme,
            adapter_doc,
            fake_doc,
            operator_doc,
            runtime_doc,
            status_doc,
            requirements,
            checklist,
        )
    )
    for marker in (
        "REQ-4: ACCEPTED",
        "REQ-5: IMPLEMENTED / NOT_ACCEPTED",
        "private WAV",
        "private credential",
        "real transcript",
        "private evidence outside the repository",
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

    current_req5_sections = {
        "README REQ-5 section": readme_req5,
        "REQ-5 operator document": operator_doc,
        "requirements REQ-5 checkpoint": requirements_req5,
        "checklist REQ-5 section": checklist_req5,
    }
    blocked_marker = "release readiness: BLOCKED pending REQ-5 acceptance"
    for label, text in current_req5_sections.items():
        _require(
            "REQ-5: IMPLEMENTED / NOT_ACCEPTED" in text,
            f"REQ-5 current marker missing from {label}",
        )
        _require(
            blocked_marker in text,
            f"REQ-5 blocked release-readiness marker missing from {label}",
        )
        for forbidden in (
            "REQ-5: ACCEPTED",
            "release readiness: READY pending next small commit",
            "real OpenAI transcription succeeded",
        ):
            _require(
                forbidden not in text,
                f"REQ-5 current section contains premature marker "
                f"{forbidden!r}: {label}",
            )

    _ok("REQ-5 docs record operator tooling as implemented-not-accepted")


def _validate_operator_source() -> None:
    source = _read(
        "scripts/operator_v540_openai_private_real_provider_acceptance.py"
    )
    tree = ast.parse(source)
    imported_modules: set[str] = set()
    print_literals: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "print"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    print_literals.append(arg.value)

    _require("openai" not in imported_modules, "operator must use Framework lazy import")
    for marker in (
        "REAL_CONFIRMATION",
        "PRIVATE_CONFIRMATION",
        "OPENAI_LOG",
        "private_staged_audio.wav",
        "private_transcript.txt",
        "operator_evidence.json",
        "staged_audio.unlink",
        "real_provider_execution_executed",
        "private_auth_value_exposed",
    ):
        _require(marker in source, f"operator source missing marker: {marker}")

    joined_prints = "\n".join(print_literals).lower()
    for forbidden in (
        "audio-path",
        "evidence-root",
        "api_key",
        "transcript:",
        "provider payload",
    ):
        _require(
            forbidden not in joined_prints,
            f"operator literal print may expose private data: {forbidden}",
        )
    _ok("REQ-5 operator source keeps private data outside public console output")


def _validate_no_execution_help() -> None:
    env = dict(__import__("os").environ)
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
    _require(
        "sk-" not in result.stdout,
        "operator help exposed a credential-like value",
    )
    _require("openai" not in sys.modules, "REQ-5 smoke imported actual OpenAI SDK")
    _ok("REQ-5 operator help is network-free and credential-free")


def main() -> None:
    _validate_surface()
    _validate_docs()
    _validate_operator_source()
    _validate_no_execution_help()

    print("v540_req5_operator_tooling_status: implemented-not-accepted")
    print("v540_req5_private_real_provider_execution_performed_in_smoke: False")
    print("v540_req5_actual_openai_sdk_imported_in_smoke: False")
    print("v540_req5_actual_provider_client_created_in_smoke: False")
    print("v540_req5_private_credential_read_in_smoke: False")
    print("v540_req5_private_audio_read_in_smoke: False")
    print("v540_req5_network_request_executed_in_smoke: False")
    print("v540_req5_private_evidence_written_in_smoke: False")
    print("v540_req5_transcript_text_exposed: False")
    print("v540_req5_microphone_accessed: False")
    print("v540_req5_drc_repo_changed: False")
    print("v540_req5_operator_execution_authorization: ready-after-source-acceptance")
    print("[OK] v5.4.0 REQ-5 private operator tooling boundary passed")


if __name__ == "__main__":
    main()
