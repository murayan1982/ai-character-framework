"""FW-VTS-0f4a deterministic v5.5.0 package-gate smoke."""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "a83f7efe85d489887b1d97122b2756e2a1b57ff5"

PACKAGE_GATE_SURFACE = {
    "README.md",
    "docs/v550_release_readiness_gate.md",
    "docs/v550_release_package_gate.md",
    "scripts/build_v550_release_package.py",
    "scripts/smoke_v550_release_package_gate.py",
    "scripts/check_v550_release_package_gate.py",
    "scripts/smoke_v550_release_readiness_gate.py",
}

DEPENDENCIES = (
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/check_release_package.py",
)

REQUIRED_ZIP_ENTRIES = {
    "README.md",
    ".env.example",
    "requirements.txt",
    "framework/__init__.py",
    "framework/motion.py",
    "framework/motion_adapter_execution.py",
    "framework/motion_session.py",
    "framework/vtube_studio_transport.py",
    "framework/vtube_studio_pyvts_transport.py",
    "framework/vtube_studio_motion_composition.py",
    "docs/v550_motion_adapter_configuration_status.md",
    "docs/v550_vtube_studio_transport_protocol_fake.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_release_readiness_gate.md",
    "docs/v550_release_package_gate.md",
    "scripts/operator_v550_vtube_studio_token_bootstrap.py",
    "scripts/operator_v550_vtube_studio_real_motion_acceptance.py",
    "scripts/verify_v550_vtube_studio_private_evidence.py",
    "scripts/smoke_v550_vtube_studio_transport_protocol_fake.py",
    "scripts/smoke_v550_vtube_studio_pyvts_transport.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/smoke_v550_release_package_gate.py",
    "scripts/check_v550_release_package_gate.py",
    "scripts/build_v550_release_package.py",
}

BEGIN_MARKER = "<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:BEGIN -->"
END_MARKER = "<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:END -->"

FORBIDDEN_MODULES = ("pyvts", "websocket", "websockets", "live2d.vts_client")


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _run(
    *args: str,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        env=env,
        check=check,
        capture_output=True,
        text=True,
    )


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


