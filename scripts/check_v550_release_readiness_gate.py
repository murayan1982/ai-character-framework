"""FW-VTS-0f3 exact six-file release-readiness checker."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "a1c39369bd35b21196b25a93a82798f47f1dad30"

EXACT_SURFACE = {
    "README.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "docs/v550_release_readiness_gate.md",
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/check_v550_release_readiness_gate.py",
}

FROZEN_PATHS = {
    ".env.example",
    ".gitignore",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_session.py",
    "framework/motion_adapter_execution.py",
    "framework/vtube_studio_transport.py",
    "framework/vtube_studio_pyvts_transport.py",
    "framework/vtube_studio_motion_composition.py",
    "live2d/vts_client.py",
    "requirements.txt",
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
    "scripts/check_v550_vtube_studio_operator_acceptance.py",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/check_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/check_v550_vtube_studio_constructor_corrective.py",
    "scripts/build_v510_fixed_release_package.py",
    "scripts/build_v520_release_package.py",
    "scripts/build_v530_release_package.py",
    "scripts/build_v540_release_package.py",
}

FROZEN_PREFIXES = (
    "core/",
    "plugins/",
    "presets/",
    "characters/",
    "config/",
    "release/",
)

DOC_PATHS = (
    "README.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "docs/v550_release_readiness_gate.md",
)

SMOKE_PATH = "scripts/smoke_v550_release_readiness_gate.py"

GENERATED_TTS_INVENTORY = (
    "utils/available_tts_models.txt",
    "utils/available_voices.txt",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _run(
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


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
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run(
        "git",
        "rev-parse",
        "origin/main",
    ).stdout.strip()
    branch = _run(
        "git",
        "branch",
        "--show-current",
    ).stdout.strip()

    _require(
        head == EXPECTED_HEAD,
        f"FW-VTS-0f3 requires HEAD {EXPECTED_HEAD}, found {head}",
    )
    _require(
        origin_main == EXPECTED_HEAD,
        "origin/main does not match the FW-VTS-0f3 baseline",
    )
    _require(branch == "main", f"expected main branch, found: {branch}")

    origin = _run(
        "git",
        "remote",
        "get-url",
        "origin",
    ).stdout.strip()
    _require(
        "ai-character-framework" in origin.casefold(),
        "origin is not AI Character Framework",
    )

    changed = _changed_paths()
    _require(
        changed == EXACT_SURFACE,
        "FW-VTS-0f3 exact surface mismatch: "
        f"expected={sorted(EXACT_SURFACE)} actual={sorted(changed)}",
    )

    frozen_hits = sorted(
        path
        for path in changed
        if path in FROZEN_PATHS
        or any(path.startswith(prefix) for prefix in FROZEN_PREFIXES)
    )
    _require(
        not frozen_hits,
        "frozen runtime/operator/package surface changed: "
        + ", ".join(frozen_hits),
    )
    _ok("FW-VTS-0f3 baseline and exact six-file surface match")


def _validate_generated_files_absent() -> None:
    tracked = _git_lines("ls-files")
    for relative in GENERATED_TTS_INVENTORY:
        _require(
            relative not in tracked,
            f"generated TTS inventory is tracked: {relative}",
        )
        _require(
            not (ROOT / relative).exists(),
            f"generated TTS inventory exists: {relative}",
        )
    _ok("generated TTS inventory files remain outside repo")


def _validate_docs() -> None:
    for relative in DOC_PATHS:
        source = _read(relative)
        for marker in (
            "FW-VTS-0f3-RELEASE-READINESS:BEGIN",
            "checkpoint: FW-VTS-0f3",
            f"baseline head: {EXPECTED_HEAD}",
            "FW-VTS-0f2: ACCEPTED / PUSHED",
            "required four intents: ACCEPTED",
            "stop_motion_supported: False",
            "stop_motion_verified: False",
            "private real-motion evidence: ACCEPTED_BY_PUBLIC_SYNC",
            "release package created: False",
            "v5.5.0 tag created: False",
            "release package authorization: READY_FOR_FW-VTS-0f4_AFTER_REVIEW",
            "commit / push: NOT_AUTHORIZED",
            "FW-VTS-0f3-RELEASE-READINESS:END",
        ):
            _require(
                marker in source,
                f"{relative} missing readiness marker: {marker}",
            )
    _ok("FW-VTS-0f3 public readiness documentation is complete")


def _validate_smoke_source() -> None:
    source = _read(SMOKE_PATH)
    tree = ast.parse(source, filename=SMOKE_PATH)

    import_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            import_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.level == 0
        ):
            import_roots.add(node.module.split(".", 1)[0])

    forbidden_imports = {
        "pyvts",
        "websocket",
        "websockets",
        "live2d",
    }
    _require(
        not (import_roots & forbidden_imports),
        "release-readiness gate imports provider/VTS runtime modules",
    )

    for forbidden in (
        "LOCALAPPDATA",
        "APPDATA",
        "bootstrap_evidence.json).read",
        "real_motion_operator_evidence.json).read",
        "vts_private_config.json).read",
        "build_v550_release_package",
        "git tag v5.5.0",
        "git push",
    ):
        _require(
            forbidden not in source,
            f"release-readiness smoke contains forbidden action: {forbidden}",
        )
    _ok("FW-VTS-0f3 smoke remains source-only and provider-safe")


def _run_validation() -> None:
    compile_result = _run(
        sys.executable,
        "-m",
        "compileall",
        "-q",
        "framework",
        "scripts",
        "examples",
        check=False,
    )
    _require(
        compile_result.returncode == 0,
        "compileall failed",
    )

    smoke = _run(
        sys.executable,
        SMOKE_PATH,
        check=False,
    )
    _require(
        smoke.returncode == 0,
        "FW-VTS-0f3 release-readiness smoke failed",
    )

    for marker in (
        "v550_release_readiness_gate_status: accepted",
        "v550_fw_vts_0f2_status: accepted",
        "v550_private_real_motion_evidence_status: accepted-by-public-sync",
        "v550_framework_root_import_provider_safe: True",
        "v550_private_vts_artifact_tracked: False",
        "v550_actual_pyvts_imported_in_gate: False",
        "v550_websocket_imported_in_gate: False",
        "v550_network_execution_in_gate: False",
        "v550_private_token_read_in_gate: False",
        "v550_private_evidence_read_in_gate: False",
        "v550_real_motion_execution_in_gate: False",
        "v550_release_package_created: False",
        "v550_tag_created: False",
        "v550_release_package_authorization: ready-for-FW-VTS-0f4",
        "[OK] FW-VTS-0f3 v5.5.0 release-readiness gate passed",
    ):
        _require(
            marker in smoke.stdout,
            f"release-readiness smoke marker missing: {marker}",
        )
    _ok("compileall and FW-VTS-0f3 release-readiness smoke pass")


def main() -> None:
    _validate_repository()
    _validate_generated_files_absent()
    _validate_docs()
    _validate_smoke_source()
    _run_validation()

    print("v550_release_readiness_exact_contract_check: PASS")
    print("v550_exact_change_surface: True")
    print("v550_exact_change_file_count: 6")
    print(f"v550_expected_head: {EXPECTED_HEAD}")
    print("v550_document_change_count: 4")
    print("v550_runtime_changed: False")
    print("v550_operator_changed: False")
    print("v550_private_verifier_changed: False")
    print("v550_package_builder_changed: False")
    print("v550_release_artifact_changed: False")
    print("v550_private_vts_artifact_tracked: False")
    print("v550_actual_pyvts_imported_during_gate: False")
    print("v550_network_execution_during_gate: False")
    print("v550_real_motion_execution_during_gate: False")
    print("v550_private_evidence_read_during_gate: False")
    print("v550_release_package_created: False")
    print("v550_tag_created: False")
    print("v550_commit_authorized: False")
    print("v550_push_authorized: False")
    print("v550_next_authorization: review-and-commit-FW-VTS-0f3")
    print("[OK] FW-VTS-0f3 exact readiness checker passed")


if __name__ == "__main__":
    main()
