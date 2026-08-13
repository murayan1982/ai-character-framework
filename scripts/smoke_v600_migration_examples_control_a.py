"""FW-RT6-11c Control A migration/example acceptance gate."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "7f0f66b11347257ac239982c4118fe8277c2a1e3"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_v5_to_v6_session_migration.md",
    "examples/app_v600_realtime_text_only.py",
    "examples/app_v600_realtime_unavailable_fallback.py",
    "scripts/smoke_v600_migration_examples_control_a.py",
    "tests/test_migration_examples_control_a.py",
}
EXAMPLES = (
    "examples/app_v600_realtime_text_only.py",
    "examples/app_v600_realtime_unavailable_fallback.py",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
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
        f"Control A exact surface drift: {sorted(actual)!r}",
    )
    print("[OK] baseline and exact seven-file Control A surface conform")


def check_docs() -> None:
    guide = (PROJECT_ROOT / "docs/v600_v5_to_v6_session_migration.md").read_text(
        encoding="utf-8"
    )
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    app = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")

    for phrase in (
        "TextChatSession",
        "VoiceInputSession",
        "VoiceOutputSession",
        "MotionSession",
        "v5_standalone",
        "v5_skeleton",
        "v6_unified",
        "host-selected",
        "never silently executes",
        "host-captured audio",
        "local host-playback",
        "motion lifecycle extension hooks",
    ):
        _require(phrase in guide, f"migration guide phrase missing: {phrase}")
    for text, begin, end in (
        (
            facade,
            "FW-RT6-11c-A-PUBLIC-MIGRATION:BEGIN",
            "FW-RT6-11c-A-PUBLIC-MIGRATION:END",
        ),
        (
            app,
            "FW-RT6-11c-A-MIGRATION-FOUNDATION:BEGIN",
            "FW-RT6-11c-A-MIGRATION-FOUNDATION:END",
        ),
    ):
        _require(text.count(begin) == 1, f"missing marker: {begin}")
        _require(text.count(end) == 1, f"missing marker: {end}")

    section = tasklist.split(
        "## FW-RT6-11c — Migration guide and examples", 1
    )[1].split("## FW-RT6-12a", 1)[0]
    _require(section.count("- [ ]") == 8, "Control A closed an aggregate task")
    _require(section.count("- [x]") == 0, "Control A changed task state")
    print("[OK] migration guide and public/app contracts conform")
    print("[OK] FW-RT6-11c task boundary remains 0 / 8 closed")


def check_example_sources() -> None:
    for relative in EXAMPLES:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative)
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
        _require("framework" in imports, f"{relative}: framework root import missing")
        _require(
            all(name in {"__future__", "framework"} for name in imports),
            f"{relative}: unexpected import: {sorted(imports)!r}",
        )
        _require(
            'if __name__ == "__main__":' in source,
            f"{relative}: main guard missing",
        )
        _require("os.environ" not in source, f"{relative}: environment read present")
        _require("getenv(" not in source, f"{relative}: environment read present")
    print("[OK] examples use only the public framework root and main guards")


def check_import_safety() -> None:
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
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(PROJECT_ROOT),
            *EXAMPLES,
        ]
    )
    _require("import_safe: PASS" in output, "example import-safety probe failed")
    print("[OK] examples import without credentials or optional provider SDKs")


def _run_example(relative: str) -> str:
    code = r"""
import runpy
import sys
from pathlib import Path

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
runpy.run_path(str(root / sys.argv[2]), run_name="__main__")
"""
    return _run(
        [
            sys.executable,
            "-I",
            "-c",
            code,
            str(PROJECT_ROOT),
            relative,
        ]
    )


def check_example_execution() -> None:
    text_output = _run_example(EXAMPLES[0])
    for phrase in (
        "compatibility_mode: v5_skeleton",
        "turn_outcome: completed",
        "mock_runtime: True",
        "provider_execution_performed: False",
    ):
        _require(phrase in text_output, f"text-only output drift: {phrase}")

    fallback_output = _run_example(EXAMPLES[1])
    for phrase in (
        "requested_mode: v6_unified",
        "construction_status: configuration_incomplete",
        "requested_outcome: rejected",
        "fallback_selected_by_host: True",
        "fallback_mode: v5_skeleton",
        "fallback_mock_runtime: True",
        "provider_execution_performed: False",
    ):
        _require(phrase in fallback_output, f"fallback output drift: {phrase}")
    print("[OK] text-only and explicit unavailable/fallback examples conform")


def check_accepted_regressions() -> None:
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
    print("[OK] accepted FW-RT6-11a/11b regression gates conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_docs()
    check_example_sources()
    check_import_safety()
    check_example_execution()
    check_accepted_regressions()
    print("v600_rt6_11c_control_a_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11c_control_a_exact_surface: 7 files")
    print("v600_rt6_11c_new_examples: 2 / PROVIDER-FREE")
    print("v600_rt6_11c_provider_credentials_required: False")
    print("v600_rt6_11c_provider_execution: False")
    print("v600_rt6_11c_network_execution: False")
    print("v600_rt6_11c_task_count: 0 / 8 CLOSED")
    print("v600_rt6_11c_control_b: NOT_AUTHORIZED")
    print("v600_rt6_11c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11c Control A migration/example gate passed")


if __name__ == "__main__":
    main()
