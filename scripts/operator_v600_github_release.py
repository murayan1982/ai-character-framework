"""Explicit operator for the v6.0.0 annotated tag and GitHub Release.

Importing this module and using ``--plan`` are read-only.  ``--execute`` is
rejected unless three exact, separate authorization phrases are supplied.  The
operator never reads Framework provider credentials or private evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = "6.0.0"
TAG = f"v{VERSION}"
PACKAGE = ROOT / "release" / f"ai-character-framework_v{VERSION}.zip"
SIDECAR = PACKAGE.with_suffix(PACKAGE.suffix + ".sha256")
NOTES = ROOT / "docs/release_notes_v6.0.0.md"
TAG_CONFIRMATION = "I_AUTHORIZE_CREATE_AND_PUSH_V600_ANNOTATED_TAG"
RELEASE_CONFIRMATION = "I_AUTHORIZE_PUBLIC_GITHUB_RELEASE_AND_ASSET_UPLOAD"
IRREVERSIBLE_CONFIRMATION = "I_ACCEPT_PUBLIC_RELEASE_ACTIONS_ARE_IRREVERSIBLE"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _run(
    *arguments: str,
    check: bool = True,
    expose_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(arguments),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        raise RuntimeError("authorized release command failed")
    if expose_output and completed.stdout:
        print(completed.stdout.rstrip())
    return completed


def _load(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    _require(spec is not None and spec.loader is not None, f"unable to load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ask(current: str | None, prompt: str) -> str:
    if current is not None:
        return current
    return input(f"Type {prompt}: ").strip()


def _assert_authorized(arguments: argparse.Namespace) -> None:
    tag = _ask(arguments.tag_confirmation, TAG_CONFIRMATION)
    release = _ask(arguments.release_confirmation, RELEASE_CONFIRMATION)
    irreversible = _ask(arguments.irreversible_confirmation, IRREVERSIBLE_CONFIRMATION)
    _require(tag == TAG_CONFIRMATION, "annotated tag authorization did not match")
    _require(release == RELEASE_CONFIRMATION, "GitHub Release authorization did not match")
    _require(irreversible == IRREVERSIBLE_CONFIRMATION, "irreversible-action authorization did not match")


def _preflight() -> str:
    _require(shutil.which("git") is not None, "git executable is unavailable")
    _require(shutil.which("gh") is not None, "GitHub CLI executable is unavailable")
    _require(NOTES.is_file(), "v6.0.0 release notes are missing")
    _run("git", "fetch", "origin", "main", "--tags")
    branch = _run("git", "branch", "--show-current").stdout.strip()
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    status = _run("git", "status", "--porcelain", "--untracked-files=all").stdout.strip()
    _require(branch == "main", "release execution requires main")
    _require(head == origin_main, "release execution requires HEAD == origin/main")
    _require(not status, "release execution requires a clean tree")
    _require(not _run("git", "tag", "--list", TAG).stdout.strip(), "local v6.0.0 tag already exists")
    remote_tag = _run("git", "ls-remote", "--tags", "origin", f"refs/tags/{TAG}").stdout.strip()
    _require(not remote_tag, "remote v6.0.0 tag already exists")
    release_view = _run("gh", "release", "view", TAG, check=False)
    _require(release_view.returncode != 0, "GitHub Release v6.0.0 already exists")
    return head


def _build_and_verify() -> str:
    builder = _load("scripts/build_v600_release_package.py", "fwrt6_operator_builder")
    builder.build_package(PACKAGE, root=ROOT)
    gate = _run(sys.executable, "scripts/check_v600_release_readiness.py", "--strict-release", check=False)
    _require(gate.returncode == 0, "strict v6.0.0 tag readiness failed")
    _require("FW-RT6-14c deterministic release gate: PASS" in gate.stdout, "strict readiness PASS marker missing")
    return hashlib.sha256(PACKAGE.read_bytes()).hexdigest()


def _publish(head: str, digest: str) -> None:
    message = "AI Character Framework v6.0.0"
    _run("git", "tag", "-a", TAG, "-m", message, head)
    _run("git", "push", "origin", TAG)
    _run(
        "gh",
        "release",
        "create",
        TAG,
        str(PACKAGE),
        str(SIDECAR),
        "--verify-tag",
        "--title",
        message,
        "--notes-file",
        str(NOTES),
    )

    with tempfile.TemporaryDirectory(prefix="acf_v600_redownload_") as temporary:
        download = Path(temporary)
        _run("gh", "release", "download", TAG, "--dir", str(download), "--pattern", PACKAGE.name)
        _run("gh", "release", "download", TAG, "--dir", str(download), "--pattern", SIDECAR.name)
        downloaded_zip = download / PACKAGE.name
        downloaded_sidecar = download / SIDECAR.name
        _require(downloaded_zip.is_file() and downloaded_sidecar.is_file(), "published assets were not redownloaded")
        _require(hashlib.sha256(downloaded_zip.read_bytes()).hexdigest() == digest, "published ZIP digest differs")
        _require(downloaded_sidecar.read_bytes() == SIDECAR.read_bytes(), "published sidecar differs")

    remote_tag = _run("git", "ls-remote", "--tags", "origin", f"refs/tags/{TAG}^{{}}").stdout.strip()
    _require(remote_tag.startswith(head), "remote annotated tag target differs from HEAD")
    _require(not _run("git", "status", "--porcelain", "--untracked-files=all").stdout.strip(), "tree is dirty after release")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan or execute the v6.0.0 GitHub Release")
    parser.add_argument("--plan", action="store_true", help="show the non-executing release plan")
    parser.add_argument("--execute", action="store_true", help="perform tag push and public GitHub Release")
    parser.add_argument("--tag-confirmation")
    parser.add_argument("--release-confirmation")
    parser.add_argument("--irreversible-confirmation")
    arguments = parser.parse_args()
    _require(not (arguments.plan and arguments.execute), "--plan and --execute are mutually exclusive")

    print("fwrt6_14c_release_operator_status: starting")
    print(f"fwrt6_14c_release_operator_mode: {'execute' if arguments.execute else 'plan'}")
    print("fwrt6_14c_provider_network_device_execution: False")
    print("fwrt6_14c_private_configuration_evidence_read: False")
    if not arguments.execute:
        print("fwrt6_14c_annotated_tag_push_github_release: NOT_AUTHORIZED / NOT_RUN")
        print("fwrt6_14c_release_operator_status: plan-complete")
        return

    _assert_authorized(arguments)
    head = _preflight()
    digest = _build_and_verify()
    _publish(head, digest)
    print("fwrt6_14c_release_operator_status: completed")
    print(f"fwrt6_14c_release_commit: {head}")
    print(f"fwrt6_14c_annotated_tag: {TAG} / VERIFIED")
    print("fwrt6_14c_tag_push: VERIFIED")
    print("fwrt6_14c_github_release: PUBLISHED")
    print("fwrt6_14c_official_zip_sidecar: VERIFIED")
    print("fwrt6_14c_published_asset_redownload: VERIFIED")
    print("fwrt6_14c_repository_clean_after: True")


if __name__ == "__main__":
    main()