def _load_builder():
    path = ROOT / "scripts" / "build_v550_release_package.py"
    spec = importlib.util.spec_from_file_location(
        "build_v550_release_package",
        path,
    )
    _require(
        spec is not None and spec.loader is not None,
        "could not load v5.5.0 package builder",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _safe_environment() -> dict[str, str]:
    env = dict(os.environ)
    for name in (
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "XAI_API_KEY",
        "ELEVENLABS_API_KEY",
        "FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION",
        "FRAMEWORK_MOTION_REAL_ADAPTER",
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
        "FRAMEWORK_VOICE_INPUT_ALLOW_PROVIDER_EXECUTION",
        "FW_REQ5_AUDIO_PATH",
    ):
        env.pop(name, None)
    env["FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION"] = "0"
    env["FRAMEWORK_MOTION_REAL_ADAPTER"] = "0"
    env["FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION"] = "0"
    env["FRAMEWORK_VOICE_INPUT_ALLOW_PROVIDER_EXECUTION"] = "0"
    return env


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    completed = _run(
        "git",
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        check=False,
    )
    return completed.returncode == 0


def _validate_repository() -> tuple[set[str], str]:
    head = _run("git", "rev-parse", "HEAD").stdout.strip()
    origin_main = _run("git", "rev-parse", "origin/main").stdout.strip()
    branch = _run("git", "branch", "--show-current").stdout.strip()

    _require(branch == "main", f"expected main branch, found: {branch}")

    origin = _run("git", "remote", "get-url", "origin").stdout.strip()
    _require(
        "ai-character-framework" in origin.casefold(),
        "origin is not AI Character Framework",
    )
    _require(
        _is_ancestor(EXPECTED_HEAD, head),
        "FW-VTS-0f4a baseline is not an ancestor of HEAD",
    )
    _require(
        _is_ancestor(EXPECTED_HEAD, origin_main),
        "FW-VTS-0f4a baseline is not an ancestor of origin/main",
    )

    changed = _changed_paths()
    if changed:
        _require(
            head == EXPECTED_HEAD,
            "dirty package-gate mode requires the exact FW-VTS-0f3c1 HEAD",
        )
        _require(
            origin_main == EXPECTED_HEAD,
            "dirty package-gate mode requires origin/main at FW-VTS-0f3c1",
        )
        _require(
            changed == PACKAGE_GATE_SURFACE,
            "FW-VTS-0f4a exact worktree surface mismatch: "
            f"expected={sorted(PACKAGE_GATE_SURFACE)} actual={sorted(changed)}",
        )
        _ok("FW-VTS-0f4a exact seven-file worktree is present")
        return changed, "package-gate-worktree"

    _require(
        head == origin_main,
        "clean package-gate mode requires HEAD and origin/main to match",
    )
    _ok("clean committed package-gate descendant is present")
    return set(), "clean-committed"


def _validate_docs() -> None:
    for relative in (
        "README.md",
        "docs/v550_release_readiness_gate.md",
        "docs/v550_release_package_gate.md",
    ):
        source = (ROOT / relative).read_text(
            encoding="utf-8",
            errors="strict",
        )
        _require(
            source.count(BEGIN_MARKER) == 1,
            f"package-gate begin marker must appear once in {relative}",
        )
        _require(
            source.count(END_MARKER) == 1,
            f"package-gate end marker must appear once in {relative}",
        )
        for marker in (
            "checkpoint: FW-VTS-0f4a",
            f"baseline head: {EXPECTED_HEAD}",
            "package version: 5.5.0",
            "tracked private VTS artifact rejection: REQUIRED",
            "final release ZIP created: False",
            "v5.5.0 tag created: False",
            "next authorization: READY_FOR_FW-VTS-0f4b_AFTER_REVIEW",
        ):
            _require(
                marker in source,
                f"package-gate documentation missing {marker} in {relative}",
            )
    _ok("FW-VTS-0f4a package-gate documentation is present")


def _validate_private_rejection_contract(builder) -> None:
    synthetic = {
        "config/tokens/plugin_token.json",
        "nested/private_token.json",
        "vts_private_config.json",
        "bootstrap_evidence.json",
        "real_motion_operator_evidence.json",
        "operator_evidence/run.json",
    }
    hits = set(builder.private_tracked_hits(synthetic))
    _require(
        hits == synthetic,
        "builder private tracked-path rejection contract is incomplete",
    )

    _require(
        builder._is_included(".env.example"),
        "public .env.example template should remain package eligible",
    )
    for excluded in (
        ".env",
        ".env.local",
        "private/.env.production",
        ".vscode/settings.json",
        "release/ai-character-framework_v5.5.0.zip",
        "sample.wav",
        "__pycache__/module.pyc",
    ):
        _require(
            not builder._is_included(excluded),
            f"builder should exclude local/private/generated path: {excluded}",
        )
    _ok("tracked private VTS hard-rejection and exclusions are enforced")


def _archive_entries(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        bad = archive.testzip()
        _require(bad is None, f"ZIP integrity failure at: {bad}")
        names = archive.namelist()
    _require(len(names) == len(set(names)), "ZIP contains duplicate entries")
    return names


def _validate_temporary_builds(
    builder,
    package_files: list[str],
    changed: set[str],
    *,
    allow_final_package: bool,
) -> None:
    final_zip = ROOT / "release" / builder.PACKAGE_BASENAME
    final_sidecar = final_zip.with_suffix(final_zip.suffix + ".sha256")

    zip_before = final_zip.read_bytes() if final_zip.is_file() else None
    sidecar_before = (
        final_sidecar.read_bytes() if final_sidecar.is_file() else None
    )
    _require(
        (zip_before is None) == (sidecar_before is None),
        "final ZIP and sidecar presence must match",
    )

    if allow_final_package:
        _require(
            zip_before is not None and sidecar_before is not None,
            "--allow-final-package requires final ZIP and sidecar",
        )
    else:
        _require(
            zip_before is None and sidecar_before is None,
            "FW-VTS-0f4a requires absent final release artifacts",
        )

    with tempfile.TemporaryDirectory(
        prefix="acf_v550_package_gate_"
    ) as temporary:
        base = Path(temporary)
        first = base / "first" / builder.PACKAGE_BASENAME
        second = base / "second" / builder.PACKAGE_BASENAME

        digest1, count1 = builder.build_package(
            first,
            root=ROOT,
            additional_files=changed,
        )
        digest2, count2 = builder.build_package(
            second,
            root=ROOT,
            additional_files=changed,
        )

        first_sidecar = first.with_suffix(first.suffix + ".sha256")
        second_sidecar = second.with_suffix(second.suffix + ".sha256")
        _require(first_sidecar.is_file(), "first temporary sidecar is missing")
        _require(second_sidecar.is_file(), "second temporary sidecar is missing")

        _require(digest1 == digest2, "temporary ZIP SHA-256 values differ")
        _require(first.read_bytes() == second.read_bytes(), "temporary ZIP bytes differ")
        _require(
            first_sidecar.read_bytes() == second_sidecar.read_bytes(),
            "temporary SHA-256 sidecar bytes differ",
        )
        _require(count1 == len(package_files), "first ZIP file count mismatch")
        _require(count2 == len(package_files), "second ZIP file count mismatch")

        names1 = _archive_entries(first)
        names2 = _archive_entries(second)
        _require(names1 == names2, "temporary ZIP entry order differs")
        _require(names1 == package_files, "ZIP entries differ from exact package set")

        missing = sorted(REQUIRED_ZIP_ENTRIES - set(names1))
        _require(
            not missing,
            "temporary ZIP missing required v5.5.0 entries: " + ", ".join(missing),
        )

        private_hits = builder.private_tracked_hits(names1)
        _require(
            not private_hits,
            "temporary ZIP contains private VTS paths: " + ", ".join(private_hits),
        )
        _require(
            ".vscode/settings.json" not in names1,
            "temporary ZIP contains local VS Code settings",
        )
        _require(
            not any(name.startswith("release/") for name in names1),
            "temporary ZIP contains generated release artifacts",
        )
        _require(
            not any(name.casefold().endswith(".wav") for name in names1),
            "temporary ZIP contains WAV audio",
        )

    if zip_before is None:
        _require(
            not final_zip.exists() and not final_sidecar.exists(),
            "package gate created final release artifacts",
        )
    else:
        _require(
            final_zip.read_bytes() == zip_before,
            "package gate changed the allowed final ZIP",
        )
        _require(
            final_sidecar.read_bytes() == sidecar_before,
            "package gate changed the allowed final sidecar",
        )

    _ok("two deterministic temporary v5.5.0 package builds passed")
    _ok("final release artifact presence and bytes remained unchanged")


def _run_dependencies(*, allow_final_package: bool) -> None:
    env = _safe_environment()
    for dependency in DEPENDENCIES:
        extra = (
            ("--allow-final-package",)
            if allow_final_package
            and dependency == "scripts/smoke_v550_release_readiness_gate.py"
            else ()
        )
        completed = _run(
            sys.executable,
            dependency,
            *extra,
            env=env,
            check=False,
        )
        if completed.returncode != 0:
            if completed.stdout:
                print(completed.stdout)
            if completed.stderr:
                print(completed.stderr, file=sys.stderr)
            raise AssertionError(f"package-gate dependency failed: {dependency}")
        print(f"[OK] FW-VTS-0f4a dependency passed: {dependency}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run v5.5.0 deterministic release-package checks"
    )
    parser.add_argument(
        "--allow-final-package",
        action="store_true",
        help=(
            "Allow an existing final v5.5.0 ZIP and sidecar while requiring "
            "both to remain unchanged"
        ),
    )
    args = parser.parse_args(argv)

    for module_name in FORBIDDEN_MODULES:
        _require(
            module_name not in sys.modules,
            f"forbidden provider/VTS module loaded before package gate: {module_name}",
        )

    changed, worktree_mode = _validate_repository()
    _validate_docs()

    builder = _load_builder()
    for module_name in FORBIDDEN_MODULES:
        _require(
            module_name not in sys.modules,
            f"package builder loaded provider/VTS module: {module_name}",
        )

    _validate_private_rejection_contract(builder)
    files = builder.package_files(ROOT, additional_files=changed)
    _validate_temporary_builds(
        builder,
        files,
        changed,
        allow_final_package=args.allow_final_package,
    )
    _run_dependencies(allow_final_package=args.allow_final_package)

    for module_name in FORBIDDEN_MODULES:
        _require(
            module_name not in sys.modules,
            f"provider/VTS module loaded during package gate: {module_name}",
        )

    print("v550_release_package_gate_status: accepted")
    print(f"v550_release_package_gate_worktree_mode: {worktree_mode}")
    print("v550_release_package_dry_run_succeeded: True")
    print("v550_release_package_deterministic: True")
    print("v550_release_package_file_set_exact: True")
    print("v550_release_package_created_in_release_dir: False")
    print("v550_release_package_temporary_sha256_present: True")
    print("v550_release_package_rejects_config_tokens: True")
    print("v550_release_package_rejects_token_json: True")
    print("v550_release_package_rejects_private_config: True")
    print("v550_release_package_rejects_private_evidence: True")
    print("v550_release_package_excludes_vscode_settings: True")
    print("v550_release_package_excludes_env_files: True")
    print("v550_release_package_excludes_private_audio: True")
    print("v550_release_package_excludes_release_artifacts: True")
    print("v550_actual_pyvts_imported_in_package_gate: False")
    print("v550_websocket_connected_in_package_gate: False")
    print("v550_network_execution_in_package_gate: False")
    print("v550_private_token_read_in_package_gate: False")
    print("v550_private_evidence_read_in_package_gate: False")
    print("v550_real_motion_execution_in_package_gate: False")
    print("v550_drc_repo_changed: False")
    print("v550_tag_created: False")
    print("v550_push_performed: False")
    print("v550_next_authorization: ready-for-FW-VTS-0f4b")
    _ok("FW-VTS-0f4a deterministic release-package gate passed")


if __name__ == "__main__":
    main()
