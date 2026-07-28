\
"""v5.4.0 deterministic release-package gate smoke.

This smoke builds the package twice in temporary directories, verifies identical
SHA-256 digests and archive entries, and re-runs the accepted source-tree
readiness and prior package regressions.

It does not write the final package under ``release/``, import the actual OpenAI
SDK, read credentials/private evidence/private audio/transcripts, create a
provider client, execute a network request, access a microphone, modify DRC,
create a tag, push, or publish.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DEPENDENCIES = (
    "scripts/smoke_v540_release_readiness_gate.py",
    "scripts/smoke_v530_release_package_gate.py",
    "scripts/check_release_package.py",
)

ALLOWED_ACCEPTANCE_WORKTREE = {
    "README.md",
    "docs/v540_release_package_gate.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "scripts/build_v540_release_package.py",
    "scripts/smoke_v540_release_package_gate.py",
    "scripts/smoke_v540_release_readiness_gate.py",
}

REQUIRED_ZIP_ENTRIES = {
    "README.md",
    "framework/__init__.py",
    "framework/voice_input_provider_execution.py",
    "framework/openai_voice_input_provider_adapter.py",
    "framework/openai_voice_input_fake_execution.py",
    "framework/openai_voice_input_real_provider.py",
    "docs/v540_release_readiness_gate.md",
    "docs/v540_release_package_gate.md",
    "docs/v540_openai_private_real_provider_operator_acceptance.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "scripts/operator_v540_openai_private_real_provider_acceptance.py",
    "scripts/verify_v540_openai_private_real_provider_evidence.py",
    "scripts/smoke_v540_release_readiness_gate.py",
    "scripts/smoke_v540_release_package_gate.py",
    "scripts/build_v540_release_package.py",
}

FORBIDDEN_BASENAMES = {
    "operator_evidence.json",
    "private_transcript.txt",
    "private_staged_audio.wav",
    "private_stt_sample.wav",
}


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _read(path: Path) -> str:
    _require(path.is_file(), f"missing required file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def _run(
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_lines(*args: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in _run("git", *args).stdout.splitlines()
        if line.strip()
    }


def _changed_paths() -> set[str]:
    return (
        _git_lines("diff", "--name-only")
        | _git_lines("diff", "--cached", "--name-only")
        | _git_lines("ls-files", "--others", "--exclude-standard")
    ) - {".vscode/settings.json"}


def _load_builder():
    path = ROOT / "scripts" / "build_v540_release_package.py"
    spec = importlib.util.spec_from_file_location(
        "build_v540_release_package",
        path,
    )
    _require(
        spec is not None and spec.loader is not None,
        "could not load v5.4.0 release package builder",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        raise AssertionError(f"release package dependency failed: {script}")
    print(f"[OK] release package dependency passed: {script}")


def _validate_docs() -> None:
    doc = _read(ROOT / "docs" / "v540_release_package_gate.md")
    checklist = _read(
        ROOT
        / "docs"
        / "v540_real_stt_provider_execution_small_commit_checklist.md"
    )
    readme = _read(ROOT / "README.md")
    combined = "\n".join((doc, checklist, readme))

    for marker in (
        "v5.4.0 release package gate: ACCEPTED",
        "v5.4.0 tag/push: READY pending final release package build",
        "v540_release_package_gate_status: accepted",
        "v540_release_package_dry_run_succeeded: True",
        "v540_release_package_deterministic: True",
        "v540_tag_authorization: ready-for-final-release-package-build",
        "does not create the final release package",
        "does not create a tag",
        "does not execute a real provider",
        "does not modify DRC",
    ):
        _require(marker in combined, f"package-gate docs missing: {marker}")

    _require(
        "## v5.4.0 release package gate" in readme,
        "README missing v5.4.0 release package gate",
    )
    _require(
        "## v5.4.0 release package gate" in checklist,
        "checklist missing v5.4.0 release package gate",
    )
    _ok("v5.4.0 release package gate documentation is present")


def _validate_worktree_scope() -> None:
    changed = _changed_paths()
    _require(
        not changed or changed == ALLOWED_ACCEPTANCE_WORKTREE,
        "release-package gate worktree contains unexpected paths: "
        + ", ".join(sorted(changed)),
    )
    _ok("release-package gate worktree scope is safe")


def _validate_package_set(builder) -> list[str]:
    files = builder.package_files(ROOT)
    for required in builder.REQUIRED_PACKAGE_FILES:
        _require(
            required in files,
            f"builder package set missing required file: {required}",
        )

    lower_names = {Path(item).name.lower() for item in files}
    _require(
        not (lower_names & FORBIDDEN_BASENAMES),
        "builder package set includes a private artifact",
    )
    _require(
        ".vscode/settings.json" not in files,
        "package includes local VS Code settings",
    )
    _require(
        not any(item.startswith("release/") for item in files),
        "package includes generated release artifacts",
    )
    _require(
        not any(
            item.lower().endswith(".env")
            or "/.env" in item.lower()
            for item in files
        ),
        "package includes an environment file",
    )
    _require(
        not any(item.lower().endswith(".wav") for item in files),
        "package includes private/raw WAV audio",
    )
    _ok("v5.4.0 release package file set is public-safe")
    return files


def _archive_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path, "r") as archive:
        bad = archive.testzip()
        _require(bad is None, f"ZIP integrity failure at: {bad}")
        return set(archive.namelist())


def _validate_deterministic_dry_run(builder, files: list[str]) -> None:
    with tempfile.TemporaryDirectory(
        prefix="acf_v540_package_gate_"
    ) as temp:
        base = Path(temp)
        first = base / "first" / builder.PACKAGE_BASENAME
        second = base / "second" / builder.PACKAGE_BASENAME

        digest1, count1 = builder.build_package(first, root=ROOT)
        digest2, count2 = builder.build_package(second, root=ROOT)

        _require(first.is_file(), "first dry-run ZIP missing")
        _require(second.is_file(), "second dry-run ZIP missing")
        _require(
            first.with_suffix(first.suffix + ".sha256").is_file(),
            "first dry-run SHA-256 sidecar missing",
        )
        _require(
            second.with_suffix(second.suffix + ".sha256").is_file(),
            "second dry-run SHA-256 sidecar missing",
        )
        _require(len(digest1) == 64, "first SHA-256 is not 64 hex chars")
        _require(len(digest2) == 64, "second SHA-256 is not 64 hex chars")
        _require(digest1 == digest2, "repeated package build is not deterministic")
        _require(count1 == len(files), "first package file count mismatch")
        _require(count2 == len(files), "second package file count mismatch")

        names1 = _archive_names(first)
        names2 = _archive_names(second)
        _require(names1 == names2, "repeated package entries differ")
        _require(names1 == set(files), "ZIP entries differ from package file set")

        for required in REQUIRED_ZIP_ENTRIES:
            _require(
                required in names1,
                f"dry-run package missing required entry: {required}",
            )

        lower_basenames = {Path(name).name.lower() for name in names1}
        _require(
            not (lower_basenames & FORBIDDEN_BASENAMES),
            "dry-run ZIP includes a private artifact",
        )
        _require(
            ".vscode/settings.json" not in names1,
            "dry-run ZIP includes local VS Code settings",
        )
        _require(
            not any(name.startswith("release/") for name in names1),
            "dry-run ZIP includes release artifacts",
        )
        _require(
            not any(
                name.lower().endswith(".env")
                or "/.env" in name.lower()
                for name in names1
            ),
            "dry-run ZIP includes an environment file",
        )
        _require(
            not any(name.lower().endswith(".wav") for name in names1),
            "dry-run ZIP includes WAV audio",
        )

    final_zip = ROOT / "release" / builder.PACKAGE_BASENAME
    final_sidecar = final_zip.with_suffix(final_zip.suffix + ".sha256")
    _require(
        not final_zip.exists(),
        "package gate created the final release ZIP",
    )
    _require(
        not final_sidecar.exists(),
        "package gate created the final release SHA-256 sidecar",
    )

    _ok("v5.4.0 deterministic temporary package build passed")


def main() -> None:
    _validate_docs()
    _validate_worktree_scope()

    _require(
        "openai" not in sys.modules,
        "actual OpenAI SDK loaded before package gate",
    )
    builder = _load_builder()
    _require(
        "openai" not in sys.modules,
        "release package builder imported the actual OpenAI SDK",
    )

    files = _validate_package_set(builder)
    _validate_deterministic_dry_run(builder, files)

    for dependency in DEPENDENCIES:
        _run_dependency(dependency)

    _require(
        "openai" not in sys.modules,
        "actual OpenAI SDK loaded during package gate",
    )

    print("v540_release_package_gate_status: accepted")
    print("v540_release_package_dry_run_succeeded: True")
    print("v540_release_package_deterministic: True")
    print("v540_release_package_created_in_release_dir: False")
    print("v540_release_package_sha256_present: True")
    print("v540_release_package_excludes_vscode_settings: True")
    print("v540_release_package_excludes_private_evidence: True")
    print("v540_release_package_excludes_private_transcript: True")
    print("v540_release_package_excludes_private_audio: True")
    print("v540_release_package_excludes_env_files: True")
    print("v540_actual_openai_sdk_imported_in_gate: False")
    print("v540_actual_provider_client_created_in_gate: False")
    print("v540_provider_execution_executed_in_gate: False")
    print("v540_network_request_executed_in_gate: False")
    print("v540_private_credential_read_in_gate: False")
    print("v540_private_evidence_read_in_gate: False")
    print("v540_private_audio_read_in_gate: False")
    print("v540_private_transcript_read_in_gate: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_tag_created: False")
    print("v540_push_performed: False")
    print("v540_tag_authorization: ready-for-final-release-package-build")
    _ok("v5.4.0 release package gate passed")


if __name__ == "__main__":
    main()
