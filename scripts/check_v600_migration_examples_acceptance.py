"""FW-RT6-11c Control C aggregate migration/example acceptance gate.

The gate is provider-free and offline-safe. It aggregates the accepted
Control A/B migration contracts without changing Framework runtime source,
root-public inventory, or host/provider ownership boundaries.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "69c47486f9abda234accd6838e2c78726cb5c65f"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_migration_examples_acceptance.py",
    "scripts/smoke_v600_migration_examples_control_a.py",
    "scripts/smoke_v600_migration_examples_control_b.py",
    "tests/test_migration_examples_control_a.py",
    "tests/test_migration_examples_control_b.py",
}
EXPECTED_TASKS = (
    "v5 standalone sessionからv6 unified sessionへのmigrationを記載する。",
    "text-only exampleを追加する。",
    "host-captured audio exampleを追加する。",
    "interrupt/partial completion exampleを追加する。",
    "local playback boundary exampleを追加する。",
    "motion extension hook exampleを追加する。",
    "unavailable capability fallback exampleを追加する。",
    "examplesがprovider credentialなしでimport可能であることを確認する。",
)
EXAMPLES = (
    "examples/app_v600_realtime_text_only.py",
    "examples/app_v600_realtime_unavailable_fallback.py",
    "examples/app_v600_host_captured_audio.py",
    "examples/app_v600_interrupt_partial_completion.py",
    "examples/app_v600_local_playback_boundary.py",
    "examples/app_v600_motion_extension_hook.py",
)
FORBIDDEN_RUNTIME_MODULES = {
    "openai",
    "elevenlabs",
    "pyvts",
    "pyaudio",
    "sounddevice",
    "websocket",
    "websockets",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
    capture: bool = True,
) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=capture,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + (result.stdout or "")
        + (result.stderr or ""),
    )
    return result.stdout or ""


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def _credential_free_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    for key in tuple(environment):
        upper_key = key.upper()
        if any(
            marker in upper_key
            for marker in (
                "API_KEY",
                "ACCESS_TOKEN",
                "AUTH_TOKEN",
                "CLIENT_SECRET",
                "PRIVATE_CREDENTIAL",
            )
        ):
            environment.pop(key)
    return environment


def _load(relative: str) -> object:
    path = PROJECT_ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    _require(spec is not None and spec.loader is not None, f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-11c Control C surface conform")


def check_accepted_history_and_focused_gates() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-11c-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-11c-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-11c-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-11c-B-ACCEPTANCE-SYNC:END",
    ):
        _require(tasklist.count(marker) == 1, f"accepted sync marker drift: {marker}")
    for phrase in (
        "Control A implementation and acceptance sync: 5cec4e338688724ee43157b7ccbf75deb67cf70e",
        "Control B implementation and acceptance: 69c47486f9abda234accd6838e2c78726cb5c65f",
        "Control A: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted Control A/B fact missing: {phrase}")

    control_a_gate = (
        PROJECT_ROOT / "scripts/smoke_v600_migration_examples_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_gate = (
        PROJECT_ROOT / "scripts/smoke_v600_migration_examples_control_b.py"
    ).read_text(encoding="utf-8")
    control_a_test = (
        PROJECT_ROOT / "tests/test_migration_examples_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_test = (
        PROJECT_ROOT / "tests/test_migration_examples_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_test.count("    def test_") == 12, "Control A test count drift")
    _require(control_b_test.count("    def test_") == 14, "Control B test count drift")
    for source, label in (
        (control_a_gate, "Control A gate"),
        (control_b_gate, "Control B gate"),
        (control_a_test, "Control A tests"),
        (control_b_test, "Control B tests"),
    ):
        _require(
            "check_v600_migration_examples_acceptance.py" in source,
            f"{label} Control C task-boundary sync missing",
        )

    _run(
        [
            sys.executable,
            "scripts/smoke_v600_migration_examples_control_a.py",
            "--source-only",
        ],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "scripts/smoke_v600_migration_examples_control_b.py",
            "--source-only",
        ],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_migration_examples_control_a",
            "tests.test_migration_examples_control_b",
        ],
        capture=False,
    )
    print("[OK] accepted Control A/B history and 26 focused tests conform")
    print("[OK] four gate/test files receive Control C task-boundary-only sync")


def check_docs_tasks_and_unchanged_boundaries() -> None:
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    guide = (PROJECT_ROOT / "docs/v600_v5_to_v6_session_migration.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "FW-RT6-11c-C-MIGRATION-ACCEPTANCE:BEGIN",
        "FW-RT6-11c-C-MIGRATION-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public contract marker drift: {marker}")
    for marker in (
        "FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")

    aggregate_text = facade.split(
        "<!-- FW-RT6-11c-C-MIGRATION-ACCEPTANCE:BEGIN -->", 1
    )[1].split(
        "<!-- FW-RT6-11c-C-MIGRATION-ACCEPTANCE:END -->", 1
    )[0] + tasklist.split(
        "<!-- FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:BEGIN -->", 1
    )[1].split(
        "<!-- FW-RT6-11c-C-AGGREGATE-ACCEPTANCE:END -->", 1
    )[0]
    for phrase in (
        "exact Control C surface: 7 files",
        "Control A/B gate/test semantic sync: 4 files / CONTROL_C TASK BOUNDARY ONLY",
        "all migration examples: 6 / PROVIDER-FREE / PUBLIC ROOT ONLY / PASS",
        "partial transcript/audio streaming claimed: False / PASS",
        "provider hard cancellation claimed: False / PASS",
        "physical playback stop claimed: False / PASS",
        "framework runtime source changed by Control C: False",
        "application-integration contract changed by Control C: False",
        "migration guide changed by Control C: False",
        "examples changed by Control C: False",
        "framework root-public names: 127 / UNCHANGED",
        "FW-RT6-11c tasks: 8 / 8 ACCEPTED-CANDIDATE",
        "FW-RT6-11c final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-12a exact contract review: NOT_AUTHORIZED",
        "Control C commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in aggregate_text, f"aggregate phrase missing: {phrase}")

    section = tasklist.split(
        "## FW-RT6-11c — Migration guide and examples", 1
    )[1].split("## FW-RT6-12a", 1)[0]
    _require(section.count("- [x]") == 8, "accepted-candidate count drift")
    _require(section.count("- [ ]") == 0, "FW-RT6-11c task remains open")
    for task in EXPECTED_TASKS:
        _require(task in section, f"FW-RT6-11c task missing: {task}")

    for marker in (
        "FW-RT6-11c-A-MIGRATION-FOUNDATION:BEGIN",
        "FW-RT6-11c-B-APP-EXAMPLES:BEGIN",
    ):
        _require(marker in app, f"accepted app contract missing: {marker}")
    for marker in (
        "FW-RT6-11c-A-MIGRATION-GUIDE:END",
        "FW-RT6-11c-B-MIGRATION-EXAMPLES:END",
    ):
        _require(marker in guide, f"accepted migration guide missing: {marker}")
    _require("FW-RT6-11c-C-" not in app, "Control C changed app contract")
    _require("FW-RT6-11c-C-" not in guide, "Control C changed migration guide")
    for unchanged in (
        "docs/app_integration_contract.md",
        "docs/v600_v5_to_v6_session_migration.md",
        *EXAMPLES,
    ):
        _require(unchanged not in EXPECTED_SURFACE, f"unchanged boundary escaped: {unchanged}")
    print("[OK] eight FW-RT6-11c tasks are aggregate acceptance-candidates")
    print("[OK] runtime, app contract, guide, examples, and API boundaries stay unchanged")


def check_example_sources_imports_and_execution() -> None:
    for relative in EXAMPLES:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        _require(
            imports == {"__future__", "framework"},
            f"{relative}: unexpected import set: {sorted(imports)!r}",
        )
        _require(
            'if __name__ == "__main__":' in source,
            f"{relative}: main guard missing",
        )

    import_probe = r"""
