"""FW-RT6-3c Control C aggregate normal unit-test acceptance check.

Offline/provider-free: validates accepted Control A/B history, the exact
six-file Control C docs/test-only surface, all nine tasklist items, the
non-empty 45-test stdlib suite, unchanged runtime and accepted tests, aggregate
smoke separation, public compatibility, and frozen version metadata without
provider, network, microphone, playback, real VTube Studio, DRC, or root-draft
stash access.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "e368a3db3e1ae6160d6a3c3f01929eb6f256c57a"
EXPECTED_BASELINE_PARENT = "98b8c5a77f69705096dee316fe7fee35eca9e3b0"
EXPECTED_BASELINE_SUBJECT = "test: cover realtime runtime primitives"

CONTROL_A = EXPECTED_BASELINE_PARENT
CONTROL_A_PARENT = "9fe14cb53a4740fea3f7172af36d7052610b215d"
CONTROL_A_SUBJECT = "test: add realtime unit test foundation"
CONTROL_A_SURFACE = {
    "docs/v600_runtime_unit_test_contract.md",
    "scripts/run_v600_unit_tests.py",
    "scripts/smoke_v600_runtime_unit_test_foundation.py",
    "tests/__init__.py",
    "tests/test_identity_models.py",
    "tests/test_lifecycle_transitions.py",
}

CONTROL_B = EXPECTED_BASELINE
CONTROL_B_PARENT = CONTROL_A
CONTROL_B_SUBJECT = EXPECTED_BASELINE_SUBJECT
CONTROL_B_SURFACE = {
    "docs/v600_runtime_unit_test_contract.md",
    "scripts/smoke_v600_runtime_unit_test_control_b.py",
    "tests/test_realtime_terminal_registry.py",
    "tests/test_realtime_generation_gate.py",
    "tests/test_realtime_event_hub.py",
    "tests/test_realtime_fake_runtime.py",
}

EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_runtime_unit_test_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}

UNCHANGED_ACCEPTED_PATHS = (
    "docs/v600_runtime_unit_test_contract.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/identity.py",
    "framework/lifecycle.py",
    "framework/realtime_event_payloads.py",
    "framework/realtime_terminal_registry.py",
    "framework/realtime_generation_gate.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_fake_runtime.py",
    "framework/realtime_session.py",
    "framework/realtime_stage.py",
    "scripts/run_v600_unit_tests.py",
    "scripts/smoke_v600_runtime_unit_test_foundation.py",
    "scripts/smoke_v600_runtime_unit_test_control_b.py",
    "tests/__init__.py",
    "tests/test_identity_models.py",
    "tests/test_lifecycle_transitions.py",
    "tests/test_realtime_terminal_registry.py",
    "tests/test_realtime_generation_gate.py",
    "tests/test_realtime_event_hub.py",
    "tests/test_realtime_fake_runtime.py",
)

TEST_COUNTS = {
    "tests/test_identity_models.py": 12,
    "tests/test_lifecycle_transitions.py": 7,
    "tests/test_realtime_terminal_registry.py": 5,
    "tests/test_realtime_generation_gate.py": 6,
    "tests/test_realtime_event_hub.py": 7,
    "tests/test_realtime_fake_runtime.py": 8,
}

TASK_LINES = (
    "- [x] `tests/`へunit test構成を追加する。",
    "- [x] test runnerを選定する。",
    "- [x] identity/model testsを追加する。",
    "- [x] transition testsを追加する。",
    "- [x] terminal registry testsを追加する。",
    "- [x] generation/stale testsを追加する。",
    "- [x] subscriber testsを追加する。",
    "- [x] fake runtime testsを追加する。",
    "- [x] smoke scriptはaggregate/release gateとして維持する。",
)

README_MARKER = "FW-RT6-3c-C-RUNTIME-UNIT-TEST-ACCEPTANCE:BEGIN"
TASKLIST_MARKER = "FW-RT6-3c-C-ACCEPTANCE-SYNC:BEGIN"
GAP_MARKER = "FW-RT6-3c-C-GAP-RESOLUTION-SYNC:BEGIN"

FORBIDDEN_PROVIDER_ROOTS = {
    "aiohttp",
    "elevenlabs",
    "google",
    "httpx",
    "openai",
    "pyaudio",
    "pyvts",
    "requests",
    "sounddevice",
    "speech_recognition",
    "websocket",
    "websockets",
    "xai_sdk",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).splitlines()
        if line.strip()
    }


def _check_commit(
    *,
    commit: str,
    parent: str,
    subject: str,
    surface: set[str],
    label: str,
) -> None:
    _assert(_git("rev-parse", f"{commit}^") == parent, f"{label} parent drift")
    _assert(
        _git("show", "-s", "--format=%s", commit) == subject,
        f"{label} subject drift",
    )
    _assert(_commit_surface(commit) == surface, f"{label} surface drift")


def _run_script(relative_path: str, expected: tuple[str, ...]) -> str:
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / relative_path)],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"{relative_path} failed:\n{output}")
    for phrase in expected:
        _assert(phrase in output, f"{relative_path} output missing: {phrase}")
    return output


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected HEAD")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control C surface: {sorted(_changed_paths())}",
    )
    _check_commit(
        commit=CONTROL_A,
        parent=CONTROL_A_PARENT,
        subject=CONTROL_A_SUBJECT,
        surface=CONTROL_A_SURFACE,
        label="Control A",
    )
    _check_commit(
        commit=CONTROL_B,
        parent=CONTROL_B_PARENT,
        subject=CONTROL_B_SUBJECT,
        surface=CONTROL_B_SURFACE,
        label="Control B",
    )
    for relative in UNCHANGED_ACCEPTED_PATHS:
        _assert(
            _git("hash-object", relative) == _git("rev-parse", f"HEAD:{relative}"),
            f"accepted source/test path changed: {relative}",
        )
    print("[OK] accepted Control A/B history and exact six-file Control C surface conform")


def _test_count(relative: str) -> int:
    source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )


def check_normal_unit_test_contract() -> None:
    _assert((PROJECT_ROOT / "tests").is_dir(), "tests directory is missing")
    _assert(
        any((PROJECT_ROOT / "tests").glob("test_*.py")),
        "tests directory contains no test modules",
    )
    for relative, expected in TEST_COUNTS.items():
        _assert(_test_count(relative) == expected, f"test count drift: {relative}")
    _assert(sum(TEST_COUNTS.values()) == 45, "full test inventory drift")

    runner = (PROJECT_ROOT / "scripts/run_v600_unit_tests.py").read_text(
        encoding="utf-8"
    )
    _assert("import unittest" in runner, "runner is not stdlib unittest")
    _assert('PATTERN = "test_*.py"' in runner, "runner discovery pattern drift")

    print("[OK] normal tests directory, stdlib runner, and 45-test inventory conform")


def check_docs_and_tasklist() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    gap = (
        PROJECT_ROOT / "docs/v600_current_source_gap_inventory.md"
    ).read_text(encoding="utf-8")

    _assert(README_MARKER in readme, "README acceptance marker missing")
    _assert(TASKLIST_MARKER in tasklist, "tasklist acceptance marker missing")
    _assert(GAP_MARKER in gap, "gap resolution marker missing")

    section_start = tasklist.index("## FW-RT6-3c — Normal unit-test layer")
    section_end = tasklist.index("\n---\n\n## FW-RT6-4a", section_start)
    section = tasklist[section_start:section_end]

    for line in TASK_LINES:
        _assert(line in section, f"accepted task line missing: {line}")
    _assert(section.count("- [x]") == 9, "accepted task count drift")
    _assert("- [ ]" not in section, "unchecked FW-RT6-3c task remains")

    required_facts = (
        "tests directory non-empty: True",
        "selected runner: unittest",
        "full discovered unit tests: 45",
        "unit tests network-free: True",
        "full unit suite: PASS",
        "next checkpoint: FW-RT6-4a",
        "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED",
        "production runtime source changed: False",
    )
    combined = "\n".join((readme, tasklist, gap))
    for fact in required_facts:
        _assert(fact in combined, f"aggregate fact missing: {fact}")

    print("[OK] README, tasklist, and gap inventory record truthful aggregate acceptance")


def check_full_unit_suite() -> None:
    output = _run_script(
        "scripts/run_v600_unit_tests.py",
        (
            "v600_unit_test_runner: unittest",
            "v600_unit_test_count: 45",
            "v600_unit_test_result: PASS",
        ),
    )
    _assert("Ran 45 tests" in output, "unittest result count drift")
    print("[OK] full provider-free normal unit suite runs 45 tests")


def check_public_and_version_smokes() -> None:
    _run_script(
        "scripts/smoke_v600_public_api_manifest.py",
        (
            "v600_public_api_manifest_status: accepted",
            "v600_public_api_manifest_name_count: 121",
            "v600_runtime_unit_test_status: accepted",
            "v600_runtime_unit_test_count: 45",
            "v600_next_checkpoint: FW-RT6-4a",
            "v600_next_checkpoint_authorized: False",
        ),
    )
    _run_script(
        "scripts/smoke_v600_version_metadata.py",
        (
            "v600_version_metadata_status: accepted",
            "v600_root_public_name_count: 121",
            "v600_runtime_unit_test_status: accepted",
            "v600_runtime_unit_test_count: 45",
            "v600_next_checkpoint: FW-RT6-4a",
            "v600_next_checkpoint_authorized: False",
        ),
    )
    print("[OK] public/version aggregate smoke gates accept FW-RT6-3c and advance to FW-RT6-4a")


def check_root_import_safety() -> None:
    probe = f"""
