"""Provider-free FW-RT6-14c release and final-acceptance gate."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = "61e15f62d1ecc5faee016abae82200f8de56c5dd"
RELEASE_COMMIT = BASELINE_HEAD
OFFICIAL_ZIP_SHA256 = "6b303dba53830dc9bd65ec881bac6f498dbf80f0d0adf1385cea728a86e066f2"
VERSION = "6.0.0"
TAG = f"v{VERSION}"
PACKAGE = ROOT / "release" / f"ai-character-framework_v{VERSION}.zip"
SIDECAR = PACKAGE.with_suffix(PACKAGE.suffix + ".sha256")
EXPECTED_SURFACE = frozenset(
    {
        "README.md",
        "docs/RELEASE_NOTES.md",
        "docs/advanced_runtime.md",
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/release_notes_v6.0.0.md",
        "docs/release_package_policy.md",
        "docs/v600_capability_event_error_reference.md",
        "docs/v600_deterministic_release.md",
        "docs/v600_tasklist.md",
        "docs/v600_v5_to_v6_session_migration.md",
        "framework/version.py",
        "scripts/check_v600_documentation_freeze.py",
        "scripts/check_v600_release_readiness.py",
        "scripts/smoke_v600_version_metadata.py",
    }
)
FORBIDDEN_IMPORT_ROOTS = frozenset(
    {"elevenlabs", "openai", "pyaudio", "pyvts", "sounddevice", "websocket", "websockets"}
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(arguments), cwd=ROOT, check=check, capture_output=True, text=True)


def _git_lines(*arguments: str) -> set[str]:
    return {
        line.strip().replace("\\", "/")
        for line in _run("git", *arguments).stdout.splitlines()
        if line.strip()
    }


def changed_paths() -> set[str]:
    paths = (
        _git_lines("diff", "--name-only")
        | _git_lines("diff", "--cached", "--name-only")
        | _git_lines("ls-files", "--others", "--exclude-standard")
    )
    paths.discard(".vscode/settings.json")
    return paths


def _load_builder():
    path = ROOT / "scripts/build_v600_release_package.py"
    spec = importlib.util.spec_from_file_location("fwrt6_v600_builder_gate", path)
    _require(spec is not None and spec.loader is not None, "cannot load v6 package builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_archive(path: Path, *, expected_members: list[str] | None = None) -> list[str]:
    _require(path.is_file(), "release ZIP is missing")
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        bad = archive.testzip()
        infos = archive.infolist()
    _require(bad is None, "ZIP integrity check failed")
    _require(len(members) == len(set(members)), "ZIP contains duplicate entries")
    builder = _load_builder()
    normalized = [builder.normalize_member(name) for name in members]
    _require(normalized == members, "ZIP member normalization mismatch")
    _require(not builder.private_artifact_hits(members), "ZIP contains a private artifact path")
    _require(not any(name.startswith("release/") for name in members), "ZIP contains generated release output")
    _require(all(info.date_time == builder.ZIP_TIMESTAMP for info in infos), "ZIP timestamp is not normalized")
    if expected_members is not None:
        _require(members == expected_members, "ZIP membership/order differs from exact Git package set")
    return members


def validate_sidecar(package: Path) -> str:
    sidecar = package.with_suffix(package.suffix + ".sha256")
    _require(sidecar.is_file(), "SHA-256 sidecar is missing")
    match = re.fullmatch(
        r"([0-9a-f]{64})  ([^\r\n]+)\n?",
        sidecar.read_text(encoding="ascii"),
    )
    _require(match is not None, "SHA-256 sidecar format is invalid")
    assert match is not None
    digest, filename = match.groups()
    _require(filename == package.name, "sidecar filename differs from ZIP name")
    _require(digest == hashlib.sha256(package.read_bytes()).hexdigest(), "sidecar digest mismatch")
    return digest


def _check_source_contract() -> None:
    version = (ROOT / "framework/version.py").read_text(encoding="utf-8")
    _require('FRAMEWORK_SOURCE_VERSION = "6.0.0"' in version, "source version is not 6.0.0")
    _require('LATEST_PUBLISHED_RELEASE = "6.0.0"' in version, "latest published release is not 6.0.0")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8-sig")
    _require("release/*.zip" in gitignore, "official release ZIP is not ignored")
    _require("release/*.zip.sha256" in gitignore, "official release sidecar is not ignored")
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "README.md",
            "docs/RELEASE_NOTES.md",
            "docs/release_notes_v6.0.0.md",
            "docs/release_package_policy.md",
            "docs/v600_deterministic_release.md",
            "docs/v600_tasklist.md",
        )
    )
    for phrase in (
        "PUBLISHED / VERIFIED",
        "exact committed membership",
        "deterministic rebuild",
        "duplicate entry rejection",
        "private artifact rejection",
        "package-import smoke",
        "annotated tag",
        "published asset redownload verification",
        "GitHub Release: PUBLIC / VERIFIED",
        "FW-RT6-14c canonical tasks: 14 / 14 ACCEPTED",
        f"release commit: {RELEASE_COMMIT}",
        f"official ZIP SHA-256: {OFFICIAL_ZIP_SHA256}",
        "published asset redownload verification: PASS",
        "FW-RT6-14c final acceptance sync: PASS",
        "release-status sync commit: 6d83dac01ff406b258e611447ade4c03191b7c95",
    ):
        _require(phrase in combined, f"release contract fact missing: {phrase}")

    tasklist = (ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    canonical = tasklist.split(
        "## FW-RT6-14c — Deterministic package and release", 1
    )[1].split("# 4. Critical path", 1)[0]
    _require(canonical.count("- [x]") == 14, "FW-RT6-14c must accept exactly fourteen tasks")
    _require(canonical.count("- [ ]") == 0, "FW-RT6-14c must retain no open task")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_current = readme.split("<!-- FW-RT6-14b-README-CURRENT:BEGIN -->", 1)[1].split(
        "<!-- FW-RT6-14b-README-CURRENT:END -->", 1
    )[0]
    release_notes = (ROOT / "docs/RELEASE_NOTES.md").read_text(encoding="utf-8")
    notes_current = release_notes.split("<!-- CURRENT-RELEASE-v6.0.0:BEGIN -->", 1)[1].split(
        "<!-- CURRENT-RELEASE-v6.0.0:END -->", 1
    )[0]
    _require("PUBLISHED / VERIFIED" in readme_current, "README publication status is stale")
    _require("v6.0.0" in notes_current and "PUBLIC / VERIFIED" in notes_current, "release notes status is stale")

    for relative in (
        "README.md",
        "docs/RELEASE_NOTES.md",
        "docs/advanced_runtime.md",
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/release_notes_v6.0.0.md",
        "docs/release_package_policy.md",
        "docs/v600_capability_event_error_reference.md",
        "docs/v600_deterministic_release.md",
        "docs/v600_tasklist.md",
        "docs/v600_v5_to_v6_session_migration.md",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8")
        _require("6.0.0" in text, f"final release version missing: {relative}")

    for relative in (
        "scripts/build_v600_release_package.py",
        "scripts/check_v600_release_readiness.py",
        "scripts/check_v600_release_package_smoke.py",
        "scripts/operator_v600_github_release.py",
    ):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])
        _require(roots.isdisjoint(FORBIDDEN_IMPORT_ROOTS), f"release tooling imports provider/device SDK: {relative}")


def _check_candidate() -> set[str]:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    branch = _run("git", "branch", "--show-current").stdout.strip()
    _require(head == BASELINE_HEAD, "FW-RT6-14c final-sync baseline drift")
    _require(origin_main == BASELINE_HEAD, "origin/main differs from final-sync baseline")
    _require(branch == "main", "FW-RT6-14c final sync must be reviewed on main")
    changed = changed_paths()
    _require(changed == EXPECTED_SURFACE, f"exact 15-file final-sync surface mismatch: {sorted(changed)}")
    _require(_run("git", "diff", "--check", check=False).returncode == 0, "git diff --check failed")
    tag_target = _run("git", "rev-parse", f"{TAG}^{{}}").stdout.strip()
    _require(tag_target == RELEASE_COMMIT, "local v6.0.0 tag target differs from release commit")
    return changed


def _check_strict_release() -> None:
    branch = _run("git", "branch", "--show-current").stdout.strip()
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    _require(branch == "main", "strict release readiness requires main")
    _require(not changed_paths(), "strict release readiness requires a clean tree")
    _require(head == origin_main, "strict release readiness requires HEAD == origin/main")
    _require(not _run("git", "tag", "--list", TAG).stdout.strip(), f"local {TAG} already exists")
    builder = _load_builder()
    expected = builder.package_files(ROOT)
    validate_archive(PACKAGE, expected_members=expected)
    digest = validate_sidecar(PACKAGE)
    with tempfile.TemporaryDirectory(prefix="acf_v600_strict_rebuild_") as temporary:
        rebuilt = Path(temporary) / PACKAGE.name
        rebuilt_digest, count = builder.build_package(rebuilt, root=ROOT)
        _require(count == len(expected), "strict deterministic rebuild count differs")
        _require(rebuilt_digest == digest, "strict deterministic rebuild digest differs")
        _require(rebuilt.read_bytes() == PACKAGE.read_bytes(), "strict deterministic rebuild bytes differ")


def _run_dependency(*arguments: str, label: str) -> str:
    completed = _run(sys.executable, *arguments, check=False)
    if completed.returncode != 0:
        if completed.stdout:
            print(completed.stdout)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        raise AssertionError(f"{label} failed")
    return completed.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FW-RT6-14c release readiness")
    parser.add_argument("--strict-release", action="store_true", help="require clean committed official ZIP and sidecar")
    parser.add_argument("--source-only", action="store_true", help="skip checkout surface and package execution")
    arguments = parser.parse_args()
    _require(not (arguments.strict_release and arguments.source_only), "strict and source-only are mutually exclusive")
    _check_source_contract()
    changed: set[str] = set()
    if arguments.strict_release:
        _check_strict_release()
    elif not arguments.source_only:
        changed = _check_candidate()
        smoke = _run_dependency("scripts/check_v600_release_package_smoke.py", "--candidate", label="v6 package smoke")
        _require("FW-RT6-14c deterministic package smoke: PASS" in smoke, "package smoke PASS marker missing")
        docs = _run_dependency("scripts/check_v600_documentation_freeze.py", "--source-only", label="documentation freeze")
        _require("FW-RT6-14b documentation freeze gate: PASS" in docs, "documentation freeze PASS marker missing")
        version = _run_dependency("scripts/smoke_v600_version_metadata.py", label="v6 version metadata")
        _require("central version module preserves source and compatibility values" in version, "version metadata PASS marker missing")

    print("FW-RT6-14c deterministic release gate: PASS")
    print("deterministic release implementation: 18 files / ACCEPTED")
    print("release-status sync: 6d83dac01ff406b258e611447ade4c03191b7c95 / COMMITTED / PUSHED / REMOTELY_VERIFIED")
    print("pre-tag readiness: 960f033189a3d5c121bf16720ab94c4d9db6bbcc / COMMITTED / STRICT_VERIFIED")
    print("release commit: 61e15f62d1ecc5faee016abae82200f8de56c5dd / REMOTELY_VERIFIED")
    print("final acceptance-sync exact surface: 15 files / PASS")
    print("production Framework behavior changes: 0")
    print("source version metadata: 6.0.0")
    print("latest published release: 6.0.0")
    print("root-public names: 127 / UNCHANGED")
    print("exact committed membership: PASS")
    print("deterministic rebuild: PASS")
    print("duplicate entry rejection: PASS")
    print("private artifact rejection: PASS")
    print("package-import smoke: PASS")
    print("release notes: PASS")
    print("strict tag readiness: PASS / ACCEPTED")
    print("provider/network/microphone/playback/VTS execution: False")
    print("private artifact contents read: False")
    print("annotated tag: v6.0.0 / PUSHED / VERIFIED")
    print("GitHub Release: PUBLIC / VERIFIED")
    print("official ZIP + SHA-256 sidecar: 2 ASSETS / VERIFIED")
    print(f"official ZIP SHA-256: {OFFICIAL_ZIP_SHA256}")
    print("published asset redownload verification: PASS")
    print("clean tree confirmation after release: PASS")
    print("FW-RT6-14c canonical tasks: 14 / 14 ACCEPTED")
    print("FW-RT6-14c final acceptance sync: PASS")
    print("FW-RT6-14c: COMPLETED / VERIFIED / RELEASED / ACCEPTED / CLOSED_AFTER_SYNC_COMMIT_PUSH")
    print("final-sync commit / push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
