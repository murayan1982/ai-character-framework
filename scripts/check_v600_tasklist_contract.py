"""FW-RT6-0a exact source-inventory/tasklist contract checker.

Default mode validates the exact six-file docs/test-only change surface against
v5.5.0 HEAD. ``--source-only`` skips Git metadata checks for an exported source
bundle but still validates documents, scripts, and current-source facts.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "f56697b6de066b062794ac7bb01330d2d9e91759"
EXACT_SURFACE = {
    "README.md",
    "docs/roadmap_feature_v6.0.0.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_tasklist_contract.py",
    "scripts/smoke_v600_current_source_gap_inventory.py",
}

PROTECTED_PREFIXES = (
    "framework/",
    "core/",
    "llm/",
    "stt/",
    "tts/",
    "live2d/",
    "plugins/",
    "registry/",
    "config/",
    "presets/",
    "characters/",
    "release/",
    ".release_build/",
    "requirements",
    ".env",
    "pyproject",
    "setup.",
)

FORBIDDEN_IMPORT_ROOTS = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "pyaudio",
    "sounddevice",
    "live2d",
    "tts",
    "stt",
    "llm",
}

REQUIRED_DOC_MARKERS = (
    "FW-RT6-0a",
    "Unified Realtime Character Runtime",
    EXPECTED_HEAD,
    "G-01",
    "G-17",
    "FW-RT6-0b",
    "NOT_AUTHORIZED",
    "runtime Python changed: False",
    "DRC repository accessed or changed: False",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="replace")


def _run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
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


def _validate_repository() -> None:
    _require((ROOT / ".git").exists(), "strict checker requires a Git working tree")

    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    _require(head == EXPECTED_HEAD, f"FW-RT6-0a requires HEAD {EXPECTED_HEAD}, found {head}")

    branch = _run("git", "branch", "--show-current").stdout.strip()
    _require(branch == "main", f"expected main branch, found: {branch}")

    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require("ai-character-framework" in origin.lower(), "origin is not the AI Character Framework repository")

    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    _require(origin_main == EXPECTED_HEAD, f"origin/main must remain {EXPECTED_HEAD}, found {origin_main}")

    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-RT6-0a exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )

    protected_hits = sorted(
        path for path in changed if any(path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
    )
    _require(not protected_hits, "protected runtime/config/release surface changed: " + ", ".join(protected_hits))
    _ok("repository baseline and exact six-file surface match")


def _validate_documents() -> None:
    combined = "\n".join(
        _read(relative)
        for relative in (
            "README.md",
            "docs/roadmap_feature_v6.0.0.md",
            "docs/v600_current_source_gap_inventory.md",
            "docs/v600_tasklist.md",
        )
    )
    for marker in REQUIRED_DOC_MARKERS:
        _require(marker in combined, f"FW-RT6-0a docs missing marker: {marker}")

    for forbidden in (
        "FW-RT6-0b implementation: AUTHORIZED",
        "runtime Python changed: True",
        "provider execution: True",
        "network execution: True",
        "DRC repository accessed or changed: True",
    ):
        _require(forbidden not in combined, f"forbidden authorization/status found: {forbidden}")

    _ok("roadmap, source gap inventory, tasklist, and README status are synchronized")


def _validate_script_import_safety() -> None:
    for relative in (
        "scripts/check_v600_tasklist_contract.py",
        "scripts/smoke_v600_current_source_gap_inventory.py",
    ):
        tree = ast.parse(_read(relative), filename=relative)
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split(".", 1)[0])
        hits = sorted(roots & FORBIDDEN_IMPORT_ROOTS)
        _require(not hits, f"{relative} imports forbidden provider/runtime modules: {hits}")
    _ok("FW-RT6-0a scripts contain no provider/audio/VTS runtime imports")


def _validate_task_dependencies() -> None:
    tasklist = _read("docs/v600_tasklist.md")
    required_tasks = (
        "FW-RT6-0a",
        "FW-RT6-0b",
        "FW-RT6-0c",
        "FW-RT6-1a",
        "FW-RT6-2c",
        "FW-RT6-2d",
        "FW-RT6-3b",
        "FW-RT6-4b",
        "FW-RT6-5a",
        "FW-RT6-6c",
        "FW-RT6-7a",
        "FW-RT6-8a",
        "FW-RT6-9a",
        "FW-RT6-10a",
        "FW-RT6-11a",
        "FW-RT6-13a",
        "FW-RT6-14c",
    )
    positions = []
    for task in required_tasks:
        position = tasklist.find(task)
        _require(position >= 0, f"tasklist missing required task: {task}")
        positions.append(position)
    _require(positions == sorted(positions), "tasklist critical dependency order is not monotonic")
    _ok("v6 critical-path task IDs and ordering are fixed")


def _validate_smoke_execution() -> None:
    completed = _run(sys.executable, "scripts/smoke_v600_current_source_gap_inventory.py")
    _require(
        "v600_source_inventory_status: implemented-awaiting-review" in completed.stdout,
        "dedicated smoke did not report implemented-awaiting-review",
    )
    _require("v600_network_execution: False" in completed.stdout, "dedicated smoke network marker missing")
    _require("v600_provider_execution: False" in completed.stdout, "dedicated smoke provider marker missing")
    _require("v600_drc_repository_accessed: False" in completed.stdout, "dedicated smoke DRC marker missing")
    print(completed.stdout, end="")
    _ok("dedicated FW-RT6-0a source inventory smoke passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="skip Git baseline/exact-surface checks for an exported source bundle",
    )
    args = parser.parse_args()

    if not args.source_only:
        _validate_repository()
    else:
        _ok("source-only mode: Git baseline/exact-surface checks skipped")

    _validate_documents()
    _validate_script_import_safety()
    _validate_task_dependencies()
    _validate_smoke_execution()

    print("v600_tasklist_contract_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 6")
    print("v600_runtime_changed: False")
    print("v600_next_checkpoint: FW-RT6-0b")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-0a tasklist contract checker passed")


if __name__ == "__main__":
    main()