import sys
sys.path.insert(0, {str(PROJECT_ROOT)!r})
import framework
assert len(framework.__all__) == 121
forbidden = {tuple(sorted(FORBIDDEN_PROVIDER_ROOTS))!r}
loaded = sorted(
    root
    for root in forbidden
    if any(name == root or name.startswith(root + ".") for name in sys.modules)
)
assert not loaded, loaded
"""
    subprocess.run(
        [sys.executable, "-I", "-c", probe],
        cwd=PROJECT_ROOT,
        check=True,
    )
    print("[OK] root-public names remain 121 and provider SDKs stay unloaded")


def main() -> None:
    check_repository_contract()
    check_normal_unit_test_contract()
    check_docs_and_tasklist()
    check_full_unit_suite()
    check_public_and_version_smokes()
    check_root_import_safety()

    print("v600_rt6_3c_control_c_status: implemented-awaiting-review")
    print("v600_rt6_3c_control_c_exact_change_surface_count: 6")
    print("v600_rt6_3c_control_c_accepted_task_count: 9")
    print("v600_rt6_3c_tests_directory_non_empty: True")
    print("v600_rt6_3c_selected_runner: unittest")
    print("v600_rt6_3c_identity_model_test_count: 12")
    print("v600_rt6_3c_transition_test_count: 7")
    print("v600_rt6_3c_terminal_registry_test_count: 5")
    print("v600_rt6_3c_generation_stale_test_count: 6")
    print("v600_rt6_3c_subscriber_event_hub_test_count: 7")
    print("v600_rt6_3c_fake_runtime_test_count: 8")
    print("v600_rt6_3c_full_unit_test_count: 45")
    print("v600_rt6_3c_unit_tests_network_free: True")
    print("v600_rt6_3c_full_unit_suite: PASS")
    print("v600_rt6_3c_smoke_scripts_retained_as_aggregate_release_gates: True")
    print("v600_rt6_3c_production_runtime_source_changed: False")
    print("v600_rt6_3c_root_public_names: 121 / unchanged")
    print("v600_rt6_3c_realtime_session_orchestration_changed: False")
    print("v600_next_checkpoint: FW-RT6-4a")
    print("v600_next_checkpoint_authorized: False")
    print("v600_rt6_3c_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3c_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3c_root_draft_stash_accessed_or_changed: False")
    print("[OK] FW-RT6-3c Control C aggregate normal runtime unit-test acceptance conforms")


if __name__ == "__main__":
    main()
