"""FW-RT6-0b Control A canonical public API manifest smoke.

This smoke is source-safe and offline-safe. It verifies the exact root-public
manifest, lazy provider-compatibility behavior, and the absence of duplicated
``framework.__all__`` construction without executing providers or network I/O.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

FORBIDDEN_AFTER_ROOT_IMPORT = {
    "core.runtime",
    "core.session",
    "core.pipeline",
    "stt.stt_engine",
    "tts.voice_engine",
    "elevenlabs",
    "openai",
    "pyvts",
    "websocket",
    "websockets",
    "live2d.vts_client",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _check_manifest_shape() -> None:
    import framework
    from framework.public_api import (
        PROVIDER_COMPAT_LAZY_EXPORT_MODULES,
        IDENTITY_PUBLIC_EXPORTS,
        LIFECYCLE_PUBLIC_EXPORTS,
        REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS,
        PROVIDER_COMPAT_LAZY_EXPORTS,
        PUBLIC_API_GROUPS,
        PUBLIC_API_NAMES,
    )

    _assert(
        tuple(framework.__all__) == PUBLIC_API_NAMES,
        "framework.__all__ must exactly match PUBLIC_API_NAMES",
    )
    _assert(
        len(PUBLIC_API_NAMES) == len(set(PUBLIC_API_NAMES)),
        "PUBLIC_API_NAMES must not contain duplicates",
    )
    _assert(
        tuple(PROVIDER_COMPAT_LAZY_EXPORT_MODULES) == PROVIDER_COMPAT_LAZY_EXPORTS,
        "lazy provider name order must match its module map",
    )

    flattened = tuple(
        name
        for group in PUBLIC_API_GROUPS.values()
        for name in group
    )
    _assert(flattened == PUBLIC_API_NAMES, "public API groups must flatten exactly")
    _assert(
        len(PUBLIC_API_NAMES) == 114,
        "v6 typed event payload extension should expose 114 canonical names",
    )
    _assert(
        tuple(IDENTITY_PUBLIC_EXPORTS)
        == ("SessionId", "TurnId", "GenerationId", "EventSequence"),
        "identity public export group drift",
    )
    _assert(
        PUBLIC_API_NAMES[95:99] == tuple(IDENTITY_PUBLIC_EXPORTS),
        "identity names must preserve their appended position",
    )
    _assert(
        tuple(LIFECYCLE_PUBLIC_EXPORTS)
        == (
            "RealtimePhase",
            "TurnOutcome",
            "RecoveryAction",
            "LifecycleTransitionErrorCode",
            "LifecycleTransitionError",
        ),
        "lifecycle public export group drift",
    )
    _assert(
        PUBLIC_API_NAMES[99:104] == tuple(LIFECYCLE_PUBLIC_EXPORTS),
        "lifecycle names must preserve their accepted appended position",
    )
    _assert(
        tuple(REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS)
        == (
            "RealtimeEventPayloadKind",
            "LifecycleEventPayload",
            "TranscriptEventPayload",
            "ResponseEventPayload",
            "SynthesisEventPayload",
            "AudioEventPayload",
            "MotionEventPayload",
            "InterruptEventPayload",
            "DiagnosticEventPayload",
            "RealtimeEventPayload",
        ),
        "typed event payload public export group drift",
    )
    _assert(
        PUBLIC_API_NAMES[104:] == tuple(REALTIME_EVENT_PAYLOAD_PUBLIC_EXPORTS),
        "typed event payload names must be appended after the accepted 104-name surface",
    )

    lazy_names = set(PROVIDER_COMPAT_LAZY_EXPORTS)
    missing_eager = sorted(
        name
        for name in PUBLIC_API_NAMES
        if name not in lazy_names and name not in framework.__dict__
    )
    _assert(not missing_eager, f"missing eager public bindings: {missing_eager}")

    eager_lazy = sorted(name for name in lazy_names if name in framework.__dict__)
    _assert(
        not eager_lazy,
        f"provider compatibility exports were imported eagerly: {eager_lazy}",
    )

    imported_forbidden = sorted(
        name for name in FORBIDDEN_AFTER_ROOT_IMPORT if name in sys.modules
    )
    _assert(
        not imported_forbidden,
        f"root import loaded forbidden provider/runtime modules: {imported_forbidden}",
    )

    print("[OK] canonical manifest preserves the 104-name prefix and appends typed event payload models")


def _check_init_source_has_one_manifest_assignment() -> None:
    init_path = PROJECT_ROOT / "framework" / "__init__.py"
    tree = ast.parse(init_path.read_text(encoding="utf-8"))

    assignments = []
    mutating_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    assignments.append(node)
        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "__all__":
                assignments.append(node)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if (
                isinstance(owner, ast.Name)
                and owner.id == "__all__"
                and node.func.attr in {"append", "extend", "insert"}
            ):
                mutating_calls.append(node.func.attr)

    _assert(len(assignments) == 1, "framework.__init__ must assign __all__ exactly once")
    assignment = assignments[0]
    _assert(
        isinstance(assignment.value, ast.Call)
        and isinstance(assignment.value.func, ast.Name)
        and assignment.value.func.id == "list"
        and len(assignment.value.args) == 1
        and isinstance(assignment.value.args[0], ast.Name)
        and assignment.value.args[0].id == "PUBLIC_API_NAMES",
        "framework.__all__ must be built only as list(PUBLIC_API_NAMES)",
    )
    _assert(
        not mutating_calls,
        f"framework.__all__ must not be incrementally mutated: {mutating_calls}",
    )

    public_api_path = PROJECT_ROOT / "framework" / "public_api.py"
    public_api_tree = ast.parse(public_api_path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(public_api_tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from_roots = {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(public_api_tree)
        if isinstance(node, ast.ImportFrom)
    }
    allowed = {"__future__", "types"}
    unexpected = sorted((imported_roots | imported_from_roots) - allowed)
    _assert(
        not unexpected,
        f"public_api.py must remain names-only and import-safe: {unexpected}",
    )

    print("[OK] framework.__all__ has one canonical, non-mutating source")


def _check_lazy_names_resolve_without_provider_sdk_import() -> None:
    code = r"""
