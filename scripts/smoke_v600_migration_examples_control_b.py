"""FW-RT6-11c Control B provider-free migration-example gate."""

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

EXPECTED_HEAD = "5cec4e338688724ee43157b7ccbf75deb67cf70e"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_v5_to_v6_session_migration.md",
    "examples/app_v600_host_captured_audio.py",
    "examples/app_v600_interrupt_partial_completion.py",
    "examples/app_v600_local_playback_boundary.py",
    "examples/app_v600_motion_extension_hook.py",
    "scripts/smoke_v600_migration_examples_control_b.py",
    "tests/test_migration_examples_control_b.py",
}
EXAMPLES = (
    "examples/app_v600_host_captured_audio.py",
    "examples/app_v600_interrupt_partial_completion.py",
    "examples/app_v600_local_playback_boundary.py",
    "examples/app_v600_motion_extension_hook.py",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
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


def _load(relative: str) -> object:
    path = PROJECT_ROOT / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    _require(spec is not None and spec.loader is not None, f"cannot load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    paths = _git("diff", "HEAD", "--name-only").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    actual = {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }
    _require(
        actual == EXPECTED_SURFACE,
        f"Control B exact surface drift: {sorted(actual)!r}",
    )
    print("[OK] baseline and exact nine-file Control B surface conform")


def check_docs_and_task_boundary() -> None:
    guide = (PROJECT_ROOT / "docs/v600_v5_to_v6_session_migration.md").read_text(
        encoding="utf-8"
    )
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for text, begin, end in (
        (
            guide,
            "FW-RT6-11c-B-MIGRATION-EXAMPLES:BEGIN",
            "FW-RT6-11c-B-MIGRATION-EXAMPLES:END",
        ),
        (
            facade,
            "FW-RT6-11c-B-PUBLIC-EXAMPLES:BEGIN",
            "FW-RT6-11c-B-PUBLIC-EXAMPLES:END",
        ),
        (
            app,
            "FW-RT6-11c-B-APP-EXAMPLES:BEGIN",
            "FW-RT6-11c-B-APP-EXAMPLES:END",
        ),
    ):
        _require(text.count(begin) == 1, f"missing marker: {begin}")
        _require(text.count(end) == 1, f"missing marker: {end}")

    for relative in EXAMPLES:
        _require(relative in guide, f"guide does not list {relative}")
    for phrase in (
        "partial transcript/audio streaming remains unsupported",
        "physical-stop confirmation",
        "typed `not_configured`",
        "127 / UNCHANGED",
    ):
        _require(
            phrase in guide or phrase in facade or phrase in app,
            f"Control B contract phrase missing: {phrase}",
        )

    section = tasklist.split(
        "## FW-RT6-11c — Migration guide and examples", 1
    )[1].split("## FW-RT6-12a", 1)[0]
    _require(section.count("- [ ]") == 0, "FW-RT6-11c task remains open")
    _require(section.count("- [x]") == 8, "Control C task count drift")
    _require(
        (
            PROJECT_ROOT
            / "scripts/check_v600_migration_examples_acceptance.py"
        ).is_file(),
        "Control C aggregate gate missing",
    )
    print("[OK] migration docs and four Control B boundaries conform")
    print("[OK] FW-RT6-11c task boundary is 8 / 8 acceptance-candidates")


def check_example_sources_and_import_safety() -> None:
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
        _require("os.environ" not in source, f"{relative}: environment read present")

    code = r"""
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
    output = _run(
        [sys.executable, "-I", "-c", code, str(PROJECT_ROOT), *EXAMPLES],
        environment=_credential_free_environment(),
    )
    _require("import_safe: PASS" in output, "Control B import probe failed")
    print("[OK] examples use only the public root and import without credentials")


def check_host_captured_audio() -> None:
    module = _load(EXAMPLES[0])
    facts = module.run_host_captured_audio()
    _require(
        facts
        == (
            "completed",
            "host captured fake transcript",
            "opaque_id",
            False,
            False,
            False,
        ),
        f"host-audio facts drifted: {facts!r}",
    )
    print("[OK] opaque host-audio handoff is fake, audio-free, and microphone-free")


def check_interrupt_partial_completion() -> None:
    module = _load(EXAMPLES[1])
    facts = module.run_interrupt_partial_completion()
    _require(
        facts
        == (
            True,
            "not_implemented",
            "partial",
            True,
            True,
            0,
            0,
            False,
            False,
        ),
        f"interrupt partial facts drifted: {facts!r}",
    )
    print("[OK] interrupt partial is terminal aggregation, not streaming or hard cancel")


def check_local_playback_boundary() -> None:
    module = _load(EXAMPLES[2])
    facts = module.run_local_playback_boundary()
    _require(
        facts == ("not_implemented", True, True, False, False),
        f"host playback facts drifted: {facts!r}",
    )
    print("[OK] host playback request/ack never claims physical stop or playback work")


def check_motion_extension_hook() -> None:
    module = _load(EXAMPLES[3])
    facts = module.run_motion_extension_hook()
    _require(facts[0] == "completed", "motion example changed conversation outcome")
    _require(
        facts[1] == ("listening", "thinking", "speaking", "completed"),
        f"motion lifecycle signals drifted: {facts[1]!r}",
    )
    _require(
        facts[2] == ("not_configured", "not_configured"),
        f"motion outcomes drifted: {facts[2]!r}",
    )
    _require(facts[3:] == (1, False), "motion example terminal/VTS facts drifted")
    print("[OK] host motion mapping stays typed and cannot replace conversation terminal")


def check_credential_free_execution() -> None:
    code = (
        "import runpy,sys;"
        f"sys.path.insert(0,{str(PROJECT_ROOT)!r});"
        "runpy.run_path(sys.argv[1],run_name='__main__')"
    )
    for relative in EXAMPLES:
        output = _run(
            [sys.executable, "-I", "-c", code, str(PROJECT_ROOT / relative)],
            environment=_credential_free_environment(),
        )
        _require(
            "provider_execution_performed: False" in output,
            f"{relative}: provider-free execution fact missing",
        )
    print("[OK] four examples execute without credentials or optional provider SDKs")


def check_accepted_control_a_and_root() -> None:
    _run(
        [
            sys.executable,
            "scripts/smoke_v600_migration_examples_control_a.py",
            "--source-only",
        ]
    )
    _run(
        [
            sys.executable,
            "scripts/check_v600_root_public_api_cleanup_acceptance.py",
            "--source-only",
        ]
    )
    _run(
        [
            sys.executable,
            "scripts/check_v600_session_compatibility_acceptance.py",
            "--source-only",
        ]
    )
    import framework

    _require(len(framework.__all__) == 127, "root-public inventory changed")
    for name in (
        "run_host_captured_audio",
        "run_interrupt_partial_completion",
        "run_local_playback_boundary",
        "run_motion_extension_hook",
    ):
        _require(name not in framework.__all__, f"example leaked root-public: {name}")
    _require(
        not any(path.startswith("framework/") for path in EXPECTED_SURFACE),
        "Control B surface includes runtime source",
    )
    print("[OK] accepted Control A/11a/11b gates and frozen 127-name root conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_docs_and_task_boundary()
    check_example_sources_and_import_safety()
    check_host_captured_audio()
    check_interrupt_partial_completion()
    check_local_playback_boundary()
    check_motion_extension_hook()
    check_credential_free_execution()
    check_accepted_control_a_and_root()
    print("v600_rt6_11c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11c_control_b_exact_surface: 9 files")
    print("v600_rt6_11c_new_control_b_examples: 4 / PROVIDER-FREE")
    print("v600_rt6_11c_all_examples: 6 / PUBLIC ROOT ONLY")
    print("v600_rt6_11c_partial_streaming_claimed: False")
    print("v600_rt6_11c_physical_playback_stop_claimed: False")
    print("v600_rt6_11c_provider_execution: False")
    print("v600_rt6_11c_network_execution: False")
    print("v600_rt6_11c_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11c_control_c_exact_surface: 7 files")
    print("v600_rt6_11c_task_count: 8 / 8 ACCEPTED-CANDIDATE")
    print("v600_rt6_11c_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_11c_control_c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11c Control B migration examples gate passed")


if __name__ == "__main__":
    main()
