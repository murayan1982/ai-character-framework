"""FW-RT6-3a Control B provider-neutral stage injection smoke.

Offline/mock-safe: validates the exact five-file Control B surface, additive
keyword-only RealtimeSession stage injection, lazy stable-package loading,
provider-neutral binding validation, fake-stage ownership, once-only close,
count-only close diagnostics, and accepted runtime regressions without provider,
network, microphone, playback, real VTube Studio, private configuration, DRC
repository, or root-draft stash execution.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "af474e2ceec9988bec1b7e7fadfe2d4037774597"
EXPECTED_BASELINE_PARENT = "6fe95075e1c9ae9e62150eb9844edfe9f004a8e2"
EXPECTED_BASELINE_SUBJECT = "feat/test: add realtime stage protocols"
EXPECTED_CONTROL_A_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/realtime_stage.py",
    "scripts/smoke_v600_realtime_stage_protocols.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_stage_injection.py",
}
UNCHANGED_PATHS = (
    "framework/realtime_stage.py",
    "framework/realtime_generation_gate.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_terminal_registry.py",
    "framework/public_api.py",
    "framework/__init__.py",
)
FORBIDDEN_IMPORT_ROOTS = {
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
}
EXPECTED_FACTORY_PARAMETERS = (
    "project_root",
    "public_metadata",
    "real_runtime_enabled",
    "voice_input_stage",
    "text_generation_stage",
    "voice_output_stage",
    "motion_stage",
)
EXPECTED_STAGE_KINDS = (
    "voice_input",
    "text_generation",
    "voice_output",
    "motion",
)


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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
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
    control_a_surface = {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", EXPECTED_BASELINE
        ).splitlines()
        if line.strip()
    }
    _assert(
        control_a_surface == EXPECTED_CONTROL_A_SURFACE,
        f"Control A surface drift: {sorted(control_a_surface)}",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control B surface: {sorted(_changed_paths())}",
    )
    for relative in UNCHANGED_PATHS:
        _assert(
            _git("hash-object", relative) == _git("rev-parse", f"HEAD:{relative}"),
            f"unrelated accepted source changed: {relative}",
        )
    print("[OK] Control A history and exact five-file Control B surface conform")


def check_source_and_import_safety() -> None:
    source_path = PROJECT_ROOT / "framework" / "realtime_session.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    for forbidden in FORBIDDEN_IMPORT_ROOTS:
        _assert(
            all(not name.startswith(forbidden) for name in imported),
            f"provider/runtime import leaked into RealtimeSession: {forbidden}",
        )
    for phrase in (
        "def _validated_injected_stages(",
        "if not any(stage is not None for stage in supplied):",
        "from .realtime_stage import (",
        "def injected_stage_kinds(self) -> tuple[str, ...]:",
        "def stage_diagnostics(self) -> Mapping[str, int]:",
        "def _close_injected_stages(self) -> None:",
        "self._close_injected_stages()",
    ):
        _assert(phrase in source, f"stage injection source marker missing: {phrase}")

    code = r'''
import sys
import framework
assert "framework.realtime_stage" not in sys.modules
assert len(framework.__all__) == 121
session = framework.create_realtime_session()
assert "framework.realtime_stage" not in sys.modules
assert session.injected_stage_kinds == ()
assert dict(session.stage_diagnostics) == {
    "injected_stage_count": 0,
    "stage_close_count": 0,
    "stage_close_error_count": 0,
}
session.close()
for name in (
    "elevenlabs", "pyvts", "pyaudio", "sounddevice",
    "speech_recognition", "google.genai", "xai_sdk",
):
    assert name not in sys.modules
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(
        completed.returncode == 0,
        f"lazy root import contract failed:\n{completed.stdout}{completed.stderr}",
    )
    print("[OK] no-stage root import remains lazy and provider/runtime safe")


def check_factory_contract() -> None:
    import framework
    from framework.realtime_session import RealtimeSession

    factory = inspect.signature(framework.create_realtime_session)
    constructor = inspect.signature(RealtimeSession)
    _assert(tuple(factory.parameters) == EXPECTED_FACTORY_PARAMETERS, "factory parameter drift")
    _assert(tuple(constructor.parameters) == EXPECTED_FACTORY_PARAMETERS, "constructor parameter drift")
    for signature in (factory, constructor):
        for name, parameter in signature.parameters.items():
            _assert(
                parameter.kind is inspect.Parameter.KEYWORD_ONLY,
                f"{name} is not keyword-only",
            )
        for name in EXPECTED_FACTORY_PARAMETERS[3:]:
            _assert(signature.parameters[name].default is None, f"{name} default drift")
    _assert(len(framework.__all__) == 121, "root-public name count drift")
    _assert(tuple(framework.__all__) == tuple(framework.PUBLIC_API_NAMES), "root manifest drift")
    print("[OK] factory change is additive, keyword-only, and root-name neutral")


class _FakeStage:
    def __init__(self, stage_kind: object, *, close_raises: bool = False) -> None:
        self.stage_kind = stage_kind
        self.close_raises = close_raises
        self.calls: list[str] = []

    def preflight(self) -> object:
        self.calls.append("preflight")
        raise AssertionError("preflight must not run in Control B")

    def capability(self) -> object:
        self.calls.append("capability")
        raise AssertionError("capability must not run in Control B")

    def start(self, *, context: object, request: object) -> object:
        self.calls.append("start")
        raise AssertionError("start must not run in Control B")

    def cancel(self, *, context: object) -> bool:
        self.calls.append("cancel")
        raise AssertionError("cancel must not run in Control B")

    def close(self) -> None:
        self.calls.append("close")
        if self.close_raises:
            raise RuntimeError("credential=/private/operator/token")


def _fake_stages(*, close_error_kind: str | None = None) -> dict[str, _FakeStage]:
    from framework.realtime_stage import RealtimeStageKind

    return {
        "voice_input": _FakeStage(
            RealtimeStageKind.VOICE_INPUT,
            close_raises=close_error_kind == "voice_input",
        ),
        "text_generation": _FakeStage(
            "text_generation",
            close_raises=close_error_kind == "text_generation",
        ),
        "voice_output": _FakeStage(
            RealtimeStageKind.VOICE_OUTPUT,
            close_raises=close_error_kind == "voice_output",
        ),
        "motion": _FakeStage(
            "motion",
            close_raises=close_error_kind == "motion",
        ),
    }


def _create_with(stages: dict[str, _FakeStage]) -> Any:
    import framework

    return framework.create_realtime_session(
        voice_input_stage=stages["voice_input"],
        text_generation_stage=stages["text_generation"],
        voice_output_stage=stages["voice_output"],
        motion_stage=stages["motion"],
    )


def check_fake_stage_injection_and_mock_path() -> None:
    stages = _fake_stages()
    session = _create_with(stages)

    _assert(session.injected_stage_kinds == EXPECTED_STAGE_KINDS, "stage kind order drift")
    _assert(
        dict(session.stage_diagnostics)
        == {
            "injected_stage_count": 4,
            "stage_close_count": 0,
            "stage_close_error_count": 0,
        },
        "initial stage diagnostics drift",
    )
    _assert(isinstance(session.stage_diagnostics, MappingProxyType), "diagnostics mutable type")
    try:
        session.stage_diagnostics["injected_stage_count"] = 99
    except TypeError:
        pass
    else:
        raise AssertionError("stage diagnostics are mutable")

    info = session.info
    _assert(info.supports_motion is True, "injected motion support not reflected")
    _assert(info.public_metadata["injected_stage_count"] == 4, "info count drift")
    _assert(info.public_metadata["injected_stage_kinds"] == EXPECTED_STAGE_KINDS, "info kinds drift")
    _assert(all(stage.calls == [] for stage in stages.values()), "construction executed a stage")

    result = session.run_turn(input_text="control-b-mock-path")
    _assert(result.outcome.value == "completed", "accepted mock turn outcome drift")
    _assert(all(stage.calls == [] for stage in stages.values()), "run_turn executed injected stage")
    _assert(session.generation_diagnostics["stale_completion_count"] == 0, "generation drift")

    session.close()
    session.close()
    _assert(all(stage.calls == ["close"] for stage in stages.values()), "stage close not once-only")
    _assert(
        dict(session.stage_diagnostics)
        == {
            "injected_stage_count": 4,
            "stage_close_count": 4,
            "stage_close_error_count": 0,
        },
        "closed stage diagnostics drift",
    )
    _assert(session.is_closed, "session did not close")
    print("[OK] four fake stages inject without execution and close exactly once")


def check_validation_and_safe_close_failure() -> None:
    import framework

    class _MissingClose:
        stage_kind = "voice_input"

        def preflight(self) -> object: return None
        def capability(self) -> object: return None
        def start(self, *, context: object, request: object) -> object: return None
        def cancel(self, *, context: object) -> bool: return False

    for action, expected_type in (
        (lambda: framework.create_realtime_session(voice_input_stage=_MissingClose()), TypeError),
        (lambda: framework.create_realtime_session(voice_input_stage=_FakeStage("motion")), ValueError),
    ):
        try:
            action()
        except expected_type as error:
            _assert("private" not in str(error).lower(), "private detail leaked in validation")
        else:
            raise AssertionError(f"expected {expected_type.__name__}")

    class _ExplodingKind(_FakeStage):
        @property
        def stage_kind(self) -> object:
            raise RuntimeError("C:/Users/operator/private-token")

        @stage_kind.setter
        def stage_kind(self, value: object) -> None:
            pass

    try:
        framework.create_realtime_session(voice_input_stage=_ExplodingKind("voice_input"))
    except TypeError as error:
        text = str(error)
        _assert("Users" not in text and "token" not in text, "raw stage-kind error leaked")
    else:
        raise AssertionError("exploding stage_kind was accepted")

    stages = _fake_stages(close_error_kind="motion")
    session = _create_with(stages)
    session.close()
    _assert(session.is_closed, "close failure prevented session close")
    _assert(stages["motion"].calls == ["close"], "failing stage close count drift")
    _assert(
        dict(session.stage_diagnostics)
        == {
            "injected_stage_count": 4,
            "stage_close_count": 3,
            "stage_close_error_count": 1,
        },
        "close error diagnostics drift",
    )
    _assert("credential" not in repr(session.info), "close exception leaked through info")
    print("[OK] invalid bindings reject safely and close failures remain count-only")


def _load_script(relative_path: str, module_name: str) -> Any:
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load regression script: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_control_a_and_runtime_regressions() -> None:
    control_a = _load_script(
        "scripts/smoke_v600_realtime_stage_protocols.py",
        "_rt6_3a_control_a_regression",
    )
    for name in (
        "check_stable_package_shape",
        "check_context_and_envelope_contract",
        "check_protocol_signatures_and_provider_neutrality",
        "check_structural_fake_stages",
        "check_docs_and_deferred_boundaries",
        "check_prior_public_compatibility",
    ):
        getattr(control_a, name)()

    terminal_callback = _load_script(
        "scripts/smoke_v600_realtime_generation_gate_terminal_callback_compatibility.py",
        "_rt6_3a_terminal_callback_regression",
    )
    terminal_callback.check_terminal_callback_late_operations()
    terminal_callback.check_normal_post_turn_no_active_interrupt()

    concurrency = _load_script(
        "scripts/smoke_v600_realtime_terminal_registry_reentrant_concurrency.py",
        "_rt6_3a_terminal_concurrency_regression",
    )
    concurrency.check_reentrant_terminal_callback_rejection()
    concurrency.check_same_turn_concurrent_run_is_one_group()
    concurrency.check_different_turn_groups_remain_serialized()
    concurrency.check_close_contract_is_preserved()

    event_close = _load_script(
        "scripts/smoke_v600_realtime_event_hub_close_hardening.py",
        "_rt6_3a_event_close_regression",
    )
    event_close.check_close_seals_and_post_close_is_silent()
    event_close.check_reentrant_close_is_deferred()
    event_close.check_concurrent_operations_do_not_interleave()
    event_close.check_concurrent_close_waits_for_operation_boundary()
    print("[OK] Control A, generation, terminal, and close/concurrency behavior remain conformant")


def check_docs() -> None:
    for relative in (
        "docs/v600_realtime_stage_protocol_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-3a-B-STAGE-INJECTION:BEGIN" in text
            and "FW-RT6-3a-B-STAGE-INJECTION:END" in text,
            f"Control B marker missing: {relative}",
        )
        for phrase in (
            "af474e2ceec9988bec1b7e7fadfe2d4037774597",
            "fake stage injection: PASS",
            "root-public names: 121 / UNCHANGED",
            "provider SDK root import: False",
            "real orchestration: False" if relative != "docs/v600_realtime_stage_protocol_contract.md" else "real unified orchestration: False",
            "Control C: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _assert(phrase in text, f"{relative} missing truthful boundary: {phrase}")
    print("[OK] docs record injection without claiming orchestration or aggregate acceptance")


def check_public_smokes() -> None:
    for relative in (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_public_facade.py",
        "scripts/smoke_app_sdk.py",
    ):
        completed = subprocess.run(
            [sys.executable, relative],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        _assert(
            completed.returncode == 0,
            f"public compatibility smoke failed: {relative}\n{completed.stdout}{completed.stderr}",
        )
    print("[OK] root-public, version, facade, and app SDK compatibility remain conformant")


def main() -> None:
    check_repository_contract()
    check_source_and_import_safety()
    check_factory_contract()
    check_fake_stage_injection_and_mock_path()
    check_validation_and_safe_close_failure()
    check_docs()
    check_public_smokes()
    check_control_a_and_runtime_regressions()
    print("v600_rt6_3a_control_b_status: implemented-awaiting-review")
    print("v600_rt6_3a_control_b_exact_change_surface_count: 5")
    print("v600_rt6_3a_control_b_factory_parameters: 7 / keyword-only")
    print("v600_rt6_3a_control_b_injected_stage_kinds: voice_input/text_generation/voice_output/motion")
    print("v600_rt6_3a_control_b_fake_stage_injection: PASS")
    print("v600_rt6_3a_control_b_constructor_stage_calls: 0")
    print("v600_rt6_3a_control_b_run_turn_stage_starts: 0 / deferred")
    print("v600_rt6_3a_control_b_stage_close_once: True")
    print("v600_rt6_3a_control_b_close_exception_exposed: False")
    print("v600_rt6_3a_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_3a_control_b_provider_sdk_root_import: False")
    print("v600_rt6_3a_control_b_real_orchestration: False")
    print("v600_rt6_3a_control_b_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3a_control_b_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3a_control_b_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_3a_control_c_authorized: False")
    print("[OK] FW-RT6-3a Control B provider-neutral stage injection conforms")


if __name__ == "__main__":
    main()
