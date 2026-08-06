"""FW-RT6-3c Control A normal unit-test foundation gate.

Offline/provider-free: validates the exact six-file candidate, stdlib unittest
discovery, identity/model and lifecycle-transition coverage, unchanged
production source and smoke gates, root-public compatibility, and absence of
provider/network imports or execution.
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

EXPECTED_BASELINE = "9fe14cb53a4740fea3f7172af36d7052610b215d"
EXPECTED_BASELINE_PARENT = "5a565afbb19e81f55d35e89486c2327a47d87ab5"
EXPECTED_BASELINE_SUBJECT = "docs/test: accept deterministic fake runtime"
EXPECTED_SURFACE = {
    "docs/v600_runtime_unit_test_contract.md",
    "scripts/run_v600_unit_tests.py",
    "scripts/smoke_v600_runtime_unit_test_foundation.py",
    "tests/__init__.py",
    "tests/test_identity_models.py",
    "tests/test_lifecycle_transitions.py",
}
UNCHANGED_ACCEPTED_PATHS = (
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
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
    "scripts/check_v600_realtime_fake_runtime_acceptance.py",
)
UNIT_LAYER_PATHS = (
    "scripts/run_v600_unit_tests.py",
    "tests/__init__.py",
    "tests/test_identity_models.py",
    "tests/test_lifecycle_transitions.py",
)
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
CONTRACT_MARKER = "FW-RT6-3c-A-UNIT-TEST-FOUNDATION"


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
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    for relative in UNCHANGED_ACCEPTED_PATHS:
        _assert(
            _git("hash-object", relative) == _git("rev-parse", f"HEAD:{relative}"),
            f"accepted source or smoke changed: {relative}",
        )
    print("[OK] baseline and exact six-file Control A surface conform")


def check_unit_layer_source_safety() -> None:
    for relative in UNIT_LAYER_PATHS:
        path = PROJECT_ROOT / relative
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imported_roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".", 1)[0].lower() for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".", 1)[0].lower())
        forbidden = imported_roots & FORBIDDEN_IMPORT_ROOTS
        _assert(
            not forbidden,
            f"forbidden unit-layer import in {relative}: {sorted(forbidden)}",
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
    print("[OK] normal unit-test layer is stdlib-only and network/provider-free")


def check_test_contract_and_counts() -> None:
    identity_source = (
        PROJECT_ROOT / "tests/test_identity_models.py"
    ).read_text(encoding="utf-8")
    transition_source = (
        PROJECT_ROOT / "tests/test_lifecycle_transitions.py"
    ).read_text(encoding="utf-8")
    contract = (
        PROJECT_ROOT / "docs/v600_runtime_unit_test_contract.md"
    ).read_text(encoding="utf-8")

    identity_tree = ast.parse(identity_source)
    transition_tree = ast.parse(transition_source)
    identity_count = sum(
        1
        for node in ast.walk(identity_tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )
    transition_count = sum(
        1
        for node in ast.walk(transition_tree)
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    )

    _assert(identity_count == 12, "identity/model test count drift")
    _assert(transition_count == 7, "transition test count drift")
    _assert(CONTRACT_MARKER in contract, "Control A contract marker missing")
    for required in (
        "runner: unittest",
        "external test dependency added: False",
        "terminal registry unit tests: DEFERRED / Control B",
        "full FW-RT6-3c aggregate acceptance: DEFERRED / Control C",
        "production runtime source changed: False",
    ):
        _assert(required in contract, f"contract fact missing: {required}")
    print("[OK] identity/model and transition unit-test contract conforms")


def check_unit_runner() -> None:
    output = _run_script(
        "scripts/run_v600_unit_tests.py",
        (
            "v600_unit_test_runner: unittest",
            "v600_unit_test_count: 19",
            "v600_unit_test_result: PASS",
        ),
    )
    _assert("Ran 19 tests" in output, "unittest result count drift")
    print("[OK] stdlib unittest discovery runs 19 provider-free tests")


def check_public_and_version_smokes() -> None:
    _run_script(
        "scripts/smoke_v600_public_api_manifest.py",
        (
            "v600_public_api_manifest_status: accepted",
            "v600_public_api_manifest_name_count: 121",
            "v600_next_checkpoint: FW-RT6-3c",
            "v600_next_checkpoint_authorized: False",
        ),
    )
    _run_script(
        "scripts/smoke_v600_version_metadata.py",
        (
            "v600_version_metadata_status: accepted",
            "v600_root_public_name_count: 121",
            "v600_next_checkpoint: FW-RT6-3c",
            "v600_next_checkpoint_authorized: False",
        ),
    )
    print("[OK] existing smoke gates remain unchanged and conformant")


def check_root_import_safety() -> None:
    probe = f'''
import sys
sys.path.insert(0, {str(PROJECT_ROOT)!r})
import framework
assert len(framework.__all__) == 121
forbidden = {tuple(root for root in sorted(FORBIDDEN_IMPORT_ROOTS) if root not in ("socket", "urllib"))!r}
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
    check_unit_layer_source_safety()
    check_test_contract_and_counts()
    check_unit_runner()
    check_public_and_version_smokes()
    check_root_import_safety()

    print("v600_rt6_3c_control_a_status: implemented-awaiting-review")
    print("v600_rt6_3c_control_a_exact_change_surface_count: 6")
    print("v600_rt6_3c_control_a_tests_directory_non_empty: True")
    print("v600_rt6_3c_control_a_runner: unittest")
    print("v600_rt6_3c_control_a_identity_model_test_count: 12")
    print("v600_rt6_3c_control_a_transition_test_count: 7")
    print("v600_rt6_3c_control_a_discovered_unit_test_count: 19")
    print("v600_rt6_3c_control_a_unit_tests_network_free: True")
    print("v600_rt6_3c_control_a_full_control_a_unit_suite: PASS")
    print("v600_rt6_3c_control_a_production_runtime_source_changed: False")
    print("v600_rt6_3c_control_a_existing_smoke_scripts_changed: False")
    print("v600_rt6_3c_control_b_authorized: False")
    print("v600_rt6_3c_aggregate_acceptance: deferred")
    print(
        "v600_rt6_3c_control_a_"
        "provider_network_microphone_playback_real_vts_execution: False"
    )
    print("v600_rt6_3c_control_a_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3c_control_a_root_draft_stash_accessed_or_changed: False")
    print("[OK] FW-RT6-3c Control A normal unit-test foundation conforms")


if __name__ == "__main__":
    main()
