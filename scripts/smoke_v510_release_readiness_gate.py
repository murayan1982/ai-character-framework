from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class ContractFailure(AssertionError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def _assert_doc(root: Path) -> None:
    path = root / "docs" / "v510_release_readiness_gate.md"
    _require(path.exists(), "v5.1.0 release readiness gate doc is missing")
    text = path.read_text(encoding="utf-8", errors="replace")
    phrases = [
        "v5.1.0 release readiness gate",
        "mock-safe pre-release checkpoint",
        "must not call real provider APIs",
        "must not generate real voice artifacts",
        "must not create release archives or tags",
        "Package import readiness",
        "Passing this gate means",
    ]
    for phrase in phrases:
        _require(phrase in text, f"release readiness gate doc missing phrase: {phrase}")
    print("[OK] v5.1.0 release readiness gate doc is documented")


def _run(root: Path, args: list[str]) -> None:
    display = " ".join(args)
    print(f"[RUN] {display}")
    completed = subprocess.run(
        args,
        cwd=str(root),
        env={
            **os.environ,
            "PYTHONNOUSERSITE": "1",
        },
        text=True,
        capture_output=True,
        check=False,
    )

    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip())

    _require(completed.returncode == 0, f"command failed: {display}")


def _assert_required_files(root: Path) -> None:
    required = [
        "docs/v510_public_contract_inventory.md",
        "docs/v510_voice_output_method_contract.md",
        "docs/v510_public_factory_signature_contract.md",
        "docs/v510_result_error_contract.md",
        "docs/v510_capability_snapshot_contract.md",
        "docs/v510_provider_config_ownership.md",
        "docs/v510_session_lifecycle_contract.md",
        "docs/v510_opaque_voice_artifact_contract.md",
        "docs/v510_public_contract_conformance_gate.md",
        "docs/v510_package_import_readiness.md",
        "scripts/smoke_v510_public_contract_inventory.py",
        "scripts/smoke_v510_voice_output_method_contract.py",
        "scripts/smoke_v510_factory_signature_contract.py",
        "scripts/smoke_v510_result_error_contract.py",
        "scripts/smoke_v510_text_chat_result_public_type.py",
        "scripts/smoke_v510_text_chat_result_runtime_method.py",
        "scripts/smoke_v510_capability_snapshot.py",
        "scripts/smoke_v510_provider_config_ownership.py",
        "scripts/smoke_v510_session_lifecycle.py",
        "scripts/smoke_v510_opaque_voice_artifact_contract.py",
        "scripts/smoke_v510_public_contract_conformance_gate.py",
        "scripts/smoke_v510_package_import_readiness.py",
        "scripts/check_release_package.py",
    ]
    missing = [item for item in required if not (root / item).exists()]
    _require(not missing, "release readiness required files are missing: " + ", ".join(missing))
    print("[OK] v5.1.0 release readiness required files are present")


def _run_release_readiness_commands(root: Path) -> None:
    commands = [
        [sys.executable, "-m", "compileall", "-q", "."],
        [sys.executable, "scripts/smoke_v510_public_contract_inventory.py"],
        [sys.executable, "scripts/smoke_v510_voice_output_method_contract.py"],
        [sys.executable, "scripts/smoke_v510_factory_signature_contract.py"],
        [sys.executable, "scripts/smoke_v510_result_error_contract.py"],
        [sys.executable, "scripts/smoke_v510_text_chat_result_public_type.py"],
        [sys.executable, "scripts/smoke_v510_text_chat_result_runtime_method.py"],
        [sys.executable, "scripts/smoke_v510_capability_snapshot.py"],
        [sys.executable, "scripts/smoke_v510_provider_config_ownership.py"],
        [sys.executable, "scripts/smoke_v510_session_lifecycle.py"],
        [sys.executable, "scripts/smoke_v510_opaque_voice_artifact_contract.py"],
        [sys.executable, "scripts/smoke_v510_public_contract_conformance_gate.py"],
        [sys.executable, "scripts/smoke_v510_package_import_readiness.py"],
        [sys.executable, "scripts/check_release_package.py"],
    ]
    for command in commands:
        _run(root, command)
    print("[OK] v5.1.0 release readiness command set passed")


def main() -> None:
    root = _repo_root()
    _assert_doc(root)
    _assert_required_files(root)
    _run_release_readiness_commands(root)
    print("[OK] v5.1.0 release readiness gate is mock-safe")


if __name__ == "__main__":
    main()
