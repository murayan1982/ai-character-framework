"""FW-VTS-0f3 v5.5.0 source-tree release-readiness gate."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = "a1c39369bd35b21196b25a93a82798f47f1dad30"
CORRECTIVE_BASELINE_HEAD = "4f643b7cfa4e77c71ba6a0a857ceb390beb7397e"
PACKAGE_GATE_BASELINE_HEAD = "a83f7efe85d489887b1d97122b2756e2a1b57ff5"
ACCEPTED_REAL_MOTION_HEAD = (
    "b7b9639dfa1f675ba04a33cd8ce297429f98fd15"
)
ACCEPTED_BOOTSTRAP_HEAD = (
    "1f737128554d701150427da4ce1c146759881255"
)

BEGIN_MARKER = "<!-- FW-VTS-0f3-RELEASE-READINESS:BEGIN -->"
END_MARKER = "<!-- FW-VTS-0f3-RELEASE-READINESS:END -->"

READINESS_DOCS = (
    "README.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
    "docs/v550_release_readiness_gate.md",
)

DEPENDENCIES = (
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_v550_vtube_studio_transport_protocol_fake.py",
    "scripts/smoke_v550_vtube_studio_pyvts_transport.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py",
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py",
    "scripts/check_release_package.py",
)

HISTORICAL_INCOMPATIBLE_DEPENDENCIES = (
    "scripts/smoke_public_facade.py",
    "scripts/smoke_v550_real_motion_adapter_readiness.py",
    "scripts/smoke_v550_motion_adapter_configuration_status.py",
)

CORRECTIVE_SURFACE = {
    "docs/v550_release_readiness_gate.md",
    "scripts/smoke_v550_release_readiness_gate.py",
    "scripts/check_v550_release_readiness_dependency_sync_corrective.py",
}

PACKAGE_GATE_SURFACE = {
    "README.md",
    "docs/v550_release_readiness_gate.md",
    "docs/v550_release_package_gate.md",
    "scripts/build_v550_release_package.py",
    "scripts/smoke_v550_release_package_gate.py",
    "scripts/check_v550_release_package_gate.py",
    "scripts/smoke_v550_release_readiness_gate.py",
}

DEPENDENCY_DOC_PATH = "docs/v550_release_readiness_gate.md"
DEPENDENCY_DOC_BEGIN = "<!-- FW-VTS-0f3c1-DEPENDENCY-SYNC:BEGIN -->"
DEPENDENCY_DOC_END = "<!-- FW-VTS-0f3c1-DEPENDENCY-SYNC:END -->"

EXPECTED_OUTPUT_MARKERS: Mapping[str, tuple[str, ...]] = {
    "scripts/smoke_v550_motion_session_real_adapter_composition.py": (
        "[OK] FW-VTS-0e MotionSession composition smoke passed",
        "v550_actual_pyvts_imported: False",
        "v550_network_executed: False",
        "v550_real_motion_executed: False",
    ),
    "scripts/smoke_v550_vtube_studio_operator_acceptance.py": (
        "v550_vtube_studio_optional_stop_corrective_smoke: PASS",
        "v550_required_four_intents: True",
        "v550_optional_stop_motion_contract: True",
        "v550_actual_pyvts_imported_in_smoke: False",
        "v550_websocket_connected_in_smoke: False",
        "v550_real_motion_executed_in_smoke: False",
    ),
    "scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py": (
        "v550_vtube_studio_real_motion_acceptance_sync_smoke: PASS",
        "v550_acceptance_sync_blocks_identical: True",
        "v550_private_values_recorded: False",
        "v550_actual_pyvts_imported_in_smoke: False",
        "v550_network_execution_in_smoke: False",
        "v550_real_motion_execution_in_smoke: False",
        "v550_private_evidence_read_in_smoke: False",
    ),
}

PUBLIC_MOTION_SYMBOLS = (
    "MotionAdapterStatus",
    "MotionCapability",
    "MotionErrorCode",
    "MotionEventType",
    "MotionIntent",
    "MotionOutcome",
    "MotionRequest",
    "MotionResult",
    "MotionState",
    "MotionSession",
    "MotionSessionInfo",
    "create_motion_session",
)

REQUIRED_BLOCK_MARKERS = (
    "checkpoint: FW-VTS-0f3",
    "status: IMPLEMENTED / AWAITING_REVIEW",
    f"baseline head: {BASELINE_HEAD}",
    f"accepted real-motion head: {ACCEPTED_REAL_MOTION_HEAD}",
    f"accepted bootstrap head: {ACCEPTED_BOOTSTRAP_HEAD}",
    "FW-VTS-0a: ACCEPTED / PUSHED",
    "FW-VTS-0b: ACCEPTED / PUSHED",
    "FW-VTS-0c: ACCEPTED / PUSHED",
    "FW-VTS-0d: ACCEPTED / PUSHED",
    "FW-VTS-0e: ACCEPTED / PUSHED",
    "FW-VTS-0f1: ACCEPTED / PUSHED",
    "FW-VTS-0f2: ACCEPTED / PUSHED",
    "required four intents: ACCEPTED",
    "stop_motion_supported: False",
    "stop_motion_verified: False",
    "optional stop_motion contract: ACCEPTED",
    "private real-motion evidence: ACCEPTED_BY_PUBLIC_SYNC",
    "release package created: False",
    "v5.5.0 tag created: False",
    "DRC repository changed: False",
    "release package authorization: READY_FOR_FW-VTS-0f4_AFTER_REVIEW",
    "commit / push: NOT_AUTHORIZED",
)

FORBIDDEN_TRACKED_PATH_RULES = (
    "config/tokens/",
    "operator_evidence/",
)

FORBIDDEN_TRACKED_BASENAMES = {
    "vts_private_config.json",
    "bootstrap_evidence.json",
    "real_motion_operator_evidence.json",
}

V550_PACKAGE = (
    ROOT / "release" / "ai-character-framework_v5.5.0.zip"
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


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


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing readiness source: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _extract_block(source: str, *, relative: str) -> str:
    _require(
        source.count(BEGIN_MARKER) == 1,
        f"{relative} must contain exactly one readiness begin marker",
    )
    _require(
        source.count(END_MARKER) == 1,
        f"{relative} must contain exactly one readiness end marker",
    )
    _, remainder = source.split(BEGIN_MARKER, 1)
    block, _ = remainder.split(END_MARKER, 1)
    return "\n".join(line.rstrip() for line in block.strip().splitlines())


def _safe_dependency_environment() -> dict[str, str]:
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


def _validate_repository_state() -> str:
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

    _require(
        _is_ancestor(CORRECTIVE_BASELINE_HEAD, head),
        "FW-VTS-0f3c1 corrective baseline is not an ancestor of HEAD",
    )
    _require(
        _is_ancestor(CORRECTIVE_BASELINE_HEAD, origin_main),
        "FW-VTS-0f3c1 corrective baseline is not an ancestor of origin/main",
    )

    changed = (
        _git_lines("diff", "--name-only")
        | _git_lines("diff", "--cached", "--name-only")
        | _git_lines("ls-files", "--others", "--exclude-standard")
    ) - {".vscode/settings.json"}

    if changed == CORRECTIVE_SURFACE:
        _require(
            head == CORRECTIVE_BASELINE_HEAD,
            "dirty corrective mode requires the exact FW-VTS-0f3 commit",
        )
        _require(
            origin_main == CORRECTIVE_BASELINE_HEAD,
            "dirty corrective mode requires origin/main at FW-VTS-0f3",
        )
        return "corrective-worktree"

    if changed == PACKAGE_GATE_SURFACE:
        _require(
            head == PACKAGE_GATE_BASELINE_HEAD,
            "package-gate mode requires the accepted FW-VTS-0f3c1 commit",
        )
        _require(
            origin_main == PACKAGE_GATE_BASELINE_HEAD,
            "package-gate mode requires origin/main at FW-VTS-0f3c1",
        )
        return "package-gate-worktree"

    _require(
        not changed,
        "readiness gate worktree contains unexpected paths: "
        + ", ".join(sorted(changed)),
    )
    return "clean-committed"


def _validate_docs() -> None:
    blocks = {
        relative: _extract_block(_read(relative), relative=relative)
        for relative in READINESS_DOCS
    }
    reference = blocks[READINESS_DOCS[0]]

    for relative, block in blocks.items():
        _require(
            block == reference,
            f"FW-VTS-0f3 readiness block differs in {relative}",
        )

    for marker in REQUIRED_BLOCK_MARKERS:
        _require(
            marker in reference,
            f"FW-VTS-0f3 readiness block missing marker: {marker}",
        )

    operator_doc = _read(
        "docs/v550_vtube_studio_operator_acceptance.md"
    )
    for marker in (
        "checkpoint: FW-VTS-0f2",
        f"accepted framework head: {ACCEPTED_REAL_MOTION_HEAD}",
        f"accepted bootstrap head: {ACCEPTED_BOOTSTRAP_HEAD}",
        "required four intents: VERIFIED",
        "stop_motion_supported: False",
        "stop_motion_verified: False",
        "private evidence: ACCEPTED_BY_VALIDATOR",
    ):
        _require(
            marker in operator_doc,
            f"accepted FW-VTS-0f2 marker missing: {marker}",
        )



def _validate_dependency_documentation() -> None:
    source = _read(DEPENDENCY_DOC_PATH)
    _require(
        source.count(DEPENDENCY_DOC_BEGIN) == 1,
        "dependency-sync begin marker must appear exactly once",
    )
    _require(
        source.count(DEPENDENCY_DOC_END) == 1,
        "dependency-sync end marker must appear exactly once",
    )

    _, remainder = source.split(DEPENDENCY_DOC_BEGIN, 1)
    section, _ = remainder.split(DEPENDENCY_DOC_END, 1)

    for relative in DEPENDENCIES:
        _require(
            relative in section,
            f"public dependency documentation missing: {relative}",
        )

    for relative in HISTORICAL_INCOMPATIBLE_DEPENDENCIES:
        _require(
            relative in section,
            f"historical exclusion is not documented: {relative}",
        )
        _require(
            relative not in DEPENDENCIES,
            f"historical dependency remains executable: {relative}",
        )

    for reason in (
        "pre-v5.2 exact",
        "pre-real-adapter",
        "earlier configuration checkpoint",
        "executable dependency tuple and this public list must remain identical",
    ):
        _require(
            reason in section,
            f"dependency-sync documentation missing rationale: {reason}",
        )


def _validate_private_artifacts_not_tracked() -> None:
    tracked = _git_lines("ls-files")
    hits: list[str] = []

    for relative in sorted(tracked):
        lower = relative.casefold()
        basename = Path(relative).name.casefold()
        if any(
            lower.startswith(prefix)
            or f"/{prefix}" in lower
            for prefix in FORBIDDEN_TRACKED_PATH_RULES
        ):
            hits.append(relative)
            continue
        if basename.endswith("_token.json"):
            hits.append(relative)
            continue
        if basename in FORBIDDEN_TRACKED_BASENAMES:
            hits.append(relative)

    _require(
        not hits,
        "private VTS artifact is tracked: " + ", ".join(hits),
    )


def _validate_public_import() -> None:
    for module_name in ("pyvts", "websocket", "websockets"):
        _require(
            module_name not in sys.modules,
            f"{module_name} loaded before Framework root import",
        )

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    import framework

    for module_name in ("pyvts", "websocket", "websockets"):
        _require(
            module_name not in sys.modules,
            f"Framework root import loaded {module_name}",
        )

    public = getattr(framework, "__all__", ())
    for name in PUBLIC_MOTION_SYMBOLS:
        _require(
            hasattr(framework, name),
            f"Framework root missing public motion symbol: {name}",
        )
        _require(
            name in public,
            f"framework.__all__ missing public motion symbol: {name}",
        )


def _validate_release_state(
    *,
    allow_final_package: bool,
) -> tuple[bytes | None, bytes | None]:
    v540_tag = _run(
        "git",
        "tag",
        "--list",
        "v5.4.0",
    ).stdout.strip()
    v550_tag = _run(
        "git",
        "tag",
        "--list",
        "v5.5.0",
    ).stdout.strip()

    _require(v540_tag == "v5.4.0", "accepted v5.4.0 tag is missing")
    _require(not v550_tag, "v5.5.0 tag already exists")

    sidecar = V550_PACKAGE.with_suffix(V550_PACKAGE.suffix + ".sha256")
    package_exists = V550_PACKAGE.is_file()
    sidecar_exists = sidecar.is_file()
    _require(
        package_exists == sidecar_exists,
        "v5.5.0 ZIP and SHA-256 sidecar presence must match",
    )

    if allow_final_package:
        _require(
            package_exists and sidecar_exists,
            "--allow-final-package requires the v5.5.0 ZIP and sidecar",
        )
        return V550_PACKAGE.read_bytes(), sidecar.read_bytes()

    _require(
        not package_exists,
        "v5.5.0 release package already exists",
    )
    _require(
        not sidecar_exists,
        "v5.5.0 release SHA-256 sidecar already exists",
    )
    return None, None


def _assert_release_artifacts_unchanged(
    before: tuple[bytes | None, bytes | None],
) -> None:
    package_before, sidecar_before = before
    sidecar = V550_PACKAGE.with_suffix(V550_PACKAGE.suffix + ".sha256")

    if package_before is None:
        _require(
            not V550_PACKAGE.exists() and not sidecar.exists(),
            "readiness gate created a final v5.5.0 release artifact",
        )
        return

    _require(
        V550_PACKAGE.is_file() and sidecar.is_file(),
        "readiness gate removed a final v5.5.0 release artifact",
    )
    _require(
        V550_PACKAGE.read_bytes() == package_before,
        "readiness gate changed the final v5.5.0 ZIP",
    )
    _require(
        sidecar.read_bytes() == sidecar_before,
        "readiness gate changed the final v5.5.0 SHA-256 sidecar",
    )


def _run_dependencies() -> None:
    env = _safe_dependency_environment()

    for relative in DEPENDENCIES:
        _require(
            (ROOT / relative).is_file(),
            f"missing readiness dependency: {relative}",
        )
        completed = _run(
            sys.executable,
            relative,
            env=env,
            check=False,
        )
        _require(
            completed.returncode == 0,
            f"readiness dependency failed: {relative}",
        )
        for marker in EXPECTED_OUTPUT_MARKERS.get(relative, ()):
            _require(
                marker in completed.stdout,
                f"readiness dependency marker missing: "
                f"{relative} / {marker}",
            )
        print(f"[OK] FW-VTS-0f3 dependency passed: {relative}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Run v5.5.0 source-tree release-readiness checks"
    )
    parser.add_argument(
        "--allow-final-package",
        action="store_true",
        help=(
            "Allow an existing final v5.5.0 ZIP and SHA-256 sidecar "
            "while requiring both to remain byte-for-byte unchanged"
        ),
    )
    args = parser.parse_args(argv)

    worktree_mode = _validate_repository_state()
    _validate_docs()
    _validate_dependency_documentation()
    _validate_private_artifacts_not_tracked()
    _validate_public_import()
    release_artifacts = _validate_release_state(
        allow_final_package=args.allow_final_package,
    )
    _run_dependencies()
    _assert_release_artifacts_unchanged(release_artifacts)

    print("v550_release_readiness_gate_status: accepted")
    print(
        "v550_release_readiness_final_package_allowed:",
        args.allow_final_package,
    )
    print("v550_release_readiness_final_artifacts_unchanged: True")
    print(f"v550_release_readiness_worktree_mode: {worktree_mode}")
    print("v550_release_readiness_dependency_count: 7")
    print("v550_release_readiness_dependency_docs_synced: True")
    print("v550_release_readiness_historical_exclusions_recorded: True")
    print("v550_release_readiness_obsolete_dependency_executed: False")
    print("v550_release_readiness_corrective_baseline_ancestor: True")
    print("v550_fw_vts_0a_status: accepted")
    print("v550_fw_vts_0b_status: accepted")
    print("v550_fw_vts_0c_status: accepted")
    print("v550_fw_vts_0d_status: accepted")
    print("v550_fw_vts_0e_status: accepted")
    print("v550_fw_vts_0f1_status: accepted")
    print("v550_fw_vts_0f2_status: accepted")
    print("v550_required_four_intents_status: accepted")
    print("v550_optional_stop_motion_contract_status: accepted")
    print(
        "v550_private_real_motion_evidence_status: "
        "accepted-by-public-sync"
    )
    print("v550_framework_root_import_provider_safe: True")
    print("v550_private_vts_artifact_tracked: False")
    print("v550_actual_pyvts_imported_in_gate: False")
    print("v550_websocket_imported_in_gate: False")
    print("v550_network_execution_in_gate: False")
    print("v550_private_token_read_in_gate: False")
    print("v550_private_evidence_read_in_gate: False")
    print("v550_real_motion_execution_in_gate: False")
    print("v550_release_package_created: False")
    print("v550_tag_created: False")
    print("v550_drc_repo_changed: False")
    print(
        "v550_release_package_authorization: "
        "ready-for-FW-VTS-0f4"
    )
    print("[OK] FW-VTS-0f3 v5.5.0 release-readiness gate passed")


if __name__ == "__main__":
    main()