import importlib.util
from pathlib import Path
import sys

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
for relative in sys.argv[2:]:
    path = root / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise AssertionError(relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

forbidden = {
    "openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "websocket", "websockets",
}
loaded = {name.split(".", 1)[0].lower() for name in sys.modules}
if loaded & forbidden:
    raise AssertionError(sorted(loaded & forbidden))
print("import_safe: PASS")
"""
    environment = _credential_free_environment()
    output = _run(
        [sys.executable, "-I", "-c", import_probe, str(PROJECT_ROOT), *EXAMPLES],
        environment=environment,
    )
    _require("import_safe: PASS" in output, "aggregate import probe failed")

    run_code = (
        "import runpy,sys;"
        f"sys.path.insert(0,{str(PROJECT_ROOT)!r});"
        "runpy.run_path(sys.argv[1],run_name='__main__')"
    )
    for relative in EXAMPLES:
        output = _run(
            [sys.executable, "-I", "-c", run_code, str(PROJECT_ROOT / relative)],
            environment=environment,
        )
        _require(
            "provider_execution_performed: False" in output,
            f"{relative}: provider-free execution fact missing",
        )

    text = _load(EXAMPLES[0]).run_text_only("aggregate")
    fallback = _load(EXAMPLES[1]).run_with_explicit_fallback("aggregate")
    host_audio = _load(EXAMPLES[2]).run_host_captured_audio()
    interrupt = _load(EXAMPLES[3]).run_interrupt_partial_completion()
    playback = _load(EXAMPLES[4]).run_local_playback_boundary()
    motion = _load(EXAMPLES[5]).run_motion_extension_hook()
    _require(text == ("v5_skeleton", "completed", True), "text example drift")
    _require(
        fallback
        == ("v6_unified", "configuration_incomplete", "rejected", "v5_skeleton", True),
        "fallback example drift",
    )
    _require(
        host_audio
        == ("completed", "host captured fake transcript", "opaque_id", False, False, False),
        "host-audio example drift",
    )
    _require(
        interrupt
        == (True, "not_implemented", "partial", True, True, 0, 0, False, False),
        "interrupt example drift",
    )
    _require(
        playback == ("not_implemented", True, True, False, False),
        "playback example drift",
    )
    _require(motion[0] == "completed", "motion changed conversation outcome")
    _require(
        motion[1] == ("listening", "thinking", "speaking", "completed"),
        "motion lifecycle drift",
    )
    _require(
        motion[2:] == (("not_configured", "not_configured"), 1, False),
        "motion boundary drift",
    )
    print("[OK] all six examples remain public-root-only and credential-free")
    print("[OK] host audio, interrupt, playback, fallback, and motion facts conform")


def check_public_and_accepted_regression_boundaries() -> None:
    import framework

    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in (
        "run_text_only",
        "run_with_explicit_fallback",
        "run_host_captured_audio",
        "run_interrupt_partial_completion",
        "run_local_playback_boundary",
        "run_motion_extension_hook",
    ):
        _require(name not in framework.__all__, f"example leaked root-public: {name}")
    _require(
        not any(path.startswith("framework/") for path in EXPECTED_SURFACE),
        "Control C surface includes Framework runtime source",
    )
    for command in (
        [
            sys.executable,
            "scripts/check_v600_root_public_api_cleanup_acceptance.py",
            "--source-only",
        ],
        [
            sys.executable,
            "scripts/check_v600_session_compatibility_acceptance.py",
            "--source-only",
        ],
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
    ):
        _run(command)
    for module_name in FORBIDDEN_RUNTIME_MODULES:
        _require(module_name not in sys.modules, f"runtime module escaped: {module_name}")
    print("[OK] accepted FW-RT6-11a/11b gates and frozen 127-name root conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_history_and_focused_gates()
    check_docs_tasks_and_unchanged_boundaries()
    check_example_sources_imports_and_execution()
    check_public_and_accepted_regression_boundaries()

    print("v600_rt6_11c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11c_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11c_control_c_exact_surface: 7 files")
    print("v600_rt6_11c_existing_gate_test_sync: 4 files / TASK BOUNDARY ONLY")
    print("v600_rt6_11c_examples: 6 / PROVIDER-FREE / PUBLIC ROOT ONLY")
    print("v600_rt6_11c_runtime_changed_by_control_c: False")
    print("v600_rt6_11c_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_11c_provider_execution: False")
    print("v600_rt6_11c_network_execution: False")
    print("v600_rt6_11c_task_count: 8 / 8 ACCEPTED-CANDIDATE")
    print("v600_rt6_11c_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_12a: NOT_AUTHORIZED")
    print("v600_rt6_11c_control_c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11c Control C aggregate migration/examples gate passed")


if __name__ == "__main__":
    main()
