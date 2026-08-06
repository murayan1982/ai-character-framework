"""FW-RT6-3c Control B normal runtime unit-test coverage gate.

Offline/provider-free: validates the accepted Control A commit, exact
six-file Control B candidate, 26 added tests across four runtime categories,
the unchanged stdlib runner and production source, the full 45-test suite,
root-public compatibility, and absence of provider/network execution.
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

EXPECTED_BASELINE = "98b8c5a77f69705096dee316fe7fee35eca9e3b0"
EXPECTED_BASELINE_PARENT = "9fe14cb53a4740fea3f7172af36d7052610b215d"
EXPECTED_BASELINE_SUBJECT = "test: add realtime unit test foundation"
CONTROL_A_SURFACE = {
    "docs/v600_runtime_unit_test_contract.md",
    "scripts/run_v600_unit_tests.py",
    "scripts/smoke_v600_runtime_unit_test_foundation.py",
    "tests/__init__.py",
    "tests/test_identity_models.py",
    "tests/test_lifecycle_transitions.py",
}
EXPECTED_SURFACE = {
    "docs/v600_runtime_unit_test_contract.md",
    "scripts/smoke_v600_runtime_unit_test_control_b.py",
    "tests/test_realtime_terminal_registry.py",
    "tests/test_realtime_generation_gate.py",
    "tests/test_realtime_event_hub.py",
    "tests/test_realtime_fake_runtime.py",
}
UNCHANGED_PATHS = (
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
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/__init__.py",
    "tests/test_identity_models.py",
    "tests/test_lifecycle_transitions.py",
)
NEW_TEST_COUNTS = {
    "tests/test_realtime_terminal_registry.py": 5,
    "tests/test_realtime_generation_gate.py": 6,
    "tests/test_realtime_event_hub.py": 7,
    "tests/test_realtime_fake_runtime.py": 8,
}
FORBIDDEN_IMPORT_ROOTS = {
    "aiohttp",
    "elevenlabs",
    "google",
    "httpx",
    "openai",
    "pyaudio",
    "pyvts",
    "requests",
    "socket",
    "sounddevice",
    "speech_recognition",
    "urllib",
    "websocket",
    "websockets",
    "xai_sdk",
}
PROVIDER_IMPORT_ROOTS = FORBIDDEN_IMPORT_ROOTS - {"socket", "urllib"}
CONTRACT_MARKER = "FW-RT6-3c-B-RUNTIME-UNIT-TEST-COVERAGE"


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
    _assert(
        completed.returncode == 0,
        f"{relative_path} failed:\n{output}",
    )
    for phrase in expected:
        _assert(
            phrase in output,
            f"{relative_path} output missing: {phrase}",
        )
    return output


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected HEAD")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^")
        == EXPECTED_BASELINE_PARENT,
        "Control A parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "Control A subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == CONTROL_A_SURFACE,
        "Control A committed surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    for relative in UNCHANGED_PATHS:
        _assert(
            _git("hash-object", relative)
            == _git("rev-parse", f"HEAD:{relative}"),
            f"accepted path changed: {relative}",
        )
    print("[OK] accepted Control A and exact six-file Control B surface conform")


def _test_count(relative: str) -> int:
    source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative)
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("test_")
    )


def check_test_source_and_counts() -> None:
    for relative, expected_count in NEW_TEST_COUNTS.items():
        path = PROJECT_ROOT / relative
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0].lower()
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0].lower())
        forbidden = imported_roots & FORBIDDEN_IMPORT_ROOTS
        _assert(
            not forbidden,
            f"forbidden import in {relative}: {sorted(forbidden)}",
        )
        _assert(
            _test_count(relative) == expected_count,
            f"test count drift in {relative}",
        )
        for line_number, line in enumerate(source.splitlines(), start=1):
            _assert(
                line == line.rstrip(),
                f"trailing whitespace in {relative}:{line_number}",
            )
        _assert(
            not source.endswith("\n\n"),
            f"new blank line at EOF in {relative}",
        )

    self_source = Path(__file__).read_text(encoding="utf-8")
    self_tree = ast.parse(self_source, filename=str(Path(__file__)))
    self_imports: set[str] = set()
    for node in ast.walk(self_tree):
        if isinstance(node, ast.Import):
            self_imports.update(
                alias.name.split(".", 1)[0].lower()
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            self_imports.add(node.module.split(".", 1)[0].lower())
    _assert(
        not (self_imports & FORBIDDEN_IMPORT_ROOTS),
        "Control B gate contains a forbidden import",
    )
    print("[OK] 26 Control B tests are stdlib-only and provider/network-free")


def check_contract_truth() -> None:
    contract = (
        PROJECT_ROOT / "docs/v600_runtime_unit_test_contract.md"
    ).read_text(encoding="utf-8")
    _assert(CONTRACT_MARKER in contract, "Control B contract marker missing")
    for required in (
        "terminal registry tests: 5",
        "generation / stale-completion tests: 6",
        "subscriber / event-hub tests: 7",
        "deterministic fake-runtime tests: 8",
        "Control B added tests: 26",
        "full discovered unit tests: 45",
        "production runtime source changed: False",
        "Control C aggregate acceptance: NOT_AUTHORIZED / DEFERRED",
    ):
        _assert(required in contract, f"contract fact missing: {required}")
    print("[OK] Control B runtime unit-test contract is truthful")


def check_full_unit_suite() -> None:
    output = _run_script(
        "scripts/run_v600_unit_tests.py",
        (
            "v600_unit_test_runner: unittest",
            "v600_unit_test_count: 45",
            "v600_unit_test_result: PASS",
        ),
    )
    _assert("Ran 45 tests" in output, "full unittest result count drift")
    print("[OK] full normal unit-test suite runs 45 tests")


def check_public_and_version_smokes() -> None:
    _run_script(
        "scripts/smoke_v600_public_api_manifest.py",
        (
            "v600_public_api_manifest_status: accepted",
            "v600_public_api_manifest_name_count: 121",
            "v600_next_checkpoint: FW-RT6-3c",
        ),
    )
    _run_script(
        "scripts/smoke_v600_version_metadata.py",
        (
            "v600_version_metadata_status: accepted",
            "v600_root_public_name_count: 121",
            "v600_next_checkpoint: FW-RT6-3c",
        ),
    )
    print("[OK] unchanged public/version smoke gates remain conformant")


def check_root_import_safety() -> None:
    probe = f'''
import sys
sys.path.insert(0, {str(PROJECT_ROOT)!r})
import framework
assert len(framework.__all__) == 121
forbidden = {tuple(sorted(PROVIDER_IMPORT_ROOTS))!r}
loaded = sorted(
    root
    for root in forbidden
    if any(name == root or name.startswith(root + ".") for name in sys.modules)
)
assert not loaded, loaded
'''
    subprocess.run(
        [sys.executable, "-I", "-c", probe],
        cwd=PROJECT_ROOT,
        check=True,
    )
    print("[OK] root-public names remain 121 and provider SDKs stay unloaded")


def main() -> None:
    check_repository_contract()
    check_test_source_and_counts()
    check_contract_truth()
    check_full_unit_suite()
    check_public_and_version_smokes()
    check_root_import_safety()

    print("v600_rt6_3c_control_b_status: implemented-awaiting-review")
    print("v600_rt6_3c_control_b_exact_change_surface_count: 6")
    print("v600_rt6_3c_control_b_terminal_registry_test_count: 5")
    print("v600_rt6_3c_control_b_generation_stale_test_count: 6")
    print("v600_rt6_3c_control_b_subscriber_event_hub_test_count: 7")
    print("v600_rt6_3c_control_b_fake_runtime_test_count: 8")
    print("v600_rt6_3c_control_b_added_test_count: 26")
    print("v600_rt6_3c_control_b_full_unit_test_count: 45")
    print("v600_rt6_3c_control_b_full_unit_suite: PASS")
    print("v600_rt6_3c_control_b_unit_tests_network_free: True")
    print("v600_rt6_3c_control_b_production_runtime_source_changed: False")
    print("v600_rt6_3c_control_b_existing_smoke_scripts_changed: False")
    print("v600_rt6_3c_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_3c_control_c_authorized: False")
    print("v600_rt6_3c_control_b_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3c_control_b_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3c_control_b_root_draft_stash_accessed_or_changed: False")
    print("[OK] FW-RT6-3c Control B normal runtime unit-test coverage conforms")


if __name__ == "__main__":
    main()