import sys
import framework
from framework.public_api import PROVIDER_COMPAT_LAZY_EXPORTS

for name in PROVIDER_COMPAT_LAZY_EXPORTS:
    value = getattr(framework, name)
    if value is None:
        raise AssertionError(f"{name} resolved to None")

forbidden = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "tts.voice_engine",
    "live2d.vts_client",
}
loaded = sorted(name for name in forbidden if name in sys.modules)
if loaded:
    raise AssertionError(f"lazy compatibility resolution imported SDK/runtime modules: {loaded}")
print("lazy-resolution-pass")
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _assert(
        completed.returncode == 0,
        "lazy provider compatibility resolution failed:\n"
        + completed.stdout
        + completed.stderr,
    )
    _assert(
        "lazy-resolution-pass" in completed.stdout,
        "lazy resolution subprocess did not finish its assertions",
    )
    print("[OK] provider compatibility exports resolve lazily without provider SDK import")


def _check_docs_and_status_markers() -> None:
    required_markers = {
        PROJECT_ROOT / "docs" / "public_facade.md": (
            "<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:BEGIN -->",
            "<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:END -->",
            "<!-- FW-RT6-1a-A-PUBLIC-IDENTITY:BEGIN -->",
            "<!-- FW-RT6-1a-A-PUBLIC-IDENTITY:END -->",
            "<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:BEGIN -->",
            "<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:END -->",
            "<!-- FW-RT6-1c-A-TYPED-PAYLOADS:BEGIN -->",
            "<!-- FW-RT6-1c-A-TYPED-PAYLOADS:END -->",
        ),
        PROJECT_ROOT / "docs" / "app_integration_contract.md": (
            "<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:BEGIN -->",
            "<!-- FW-RT6-0b-A-PUBLIC-API-MANIFEST:END -->",
            "<!-- FW-RT6-1a-A-PUBLIC-IDENTITY:BEGIN -->",
            "<!-- FW-RT6-1a-A-PUBLIC-IDENTITY:END -->",
            "<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:BEGIN -->",
            "<!-- FW-RT6-1b-A-LIFECYCLE-MODELS:END -->",
            "<!-- FW-RT6-1c-A-TYPED-PAYLOADS:BEGIN -->",
            "<!-- FW-RT6-1c-A-TYPED-PAYLOADS:END -->",
        ),
    }
    for path, markers in required_markers.items():
        text = path.read_text(encoding="utf-8")
        for marker in markers:
            _assert(marker in text, f"missing marker in {path.name}: {marker}")

    print("[OK] public facade and app integration docs record Control A")


def main() -> None:
    _check_manifest_shape()
    _check_init_source_has_one_manifest_assignment()
    _check_lazy_names_resolve_without_provider_sdk_import()
    _check_docs_and_status_markers()

    print("v600_public_api_manifest_status: implemented-awaiting-review")
    print("v600_public_api_manifest_name_count: 114")
    print("v600_framework_all_single_source: True")
    print("v600_provider_compatibility_exports_preserved: True")
    print("v600_provider_compatibility_exports_lazy: True")
    print("v600_provider_sdk_imported: False")
    print("v600_runtime_imported: False")
    print("v600_network_execution: False")
    print("v600_provider_execution: False")
    print("v600_next_control: FW-RT6-1c Control B")
    print("v600_next_control_authorized: False")
    print("[OK] canonical public API manifest smoke passed with typed event payload models")


if __name__ == "__main__":
    main()
