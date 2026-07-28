\
"""v5.4.0 source-tree release readiness gate.

This gate is mock-safe and public-source-only. It validates accepted REQ-1
through REQ-5, the public REQ-5 acceptance sync, v5.3/v5.2 regressions, and the
baseline release-package check.

It does not import the actual OpenAI SDK, read credentials/private evidence/
private audio/transcripts, create a provider client, execute a network request,
access a microphone, modify DRC, build a release package, create a tag, push, or
publish.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEPENDENCIES = (
    "scripts/smoke_v540_provider_execution_configuration_status.py",
    "scripts/smoke_v540_openai_adapter_client_injection_contract.py",
    "scripts/smoke_v540_openai_fake_execution_boundary.py",
    "scripts/smoke_v540_openai_real_provider_runtime.py",
    "scripts/smoke_v540_openai_private_real_provider_operator_acceptance.py",
    "scripts/smoke_v540_real_stt_provider_execution_requirements.py",
    "scripts/smoke_v530_release_readiness_gate.py",
    "scripts/smoke_v520_release_readiness_gate.py",
    "scripts/check_release_package.py",
)

PUBLIC_V540_SYMBOLS = (
    "OpenAIVoiceInputPrivateCredential",
    "OpenAIVoiceInputRuntimeMode",
    "OpenAIVoiceInputRealProviderStatus",
    "OpenAIVoiceInputRealProviderPolicy",
    "OpenAIVoiceInputRealClientFactory",
    "OpenAIVoiceInputRealProviderExecutor",
)

ALLOWED_ACCEPTANCE_WORKTREE = {
    "README.md",
    "docs/v540_release_readiness_gate.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "scripts/smoke_v540_release_readiness_gate.py",
}

FORBIDDEN_PRIVATE_TRACKED_MARKERS = (
    "operator_evidence.json",
    "private_transcript.txt",
    "private_staged_audio.wav",
    "private_stt_sample.wav",
)


def _read(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"Missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8", errors="replace")


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_lines(*args: str) -> set[str]:
    output = _run("git", *args).stdout
    return {
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    }


def _changed_paths() -> set[str]:
    return (
        _git_lines("diff", "--name-only")
        | _git_lines("diff", "--cached", "--name-only")
        | _git_lines("ls-files", "--others", "--exclude-standard")
    ) - {".vscode/settings.json"}


def _run_dependency(script: str) -> None:
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_LOG", None)
    env.pop("FW_REQ5_AUDIO_PATH", None)

    completed = subprocess.run(
        [sys.executable, script],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        raise AssertionError(f"readiness dependency failed: {script}")
    print(f"[OK] readiness dependency passed: {script}")


def _validate_docs() -> None:
    doc = _read(ROOT / "docs" / "v540_release_readiness_gate.md")
    checklist = _read(
        ROOT
        / "docs"
        / "v540_real_stt_provider_execution_small_commit_checklist.md"
    )
    readme = _read(ROOT / "README.md")
    combined = "\n".join((doc, checklist, readme))

    for marker in (
        "v5.4.0 release readiness: ACCEPTED",
        "v5.4.0 release package/tag: READY pending next small commit",
        "v540_release_readiness_gate_status: accepted",
        "v540_release_package_authorization: ready-for-release-package-gate",
        "REQ-1: ACCEPTED",
        "REQ-2: ACCEPTED",
        "REQ-3: ACCEPTED",
        "REQ-4: ACCEPTED",
        "REQ-5: ACCEPTED",
        "v540_req5_private_evidence_status: accepted-by-validator",
        "private evidence remained outside the repository",
        "does not create the release package",
        "does not create a tag",
        "does not modify DRC",
    ):
        _require(marker in combined, f"release-readiness docs missing: {marker}")

    _require(
        "## v5.4.0 release readiness gate" in readme,
        "README missing v5.4.0 release readiness section",
    )
    _require(
        "## v5.4.0 release readiness gate" in checklist,
        "checklist missing v5.4.0 release readiness section",
    )

    _ok("v5.4.0 release readiness gate documentation is present")


def _validate_worktree_scope() -> None:
    changed = _changed_paths()
    _require(
        not changed or changed == ALLOWED_ACCEPTANCE_WORKTREE,
        "release-readiness gate worktree contains unexpected paths: "
        + ", ".join(sorted(changed)),
    )
    _ok("release-readiness gate worktree scope is safe")


def _validate_private_artifacts_not_tracked() -> None:
    tracked = _git_lines("ls-files")
    hits = sorted(
        item
        for item in tracked
        if any(
            marker.lower() in item.lower()
            for marker in FORBIDDEN_PRIVATE_TRACKED_MARKERS
        )
    )
    _require(
        not hits,
        "private REQ-5 artifact is tracked: " + ", ".join(hits),
    )
    _ok("private REQ-5 artifacts are absent from tracked source")


def _validate_no_v540_release_outputs() -> None:
    package = ROOT / "release" / "ai-character-framework_v5.4.0.zip"
    sidecars = (
        ROOT / "release" / "ai-character-framework_v5.4.0.zip.sha256",
        ROOT / "release" / "ai-character-framework_v5.4.0.sha256.txt",
    )
    _require(not package.exists(), "v5.4.0 release package already exists")
    _require(
        not any(path.exists() for path in sidecars),
        "v5.4.0 release checksum sidecar already exists",
    )

    local_tag = _run("git", "tag", "--list", "v5.4.0").stdout.strip()
    _require(not local_tag, "v5.4.0 tag already exists")
    _ok("v5.4.0 release package and tag remain uncreated")


def _validate_public_import() -> None:
    _require(
        "openai" not in sys.modules,
        "actual OpenAI SDK loaded before Framework import",
    )

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import framework

    _require(
        "openai" not in sys.modules,
        "Framework root import loaded the actual OpenAI SDK",
    )

    for name in PUBLIC_V540_SYMBOLS:
        _require(
            hasattr(framework, name),
            f"framework missing v5.4.0 public symbol: {name}",
        )
        _require(
            name in getattr(framework, "__all__", ()),
            f"framework.__all__ missing v5.4.0 public symbol: {name}",
        )

    _ok("Framework root import remains v5.4.0 provider-safe")
    _ok("Framework exports the accepted v5.4.0 public runtime symbols")


def main() -> None:
    _validate_docs()
    _validate_worktree_scope()
    _validate_private_artifacts_not_tracked()
    _validate_no_v540_release_outputs()
    _validate_public_import()

    for dependency in DEPENDENCIES:
        _run_dependency(dependency)

    print("v540_release_readiness_gate_status: accepted")
    print("v540_req1_status: accepted")
    print("v540_req2_status: accepted")
    print("v540_req3_status: accepted")
    print("v540_req4_status: accepted")
    print("v540_req5_status: accepted")
    print("v540_req5_private_evidence_status: accepted-by-public-sync")
    print("v540_framework_root_import_provider_safe: True")
    print("v540_public_real_stt_runtime_symbols_present: True")
    print("v540_actual_openai_sdk_imported_in_gate: False")
    print("v540_actual_provider_client_created_in_gate: False")
    print("v540_network_request_executed_in_gate: False")
    print("v540_private_credential_read_in_gate: False")
    print("v540_private_evidence_read_in_gate: False")
    print("v540_private_audio_read_in_gate: False")
    print("v540_private_transcript_read_in_gate: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_release_package_created: False")
    print("v540_tag_created: False")
    print(
        "v540_release_package_authorization: "
        "ready-for-release-package-gate"
    )
    _ok("v5.4.0 source-tree release readiness gate passed")


if __name__ == "__main__":
    main()
