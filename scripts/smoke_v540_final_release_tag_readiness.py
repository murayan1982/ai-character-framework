"""v5.4.0 final release tag-readiness gate.

Local checkpoint mode:
    python scripts/smoke_v540_final_release_tag_readiness.py --allow-dirty

Strict pre-tag mode after committing this checkpoint and rebuilding the final
package from the clean committed tree:
    python scripts/smoke_v540_final_release_tag_readiness.py \
        --require-clean-tree --require-package

This gate never creates a tag, pushes, publishes, imports the actual OpenAI SDK,
reads API credentials/private evidence/private audio/private transcripts,
creates a provider client, executes a network request, accesses a microphone,
or modifies DRC.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "5.4.0"
TAG = f"v{VERSION}"
PACKAGE = ROOT / "release" / f"ai-character-framework_v{VERSION}.zip"
SIDECAR = PACKAGE.with_suffix(PACKAGE.suffix + ".sha256")
EXPECTED_REMOTE_FRAGMENT = "ai-character-framework"

CHECKPOINT_WORKTREE = {
    "README.md",
    "docs/release_notes_v5.4.0.md",
    "docs/v540_final_release_tag_readiness.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "scripts/smoke_v540_final_release_tag_readiness.py",
}

REQUIRED_PACKAGE_ENTRIES = {
    "README.md",
    "docs/release_notes_v5.4.0.md",
    "docs/v540_final_release_tag_readiness.md",
    "docs/v540_release_package_gate.md",
    "docs/v540_release_readiness_gate.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "framework/openai_voice_input_real_provider.py",
    "framework/voice_input_provider_execution.py",
    "scripts/build_v540_release_package.py",
    "scripts/smoke_v540_final_release_tag_readiness.py",
    "scripts/smoke_v540_release_package_gate.py",
    "scripts/smoke_v540_release_readiness_gate.py",
}

FORBIDDEN_PRIVATE_BASENAMES = {
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
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        env=env,
        check=check,
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


def _load_builder():
    builder_path = ROOT / "scripts" / "build_v540_release_package.py"
    spec = importlib.util.spec_from_file_location(
        "build_v540_release_package",
        builder_path,
    )
    _require(
        spec is not None and spec.loader is not None,
        "could not load v5.4.0 package builder",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_strict_dependency(
    script: str,
    *extra_args: str,
) -> None:
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env.pop("OPENAI_LOG", None)
    env.pop("FW_REQ5_AUDIO_PATH", None)

    completed = subprocess.run(
        [sys.executable, script, *extra_args],
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
        raise AssertionError(f"strict tag-readiness dependency failed: {script}")
    print(f"[OK] strict tag-readiness dependency passed: {script}")


def _validate_docs() -> None:
    doc = _read(ROOT / "docs" / "v540_final_release_tag_readiness.md")
    notes = _read(ROOT / "docs" / "release_notes_v5.4.0.md")
    checklist = _read(
        ROOT
        / "docs"
        / "v540_real_stt_provider_execution_small_commit_checklist.md"
    )
    readme = _read(ROOT / "README.md")
    combined = "\n".join((doc, notes, checklist, readme))

    for marker in (
        "v5.4.0 final tag readiness: ACCEPTED",
        "v5.4.0 tag/push: READY after clean committed package rebuild",
        "v540_final_tag_readiness_status: accepted",
        "v540_final_package_rebuild_required_after_checkpoint_commit: True",
        "v540_tag_authorization: ready-after-strict-package-verification",
        "REQ-1: ACCEPTED",
        "REQ-2: ACCEPTED",
        "REQ-3: ACCEPTED",
        "REQ-4: ACCEPTED",
        "REQ-5: ACCEPTED",
        "Real STT Provider Execution",
        "private evidence remained outside the repository",
        "does not create a tag",
        "does not push or publish",
    ):
        _require(marker in combined, f"tag-readiness docs missing: {marker}")

    _require(
        "## v5.4.0 final release tag readiness" in readme,
        "README missing v5.4.0 final tag-readiness section",
    )
    _require(
        "## v5.4.0 final release tag readiness" in checklist,
        "checklist missing v5.4.0 final tag-readiness section",
    )
    _require(
        "release_notes_v5.4.0.md" in readme,
        "README missing v5.4.0 release-notes link",
    )
    _ok("v5.4.0 final tag-readiness documentation is present")


def _validate_git_state(
    *,
    allow_dirty: bool,
    require_clean_tree: bool,
    allow_existing_tag: bool,
) -> str:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    _require(len(head) == 40, "git HEAD should resolve to a full commit SHA")

    branch = _run("git", "branch", "--show-current").stdout.strip()
    _require(branch == "main", f"expected main branch, found: {branch}")

    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require(
        EXPECTED_REMOTE_FRAGMENT.lower() in origin.lower(),
        "origin does not appear to be the Framework repository",
    )

    changed = _changed_paths()
    if require_clean_tree:
        _require(
            not changed,
            "working tree must be clean before final tag readiness: "
            + ", ".join(sorted(changed)),
        )
        _ok("working tree is clean for final tag readiness")
    elif allow_dirty:
        _require(
            changed == CHECKPOINT_WORKTREE,
            "local checkpoint worktree differs from expected five files: "
            + ", ".join(sorted(changed)),
        )
        _ok("local checkpoint worktree matches the exact five-file surface")
    else:
        _require(
            not changed,
            "working tree is dirty; use --allow-dirty only for the exact "
            "uncommitted checkpoint surface",
        )
        _ok("working tree is clean")

    tag_check = _run(
        "git",
        "rev-parse",
        "--verify",
        f"refs/tags/{TAG}",
        check=False,
    )
    if tag_check.returncode == 0:
        _require(allow_existing_tag, f"{TAG} already exists")
        _ok(f"{TAG} already exists and was explicitly allowed")
    else:
        _ok(f"{TAG} does not already exist locally")

    _ok(f"git HEAD resolves: {head}")
    _ok("branch and origin match the Framework release target")
    return head


def _validate_current_package_set(builder) -> list[str]:
    files = builder.package_files(ROOT)
    for required in REQUIRED_PACKAGE_ENTRIES:
        _require(
            required in files,
            f"tracked package set missing tag-readiness entry: {required}",
        )

    lower_basenames = {Path(item).name.lower() for item in files}
    _require(
        not (lower_basenames & FORBIDDEN_PRIVATE_BASENAMES),
        "tracked package set includes a private REQ-5 artifact",
    )
    _require(
        not any(item.lower().endswith(".wav") for item in files),
        "tracked package set includes WAV audio",
    )
    _ok("tracked package set includes final tag-readiness files")
    return files


def _parse_sidecar() -> tuple[str, str]:
    text = SIDECAR.read_text(
        encoding="utf-8",
        errors="strict",
    ).strip()
    match = re.fullmatch(r"([0-9a-fA-F]{64})\s{2}(.+)", text)
    _require(match is not None, "SHA-256 sidecar format is invalid")
    assert match is not None
    return match.group(1).lower(), match.group(2)


def _validate_final_package(builder, expected_files: list[str]) -> str:
    _require(PACKAGE.is_file(), f"missing final package: {PACKAGE}")
    _require(SIDECAR.is_file(), f"missing SHA-256 sidecar: {SIDECAR}")

    expected_hash, sidecar_name = _parse_sidecar()
    _require(
        sidecar_name == PACKAGE.name,
        "sidecar filename does not match final ZIP",
    )

    final_bytes = PACKAGE.read_bytes()
    actual_hash = hashlib.sha256(final_bytes).hexdigest()
    _require(
        expected_hash == actual_hash,
        "final ZIP SHA-256 does not match sidecar",
    )

    with zipfile.ZipFile(PACKAGE, "r") as archive:
        names = archive.namelist()
        bad_entry = archive.testzip()

    _require(bad_entry is None, f"ZIP integrity failure at: {bad_entry}")
    _require(
        len(names) == len(set(names)),
        "final ZIP contains duplicate entries",
    )
    _require(
        names == expected_files,
        "final ZIP does not match the current committed package set",
    )

    for required in REQUIRED_PACKAGE_ENTRIES:
        _require(
            required in names,
            f"final ZIP missing tag-readiness entry: {required}",
        )

    lower_basenames = {Path(name).name.lower() for name in names}
    _require(
        not (lower_basenames & FORBIDDEN_PRIVATE_BASENAMES),
        "final ZIP contains a private REQ-5 artifact",
    )
    _require(
        ".vscode/settings.json" not in names,
        "final ZIP contains local VS Code settings",
    )
    _require(
        not any(name.startswith("release/") for name in names),
        "final ZIP contains generated release artifacts",
    )
    _require(
        not any(
            name.lower().endswith(".env")
            or "/.env" in name.lower()
            for name in names
        ),
        "final ZIP contains an environment file",
    )
    _require(
        not any(name.lower().endswith(".wav") for name in names),
        "final ZIP contains WAV audio",
    )

    with tempfile.TemporaryDirectory(
        prefix="acf_v540_tag_ready_verify_"
    ) as temporary:
        rebuilt = Path(temporary) / builder.PACKAGE_BASENAME
        rebuilt_hash, rebuilt_count = builder.build_package(
            rebuilt,
            root=ROOT,
        )
        _require(
            rebuilt_count == len(expected_files),
            "rebuilt package file count mismatch",
        )
        _require(
            rebuilt_hash == actual_hash,
            "final package is not deterministic for current HEAD",
        )
        _require(
            rebuilt.read_bytes() == final_bytes,
            "rebuilt ZIP bytes differ from final ZIP",
        )

    _ok("final v5.4.0 ZIP and sidecar match current HEAD")
    _ok("final package membership and deterministic rebuild passed")
    return actual_hash


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run v5.4.0 final release tag-readiness checks"
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow only the exact uncommitted five-file checkpoint surface",
    )
    parser.add_argument(
        "--require-clean-tree",
        action="store_true",
        help="Require a clean committed tree before tag creation",
    )
    parser.add_argument(
        "--require-package",
        action="store_true",
        help="Require and verify the final v5.4.0 ZIP and sidecar",
    )
    parser.add_argument(
        "--allow-existing-tag",
        action="store_true",
        help="Allow the local v5.4.0 tag to already exist",
    )
    args = parser.parse_args(argv)

    _require(
        not (args.allow_dirty and args.require_clean_tree),
        "--allow-dirty and --require-clean-tree are mutually exclusive",
    )
    _require(
        args.require_package == args.require_clean_tree,
        "--require-package and --require-clean-tree must be used together",
    )
    _require(
        "openai" not in sys.modules,
        "actual OpenAI SDK loaded before tag-readiness gate",
    )

    _validate_docs()
    head = _validate_git_state(
        allow_dirty=args.allow_dirty,
        require_clean_tree=args.require_clean_tree,
        allow_existing_tag=args.allow_existing_tag,
    )

    builder = _load_builder()
    _require(
        "openai" not in sys.modules,
        "package builder imported the actual OpenAI SDK",
    )
    expected_files = _validate_current_package_set(builder)

    package_hash = "not-required-in-local-checkpoint"
    if args.require_package:
        _run_strict_dependency(
            "scripts/smoke_v540_release_package_gate.py",
            "--allow-final-package",
        )
        _run_strict_dependency("scripts/check_release_package.py")
        package_hash = _validate_final_package(builder, expected_files)
    else:
        _ok(
            "strict package-gate and final ZIP verification are deferred "
            "until the checkpoint is committed"
        )

    _require(
        "openai" not in sys.modules,
        "actual OpenAI SDK loaded during tag-readiness gate",
    )

    strict_ready = bool(args.require_package and args.require_clean_tree)

    print("v540_final_tag_readiness_status: accepted")
    print("v540_final_tag_readiness_head:", head)
    print("v540_final_package_sha256:", package_hash)
    print(
        "v540_final_package_rebuild_required_after_checkpoint_commit:",
        not strict_ready,
    )
    print(
        "v540_final_package_verified_for_current_head:",
        strict_ready,
    )
    print("v540_release_notes_present: True")
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
    print("v540_publish_performed: False")
    print(
        "v540_tag_authorization:",
        (
            "ready-after-strict-package-verification"
            if strict_ready
            else "blocked-pending-clean-commit-and-package-rebuild"
        ),
    )
    _ok("v5.4.0 final release tag-readiness gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
