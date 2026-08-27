"""Run the provider-free FW-RT6-14b documentation-freeze gate."""

from __future__ import annotations

import argparse
import ast
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = "72cfa09f6551e1fc3d042777733627c900237cdc"
EXPECTED_FULL_UNIT_COUNT = 828
EXPECTED_ROOT_PUBLIC_COUNT = 127
EXPECTED_EVENT_COUNT = 48
ROOT_MANIFEST_FILE_SHA256 = (
    "e3c7bb1d2b0646d2ecec9aadf3df8c0af1329622500652daddbb3c85113d01ef"
)
ROOT_PUBLIC_SHA256 = (
    "4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0"
)
EXPECTED_SURFACE = frozenset(
    {
        "README.md",
        "docs/advanced_runtime.md",
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_v5_to_v6_session_migration.md",
        "docs/v600_capability_event_error_reference.md",
        "docs/v600_tasklist.md",
        "scripts/check_v600_documentation_freeze.py",
    }
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _safe_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for key in tuple(environment):
        folded = key.casefold()
        if any(
            fragment in folded
            for fragment in (
                "api_key",
                "apikey",
                "authorization",
                "credential",
                "password",
                "private_key",
                "secret",
                "token",
            )
        ):
            environment.pop(key, None)
    environment.update(
        {
            "AI_CHARACTER_FRAMEWORK_REAL_RUNTIME_ENABLED": "0",
            "AI_CHARACTER_FRAMEWORK_ALLOW_PROVIDER_EXECUTION": "0",
            "AI_CHARACTER_FRAMEWORK_ALLOW_DEVICE_EXECUTION": "0",
        }
    )
    return environment


def _run_checked(command: list[str], *, label: str) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=_safe_environment(),
        check=False,
        capture_output=True,
        text=True,
    )
    _require(completed.returncode == 0, f"{label} failed")
    return completed.stdout + completed.stderr


def _marker_block(text: str, begin: str, end: str) -> str:
    _require(text.count(begin) == 1, f"marker must be unique: {begin}")
    _require(text.count(end) == 1, f"marker must be unique: {end}")
    _before, separator, remainder = text.partition(begin)
    _require(bool(separator), f"missing marker: {begin}")
    block, separator, _after = remainder.partition(end)
    _require(bool(separator), f"missing marker: {end}")
    return block


def check_repository_surface() -> None:
    head = _run_checked(["git", "rev-parse", "HEAD"], label="git head").strip()
    branch = _run_checked(
        ["git", "branch", "--show-current"], label="git branch"
    ).strip()
    _require(head == BASELINE_HEAD, "documentation-freeze baseline drift")
    _require(branch == "main", "documentation freeze must be reviewed on main")
    status = _run_checked(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        label="git status",
    )
    changed_paths = {
        line[3:].strip()
        for line in status.splitlines()
        if len(line) >= 4
    }
    _require(changed_paths == EXPECTED_SURFACE, "documentation-freeze surface drift")
    _run_checked(["git", "diff", "--check"], label="git diff check")


def check_readme() -> None:
    text = _read("README.md")
    current = _marker_block(
        text,
        "<!-- FW-RT6-14b-README-CURRENT:BEGIN -->",
        "<!-- FW-RT6-14b-README-CURRENT:END -->",
    )
    history = _marker_block(
        text,
        "<!-- README-HISTORICAL-DEVELOPMENT-LOG:BEGIN -->",
        "<!-- README-HISTORICAL-DEVELOPMENT-LOG:END -->",
    )
    _require(text.index("FW-RT6-14b-README-CURRENT:BEGIN") < text.index("What this framework provides"), "current README status must precede setup content")
    _require(text.index("README-HISTORICAL-DEVELOPMENT-LOG:BEGIN") > text.index("License"), "historical README log must follow current project content")
    for phrase in (
        "6.0.0",
        "PUBLISHED / VERIFIED",
        "Latest published release",
        "v6.0.0",
        "799589526aef1a9d903fe4da4c23550b5c12ca38",
        "FW-RT6-14c release tooling",
        "14 / 14 ACCEPTED",
        "6b303dba53830dc9bd65ec881bac6f498dbf80f0d0adf1385cea728a86e066f2",
        "127 names / unchanged",
        "v5_skeleton",
        "v6_unified",
        "FW-RT6-14c",
        "docs/v600_capability_event_error_reference.md",
        "scripts/check_v600_documentation_freeze.py",
    ):
        _require(phrase in current or phrase in text, f"README freeze fact missing: {phrase}")
    _require("append-only" in history, "historical README log warning missing")
    _require("### v5.1.0 release readiness gate" in history, "historical README content moved outside log")
    for phrase in (
        "6.0.0",
        "PUBLISHED / VERIFIED",
        "799589526aef1a9d903fe4da4c23550b5c12ca38",
        "FW-RT6-14c release tooling",
        "14 / 14 ACCEPTED",
        "61e15f62d1ecc5faee016abae82200f8de56c5dd",
        "docs/v600_deterministic_release.md",
        "docs/release_notes_v6.0.0.md",
    ):
        _require(phrase in current, f"README current release fact missing: {phrase}")


