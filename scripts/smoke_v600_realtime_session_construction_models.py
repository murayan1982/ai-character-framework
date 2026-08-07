"""FW-RT6-4a Control A construction/config model smoke.

Offline/provider-free: validates the exact additive public-model candidate,
strict construction-result invariants, root import safety, unchanged
``RealtimeSession`` constructor/factory adoption boundary, focused unit tests,
and the full normal unit suite without provider, network, microphone, playback,
real VTube Studio, DRC, or root-draft stash access.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import fields
import inspect
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "0192f941e3a2009d203535ec0c97a6ceb69050ed"
EXPECTED_SURFACE = {
    "docs/v600_realtime_session_construction_contract.md",
    "framework/__init__.py",
    "framework/public_api.py",
    "framework/realtime.py",
    "framework/realtime_session_config.py",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_realtime_session_construction_models.py",
    "scripts/smoke_v600_version_metadata.py",
    "tests/test_realtime_session_construction.py",
}
EXPECTED_REALTIME_SESSION_SHA256 = (
    "c392d1c48da7b05bf48c9d07a619a95193c201bd62423bbd4116db7397283d1c"
)
EXPECTED_REALTIME_STAGE_SHA256 = (
    "0bb4a185ddd94e6386c6d4c8348127a95ca79d92e12c69ce31b5aa7d0b3b4dda"
)
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
    return paths - {".vscode/settings.json"}


def _check_repository_contract(*, source_only: bool) -> None:
    if source_only:
        print("[OK] source-only mode skips Git metadata while preserving source checks")
        return

    _assert((PROJECT_ROOT / ".git").exists(), "strict mode requires a Git working tree")
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected FW baseline HEAD")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_BASELINE, "origin/main baseline drift")
    _assert(_git("branch", "--show-current") == "main", "FW-RT6-4a requires main branch")
    _assert(
        "ai-character-framework" in _git("remote", "get-url", "origin").lower(),
        "origin is not the AI Character Framework repository",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"FW-RT6-4a Control A exact surface mismatch: {sorted(_changed_paths())}",
    )
    print("[OK] baseline and exact ten-file Control A surface conform")


def _sha256(relative: str) -> str:
    import hashlib

    content = (PROJECT_ROOT / relative).read_bytes()
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


def _check_deferred_runtime_surface() -> None:
    _assert(
        _sha256("framework/realtime_session.py") == EXPECTED_REALTIME_SESSION_SHA256,
        "RealtimeSession runtime source changed during Control A",
    )
    _assert(
        _sha256("framework/realtime_stage.py") == EXPECTED_REALTIME_STAGE_SHA256,
        "accepted realtime stage protocol source changed during Control A",
    )

    from framework.realtime_session import RealtimeSession, create_realtime_session

    expected = (
        "project_root",
        "public_metadata",
        "real_runtime_enabled",
        "voice_input_stage",
        "text_generation_stage",
        "voice_output_stage",
        "motion_stage",
    )
    constructor = tuple(
        name
        for name, parameter in inspect.signature(RealtimeSession).parameters.items()
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY
    )
    factory = tuple(inspect.signature(create_realtime_session).parameters)
    _assert(constructor == expected, f"constructor adoption occurred early: {constructor}")
    _assert(factory == expected, f"factory adoption occurred early: {factory}")
    print("[OK] RealtimeSession adoption remains deferred and accepted runtime source is unchanged")


def _check_source_import_safety() -> None:
    path = PROJECT_ROOT / "framework" / "realtime_session_config.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    _assert(not (roots & FORBIDDEN_PROVIDER_ROOTS), "construction model imports provider runtime")

    source = path.read_text(encoding="utf-8")
    for forbidden in (
        "os.environ",
        "getenv(",
        "open(",
        "Path.home",
        "subprocess",
        "socket",
    ):
        _assert(
            forbidden not in source,
            f"construction model contains forbidden access: {forbidden}",
        )
    print(
        "[OK] construction model source is provider-, environment-, "
        "filesystem-, and execution-free"
    )


def _check_public_models() -> None:
    import framework
    from framework.identity import SessionId
    from framework.public_api import (
        PUBLIC_API_NAMES,
        REALTIME_SESSION_CONSTRUCTION_PUBLIC_EXPORTS,
    )
    from framework.realtime import RealtimeErrorCode
    from framework.realtime_session_config import (
        RealtimeSessionConfig,
        RealtimeSessionConstructionResult,
        RealtimeSessionConstructionStatus,
    )

    _assert(len(PUBLIC_API_NAMES) == 124, "canonical root-public count must be 124")
    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ manifest drift")
    _assert(
        PUBLIC_API_NAMES[:121] == tuple(framework.__all__[:121]),
        "accepted 121-name root prefix drift",
    )
    _assert(
        tuple(REALTIME_SESSION_CONSTRUCTION_PUBLIC_EXPORTS)
        == (
            "RealtimeSessionConfig",
            "RealtimeSessionConstructionStatus",
            "RealtimeSessionConstructionResult",
        ),
        "construction public group drift",
    )
    _assert(
        PUBLIC_API_NAMES[121:] == tuple(REALTIME_SESSION_CONSTRUCTION_PUBLIC_EXPORTS),
        "construction names are not the exact additive suffix",
    )
    _assert(
        RealtimeErrorCode.CONFIGURATION_MISSING.value == "configuration_missing",
        "typed configuration missing error code drift",
    )

    config_fields = tuple(item.name for item in fields(RealtimeSessionConfig))
    _assert(
        config_fields
        == (
            "real_runtime_enabled",
            "voice_input_stage",
            "text_generation_stage",
            "voice_output_stage",
            "motion_stage",
        ),
        f"RealtimeSessionConfig field drift: {config_fields}",
    )
    sentinel = object()
    config = RealtimeSessionConfig(text_generation_stage=sentinel)
    _assert(config.real_runtime_enabled is False, "real runtime must default off")
    _assert(config.text_generation_stage is sentinel, "stage binding identity drift")
    _assert("stage" not in repr(config), "stage binding leaked through config repr")

    result_fields = tuple(item.name for item in fields(RealtimeSessionConstructionResult))
    _assert(
        result_fields
        == (
            "status",
            "session_id",
            "configuration_complete",
            "runtime_executable",
            "real_runtime_requested",
            "real_runtime_enabled",
            "missing_stage_kinds",
            "failed_stage_kinds",
            "safe_message",
            "retryable",
            "public_metadata",
        ),
        f"construction result field drift: {result_fields}",
    )
    _assert(
        tuple(item.value for item in RealtimeSessionConstructionStatus)
        == (
            "mock_ready",
            "real_configuration_ready",
            "configuration_incomplete",
            "preflight_failed",
        ),
        "construction status vocabulary drift",
    )

    mock = RealtimeSessionConstructionResult(
        status="mock_ready",
        session_id=SessionId.new(),
        configuration_complete=True,
        runtime_executable=True,
        real_runtime_requested=False,
        real_runtime_enabled=False,
    )
    _assert(
        mock.status is RealtimeSessionConstructionStatus.MOCK_READY,
        "status normalization drift",
    )
    incomplete = RealtimeSessionConstructionResult(
        status="configuration_incomplete",
        session_id=SessionId.new(),
        configuration_complete=False,
        runtime_executable=False,
        real_runtime_requested=True,
        real_runtime_enabled=False,
        missing_stage_kinds=("text_generation",),
    )
    _assert(incomplete.missing_stage_kinds == ("text_generation",), "missing stage drift")
    print("[OK] config, status, result, invariants, typed error, and exact public suffix conform")


def _check_root_import_safety() -> None:
    code = r'''
import sys
import framework

assert len(framework.__all__) == 124
assert framework.__all__[-3:] == [
    "RealtimeSessionConfig",
    "RealtimeSessionConstructionStatus",
    "RealtimeSessionConstructionResult",
]
assert "framework.realtime_session_config" in sys.modules
assert "framework.realtime_stage" not in sys.modules
forbidden = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "pyaudio",
    "sounddevice",
    "tts.voice_engine",
    "stt.stt_engine",
    "live2d.vts_client",
}
loaded = sorted(name for name in forbidden if name in sys.modules)
if loaded:
    raise AssertionError(loaded)
print("construction-root-import-pass")
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"root import safety failed:\n{output}")
    _assert("construction-root-import-pass" in output, "root import subprocess incomplete")
    print("[OK] root import binds construction models without stage package or provider SDK import")


def _run(relative: str, *args: str, expected: tuple[str, ...] = ()) -> str:
    completed = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / relative), *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    output = completed.stdout + completed.stderr
    _assert(completed.returncode == 0, f"{relative} failed:\n{output}")
    for phrase in expected:
        _assert(phrase in output, f"{relative} output missing: {phrase}")
    return output


def _check_tests_and_regressions() -> None:
    focused = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_realtime_session_construction", "-v"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(PROJECT_ROOT)},
    )
    focused_output = focused.stdout + focused.stderr
    _assert(focused.returncode == 0, f"focused construction tests failed:\n{focused_output}")
    _assert("Ran 10 tests" in focused_output, "focused construction test count drift")

    full = _run(
        "scripts/run_v600_unit_tests.py",
        expected=(
            "v600_unit_test_count: 55",
            "Ran 55 tests",
            "v600_unit_test_result: PASS",
        ),
    )
    _assert("FAILED" not in full, "full normal unit suite reported failure")

    _run(
        "scripts/smoke_v600_public_api_manifest.py",
        expected=(
            "v600_public_api_manifest_name_count: 124",
            "v600_realtime_session_construction_models_status: implemented-awaiting-review",
        ),
    )
    _run("scripts/smoke_v600_version_metadata.py", expected=("v600_root_public_name_count: 124",))
    _run(
        "scripts/smoke_app_sdk.py",
        expected=("[OK] app SDK canonical public API manifest is stable",),
    )
    print("[OK] focused 10-test layer, full 55-test suite, and canonical public regressions pass")


def _check_contract_document() -> None:
    text = (PROJECT_ROOT / "docs" / "v600_realtime_session_construction_contract.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "FW-RT6-4a-A-CONSTRUCTION-MODELS:BEGIN",
        "FW-RT6-4a-A-CONSTRUCTION-MODELS:END",
        EXPECTED_BASELINE,
        "status: IMPLEMENTED / AWAITING_REVIEW",
        "root-public names: 124 / ADDITIVE THREE-NAME SUFFIX",
        "RealtimeSession runtime adoption: False / DEFERRED",
        "Control B: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _assert(marker in text, f"construction contract missing marker: {marker}")
    print("[OK] Control A contract records exact additive scope and deferred runtime adoption")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="skip Git baseline/surface checks for a git-archive source bundle",
    )
    args = parser.parse_args()

    _check_repository_contract(source_only=args.source_only)
    _check_deferred_runtime_surface()
    _check_source_import_safety()
    _check_public_models()
    _check_root_import_safety()
    _check_tests_and_regressions()
    _check_contract_document()

    print("v600_rt6_4a_control_a_status: implemented-awaiting-review")
    print("v600_rt6_4a_control_a_exact_surface: 10 files")
    print("v600_rt6_4a_root_public_names: 124")
    print("v600_rt6_4a_construction_public_models: 3")
    print("v600_rt6_4a_realtime_error_configuration_missing: True")
    print("v600_rt6_4a_default_real_runtime_enabled: False")
    print("v600_rt6_4a_stage_repr_exposed: False")
    print("v600_rt6_4a_realtime_session_runtime_changed: False")
    print("v600_rt6_4a_focused_unit_tests: 10 / PASS")
    print("v600_rt6_4a_full_unit_tests: 55 / PASS")
    print("v600_rt6_4a_provider_execution: False")
    print("v600_rt6_4a_network_execution: False")
    print("v600_rt6_4a_microphone_access: False")
    print("v600_rt6_4a_playback_execution: False")
    print("v600_rt6_4a_real_vts_execution: False")
    print("v600_rt6_4a_drc_accessed_or_changed: False")
    print("v600_rt6_4a_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_4a_control_b: NOT_AUTHORIZED")
    print("v600_rt6_4a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