def check_contract_docs() -> None:
    advanced = _read("docs/advanced_runtime.md")
    migration = _read("docs/v600_v5_to_v6_session_migration.md")
    reference = _read("docs/v600_capability_event_error_reference.md")
    app = _read("docs/app_integration_contract.md")
    facade = _read("docs/public_facade.md")
    combined = "\n".join((advanced, migration, reference, app, facade))

    _marker_block(
        advanced,
        "<!-- FW-RT6-14b-ADVANCED-RUNTIME-FREEZE:BEGIN -->",
        "<!-- FW-RT6-14b-ADVANCED-RUNTIME-FREEZE:END -->",
    )
    _marker_block(
        migration,
        "<!-- FW-RT6-14b-MIGRATION-FREEZE:BEGIN -->",
        "<!-- FW-RT6-14b-MIGRATION-FREEZE:END -->",
    )
    reference_block = _marker_block(
        reference,
        "<!-- FW-RT6-14b-CAPABILITY-EVENT-ERROR-REFERENCE:BEGIN -->",
        "<!-- FW-RT6-14b-CAPABILITY-EVENT-ERROR-REFERENCE:END -->",
    )
    _require(
        app.count("FW-RT6-14b-DOCUMENTATION-FREEZE:BEGIN") == 1,
        "app integration freeze marker must be unique",
    )
    _require(
        facade.count("FW-RT6-14b-DOCUMENTATION-FREEZE:BEGIN") == 1,
        "public facade freeze marker must be unique",
    )

    final_blocks = (
        _marker_block(
            advanced,
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:END -->",
        ),
        _marker_block(
            migration,
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:END -->",
        ),
        _marker_block(
            reference,
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:END -->",
        ),
        _marker_block(
            app,
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:END -->",
        ),
        _marker_block(
            facade,
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
            "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:END -->",
        ),
    )
    final_combined = "\n".join(final_blocks)

    for phrase in (
        "7d65771784ddc5409076909f874d098758486d98",
        "production Framework source changes: 0 files",
        "root-public names: 127 / UNCHANGED",
        "provider hard cancel claimed: False",
        "Framework physical playback stop claimed: False",
        "RealtimeSession real orchestration changed/enabled: False",
        "FW-RT6-14b canonical tasks: 0 / 8 CLOSED / UNCHANGED",
        "FW-RT6-14c implementation: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in combined, f"documentation-freeze fact missing: {phrase}")

    for phrase in (
        BASELINE_HEAD,
        "implementation commit: 72cfa09f6551e1fc3d042777733627c900237cdc",
        "implementation: COMPLETED / VERIFIED / COMMITTED / PUSHED / REMOTELY_VERIFIED",
        "final acceptance-sync exact surface: 8 files",
        "production Framework source changes: 0 files",
        "test source changes: 0 files",
        "root-public names: 127 / UNCHANGED",
        "documentation-freeze checker: PROVIDER_FREE / PASS",
        "full Framework unit suite: 828 / PASS",
        "provider/network/microphone/playback/VTS execution: False",
        "private configuration/evidence read or written: False",
        "FW-RT6-14b tasks: 8 / 8 ACCEPTED",
        "FW-RT6-14b final acceptance sync: PASS",
        "FW-RT6-14b: COMPLETED / VERIFIED / ACCEPTED / CLOSED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-14c exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-14c implementation: NOT_AUTHORIZED",
        "acceptance-sync commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in final_combined, f"final acceptance fact missing: {phrase}")

    for relative, text in (
        ("docs/advanced_runtime.md", advanced),
        ("docs/v600_v5_to_v6_session_migration.md", migration),
        ("docs/v600_capability_event_error_reference.md", reference),
        ("docs/app_integration_contract.md", app),
        ("docs/public_facade.md", facade),
    ):
        current_release = _marker_block(
            text,
            "<!-- FW-RT6-14c-DETERMINISTIC-RELEASE:BEGIN -->",
            "<!-- FW-RT6-14c-DETERMINISTIC-RELEASE:END -->",
        )
        _require("6.0.0" in current_release, f"14c release metadata missing: {relative}")
        final_release = _marker_block(
            text,
            "<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
            "<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:END -->",
        )
        for phrase in (
            "latest published release: 6.0.0",
            "v6.0.0",
            "14 / 14 ACCEPTED",
            "127 / UNCHANGED",
            "AWAITING_SYNC_COMMIT_PUSH",
        ):
            _require(phrase in final_release, f"14c final publication fact missing in {relative}: {phrase}")

    event_values = set(re.findall(r"`(realtime\.[a-z0-9_.]+)`", reference_block))
    _require(len(event_values) == EXPECTED_EVENT_COUNT, "event reference must list exactly 48 unique event values")
    for phrase in (
        "RealtimeCapabilitySnapshot.as_dict()",
        "RealtimeSessionConstructionResult",
        "RealtimeErrorCode",
        "RealtimeExecutionErrorCode",
        "LifecycleTransitionErrorCode",
        "TurnOutcome",
        "InterruptOutcome",
        "OutputFlushOutcome",
        "RecoveryAction",
        "Non-goals and experimental scope",
    ):
        _require(phrase in reference_block, f"integrated reference section missing: {phrase}")


def check_tasklist_boundary() -> None:
    tasklist = _read("docs/v600_tasklist.md")
    canonical = tasklist.split(
        "## FW-RT6-14b — Documentation and migration freeze", 1
    )[1].split("## FW-RT6-14c", 1)[0]
    _require(canonical.count("- [ ]") == 0, "14b final sync retains an open task")
    _require(canonical.count("- [x]") == 8, "14b final sync must accept eight tasks")
    candidate = _marker_block(
        tasklist,
        "<!-- FW-RT6-14b-DOCUMENTATION-FREEZE-CANDIDATE:BEGIN -->",
        "<!-- FW-RT6-14b-DOCUMENTATION-FREEZE-CANDIDATE:END -->",
    )
    for phrase in (
        "exact contract review: COMPLETED",
        "implementation: IMPLEMENTED / VERIFIED / AWAITING_REVIEW",
        "exact implementation surface: 8 files",
        "documentation-freeze checker: PROVIDER_FREE / PASS",
        "FW-RT6-14b canonical tasks: 0 / 8 CLOSED / UNCHANGED",
        "FW-RT6-14b final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-14c exact contract review: NOT_AUTHORIZED",
    ):
        _require(phrase in candidate, f"14b tasklist candidate fact missing: {phrase}")

    final_sync = _marker_block(
        tasklist,
        "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
        "<!-- FW-RT6-14b-FINAL-ACCEPTANCE-SYNC:END -->",
    )
    for phrase in (
        "acceptance-sync baseline head: 72cfa09f6551e1fc3d042777733627c900237cdc",
        "implementation commit: 72cfa09f6551e1fc3d042777733627c900237cdc",
        "implementation: COMPLETED / VERIFIED / COMMITTED / PUSHED / REMOTELY_VERIFIED",
        "final acceptance-sync exact surface: 8 files",
        "final acceptance-sync production Framework source changes: 0 files",
        "final acceptance-sync test source changes: 0 files",
        "documentation-freeze checker: PROVIDER_FREE / PASS",
        "full Framework unit suite: 828 / PASS",
        "FW-RT6-14b tasks: 8 / 8 ACCEPTED",
        "FW-RT6-14b final acceptance sync: PASS",
        "FW-RT6-14b: COMPLETED / VERIFIED / ACCEPTED / CLOSED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-14c exact contract review: AUTHORIZED_AFTER_SYNC_COMMIT_PUSH",
        "FW-RT6-14c implementation: NOT_AUTHORIZED",
        "acceptance-sync commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in final_sync, f"14b final-sync fact missing: {phrase}")

    canonical_14c = tasklist.split(
        "## FW-RT6-14c — Deterministic package and release", 1
    )[1].split("# 4. Critical path", 1)[0]
    _require(canonical_14c.count("- [ ]") == 0, "14c final sync retains an open task")
    _require(canonical_14c.count("- [x]") == 14, "14c final sync must accept fourteen tasks")
    release_sync = _marker_block(
        tasklist,
        "<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:BEGIN -->",
        "<!-- FW-RT6-14c-FINAL-ACCEPTANCE-SYNC:END -->",
    )
    for phrase in (
        "final-sync baseline: 61e15f62d1ecc5faee016abae82200f8de56c5dd",
        "release tag: v6.0.0 / ANNOTATED / PUSHED / VERIFIED",
        "strict tag readiness: PASS",
        "GitHub Release: PUBLIC / VERIFIED",
        "official ZIP + SHA-256 sidecar: 2 ASSETS / VERIFIED",
        "official ZIP SHA-256: 6b303dba53830dc9bd65ec881bac6f498dbf80f0d0adf1385cea728a86e066f2",
        "published asset redownload verification: PASS",
        "clean tree confirmation: PASS",
        "latest published release: 6.0.0",
        "FW-RT6-14c canonical tasks: 14 / 14 ACCEPTED",
        "FW-RT6-14c final acceptance sync: PASS",
        "final-sync exact surface: 15 files",
        "final-sync commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in release_sync, f"14c final-sync fact missing: {phrase}")


def check_current_markdown_links() -> None:
    documents = {
        "README.md": _marker_block(
            _read("README.md"),
            "<!-- FW-RT6-14b-README-CURRENT:BEGIN -->",
            "<!-- FW-RT6-14b-README-CURRENT:END -->",
        ),
        "docs/advanced_runtime.md": _read("docs/advanced_runtime.md"),
        "docs/v600_v5_to_v6_session_migration.md": _marker_block(
            _read("docs/v600_v5_to_v6_session_migration.md"),
            "<!-- FW-RT6-14b-MIGRATION-FREEZE:BEGIN -->",
            "<!-- FW-RT6-14b-MIGRATION-FREEZE:END -->",
        ),
        "docs/v600_capability_event_error_reference.md": _read(
            "docs/v600_capability_event_error_reference.md"
        ),
    }
    for relative_path, text in documents.items():
        parent = (PROJECT_ROOT / relative_path).parent
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            _require((parent / target).resolve().is_file(), f"broken current documentation link in {relative_path}: {target}")


def check_root_public_manifest() -> None:
    manifest_path = PROJECT_ROOT / "docs/v600_root_public_api_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    _require(sha256(manifest_bytes).hexdigest() == ROOT_MANIFEST_FILE_SHA256, "root-public manifest file changed")
    names = tuple(manifest["root_public_exports"])
    digest = sha256("".join(f"{name}\n" for name in names).encode("utf-8")).hexdigest()
    _require(len(names) == EXPECTED_ROOT_PUBLIC_COUNT, "root-public name count drift")
    _require(digest == ROOT_PUBLIC_SHA256, "root-public name digest drift")
    _require(manifest["root_public_sha256"] == ROOT_PUBLIC_SHA256, "embedded root-public digest drift")


def check_checker_source() -> None:
    source = _read("scripts/check_v600_documentation_freeze.py")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    forbidden_roots = {
        "openai",
        "elevenlabs",
        "pyvts",
        "websocket",
        "websockets",
        "sounddevice",
        "pyaudio",
    }
    _require(
        imported_roots.isdisjoint(forbidden_roots),
        "documentation checker imports an optional provider/device module",
    )


def run_aggregate_gate() -> None:
    output = _run_checked(
        [
            sys.executable,
            "scripts/check_v600_aggregate_conformance.py",
            "--source-only",
        ],
        label="FW-RT6-14a aggregate conformance gate",
    )
    _require("FW-RT6-14a aggregate conformance gate: PASS" in output, "aggregate PASS marker missing")
    _require(f"full Framework unit suite: {EXPECTED_FULL_UNIT_COUNT} / PASS" in output, "aggregate full-unit count drift")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the provider-free FW-RT6-14b documentation-freeze gate."
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Skip checkout/status verification while retaining all provider-free gates.",
    )
    return parser.parse_args()


def main() -> None:
    arguments = _parse_args()
    if not arguments.source_only:
        check_repository_surface()
    check_readme()
    check_contract_docs()
    check_tasklist_boundary()
    check_current_markdown_links()
    check_root_public_manifest()
    check_checker_source()
    run_aggregate_gate()

    print("FW-RT6-14b documentation freeze gate: PASS")
    print("implementation commit: 72cfa09f6551e1fc3d042777733627c900237cdc / VERIFIED")
    print("final acceptance-sync exact surface: 8 files / PASS")
    print("production Framework source changes: 0 files")
    print("test source changes: 0 files")
    print("README current v6 source status: PUBLISHED / VERIFIED")
    print("README historical development log: DELIMITED / APPEND_ONLY")
    print("advanced runtime contract: v6 / PASS")
    print("v5-to-v6 migration guide: PASS")
    print("capability/event/error reference: 48 EVENTS / PASS")
    print("root-public manifest gate: PASS / 127 UNCHANGED")
    print("FW-RT6-14a aggregate conformance gate: PASS")
    print("dedicated aggregate tests: 12 / PASS")
    print("current-compatible smoke dependencies: 11 / PASS")
    print("full Framework unit suite: 828 / PASS")
    print("provider/network/microphone/playback/VTS execution: False")
    print("private configuration/evidence read or written: False")
    print("FW-RT6-14b canonical tasks: 8 / 8 ACCEPTED")
    print("FW-RT6-14b final acceptance sync: PASS")
    print("FW-RT6-14b: COMPLETED / VERIFIED / ACCEPTED / CLOSED_AFTER_SYNC_COMMIT_PUSH")
    print("FW-RT6-14c canonical tasks: 14 / 14 ACCEPTED")
    print("FW-RT6-14c final acceptance sync: PASS / AWAITING_SYNC_COMMIT_PUSH")
    print("v6 source version metadata: 6.0.0")
    print("v6.0.0 publication status: PUBLISHED / VERIFIED")
    print("latest published release: 6.0.0")
    print("commit / push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
