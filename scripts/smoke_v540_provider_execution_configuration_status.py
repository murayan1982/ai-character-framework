"""Validate accepted v5.4.0 REQ-1 provider execution configuration/status."""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CHANGED_PATHS = {
    "README.md",
    "docs/v540_provider_execution_configuration_status.md",
    "docs/v540_real_stt_provider_execution_requirements.md",
    "docs/v540_real_stt_provider_execution_small_commit_checklist.md",
    "framework/__init__.py",
    "framework/voice_input_provider_execution.py",
    "scripts/smoke_v540_provider_execution_configuration_status.py",
}
LOCAL_ONLY_PATHS = {".vscode/settings.json"}
FORBIDDEN_PROVIDER_MODULE_FRAGMENTS = (
    "speech_recognition",
    "pyaudio",
    "sounddevice",
    "whisper",
    "faster_whisper",
    "openai",
    "google.cloud",
    "boto3",
    "azure",
)


def _read(relative: str) -> str:
    path = ROOT / relative
    if not path.is_file():
        raise AssertionError(f"Missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="replace")


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _git_lines(*args: str) -> set[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }


def _changed_paths() -> set[str]:
    tracked = _git_lines("diff", "--name-only")
    staged = _git_lines("diff", "--cached", "--name-only")
    untracked = _git_lines("ls-files", "--others", "--exclude-standard")
    return (tracked | staged | untracked) - LOCAL_ONLY_PATHS


def _validate_changed_surface() -> None:
    actual = _changed_paths()
    _require(
        actual == EXPECTED_CHANGED_PATHS,
        "REQ-1 changed surface mismatch:\n"
        f"expected={sorted(EXPECTED_CHANGED_PATHS)}\n"
        f"actual={sorted(actual)}",
    )
    _ok("REQ-1 worktree contains the exact seven-file accepted surface")


def _validate_docs() -> None:
    readme = _read("README.md")
    requirements = _read("docs/v540_real_stt_provider_execution_requirements.md")
    checklist = _read(
        "docs/v540_real_stt_provider_execution_small_commit_checklist.md"
    )
    contract = _read("docs/v540_provider_execution_configuration_status.md")

    combined = "\n".join((readme, requirements, checklist, contract))
    for marker in (
        "REQ-1: ACCEPTED",
        "VoiceInputProviderExecutionConfig",
        "resolve_voice_input_provider_execution_config",
        "get_voice_input_provider_execution_status",
        "explicit_arguments_only",
        "credential availability",
        "provider_execution_not_allowed",
        "provider_not_configured",
        "credentials_unavailable",
        "provider_execution_not_implemented",
        "REQ-2: READY pending next small commit",
    ):
        _require(marker in combined, f"REQ-1 docs missing marker: {marker}")

    for forbidden in (
        "REQ-1: IMPLEMENTED / NOT_ACCEPTED",
        "REQ-2: BLOCKED pending REQ-1 acceptance",
        "real provider execution succeeded",
        "private provider acceptance completed",
    ):
        _require(
            forbidden not in combined,
            f"REQ-1 docs contain stale or premature marker: {forbidden}",
        )

    _ok(
        "REQ-1 docs record acceptance and authorize REQ-2 "
        "for the next small commit"
    )


def _validate_source_boundary() -> None:
    source = _read("framework/voice_input_provider_execution.py")
    tree = ast.parse(source)

    imported_roots: set[str] = set()
    calls: list[str] = []
    arguments: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".")[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments.update(arg.arg for arg in node.args.args)
            arguments.update(arg.arg for arg in node.args.kwonlyargs)

    _require(
        "os" not in imported_roots,
        "REQ-1 module must not inspect process environment",
    )
    _require(
        "pathlib" not in imported_roots,
        "REQ-1 module must not inspect files",
    )
    _require(
        not imported_roots.intersection(
            {
                "openai",
                "google",
                "boto3",
                "azure",
                "whisper",
                "speech_recognition",
            }
        ),
        "REQ-1 module must not import provider SDKs",
    )
    _require(
        not set(calls).intersection(
            {
                "getenv",
                "open",
                "read_text",
                "read_bytes",
                "transcribe",
                "recognize",
                "create_client",
            }
        ),
        "REQ-1 module must not read environment/files or execute providers",
    )
    _require(
        not arguments.intersection(
            {
                "api_key",
                "credential",
                "credential_value",
                "audio",
                "audio_bytes",
                "audio_path",
                "client",
                "client_factory",
            }
        ),
        "REQ-1 public functions must not accept secrets, audio, or clients",
    )
    _ok(
        "REQ-1 source is explicit-only, provider-safe, "
        "credential-value-free, and audio-free"
    )


def _validate_runtime_contract() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    hits = sorted(
        name
        for name in loaded
        if any(
            fragment in name.lower()
            for fragment in FORBIDDEN_PROVIDER_MODULE_FRAGMENTS
        )
    )
    _require(
        not hits,
        f"framework import loaded provider/runtime modules: {hits}",
    )

    exports = (
        "VoiceInputProviderExecutionConfig",
        "resolve_voice_input_provider_execution_config",
        "get_voice_input_provider_execution_status",
    )
    for name in exports:
        _require(
            hasattr(framework, name),
            f"framework missing REQ-1 export: {name}",
        )
        _require(
            name in framework.__all__,
            f"framework.__all__ missing REQ-1 export: {name}",
        )

    default_config = (
        framework.resolve_voice_input_provider_execution_config()
    )
    _require(default_config.provider is None, "default provider must be unset")
    _require(
        default_config.allow_provider_execution is False,
        "default opt-in must be false",
    )
    _require(
        default_config.credentials_available is False,
        "default credential availability must be false",
    )
    _require(
        default_config.to_public_dict()["credential_values_read"] is False,
        "public config must report no credential-value read",
    )

    blocked = framework.get_voice_input_provider_execution_status(
        default_config
    )
    _require(blocked.status == "blocked", "default status must be blocked")
    _require(blocked.blocked is True, "default status must carry blocked=True")
    _require(
        blocked.reason_code == "provider_execution_not_allowed",
        "default reason mismatch",
    )

    no_provider = framework.get_voice_input_provider_execution_status(
        framework.resolve_voice_input_provider_execution_config(
            allow_provider_execution=True,
        )
    )
    _require(
        no_provider.reason_code == "provider_not_configured",
        "missing-provider reason mismatch",
    )

    no_credentials = framework.get_voice_input_provider_execution_status(
        framework.resolve_voice_input_provider_execution_config(
            provider=" Example_STT ",
            allow_provider_execution=True,
        )
    )
    _require(
        no_credentials.reason_code == "credentials_unavailable",
        "credential-availability reason mismatch",
    )
    _require(
        no_credentials.public_metadata["credentials_available"] == "false",
        "credential availability metadata mismatch",
    )

    configured = framework.get_voice_input_provider_execution_status(
        framework.resolve_voice_input_provider_execution_config(
            provider=" Example_STT ",
            allow_provider_execution=True,
            credentials_available=True,
        )
    )
    _require(
        configured.status == "configured",
        "fully declared config must report configured",
    )
    _require(
        configured.configured is True,
        "fully declared config must carry configured=True",
    )
    _require(
        configured.available is False,
        "REQ-1 must not report provider execution available",
    )
    _require(
        configured.reason_code == "provider_execution_not_implemented",
        "configured reason mismatch",
    )
    _require(
        configured.public_metadata["provider_execution_executed"] == "false",
        "REQ-1 must report no provider execution",
    )
    _require(
        configured.public_metadata["audio_read"] == "false",
        "REQ-1 must report no audio read",
    )
    _require(
        configured.public_metadata["microphone_accessed"] == "false",
        "REQ-1 must report no microphone access",
    )
    _require(
        configured.public_metadata["credential_values_read"] == "false",
        "REQ-1 must report no credential-value read",
    )

    _require(
        hasattr(framework, "resolve_voice_input_provider_config"),
        "v5.2 resolver export changed",
    )
    _require(
        hasattr(framework, "get_voice_input_capabilities"),
        "v5.2 capability export changed",
    )

    _ok(
        "REQ-1 public status matrix is typed, conservative, "
        "and execution-free"
    )


def main() -> None:
    _validate_changed_surface()
    _validate_docs()
    _validate_source_boundary()
    _validate_runtime_contract()

    print("v540_provider_execution_configuration_status: accepted")
    print("v540_provider_execution_config_public_export_present: True")
    print("v540_provider_execution_capability_status_present: True")
    print("v540_provider_execution_default_opt_in: False")
    print("v540_provider_setting_explicit_only: True")
    print("v540_credential_availability_boolean_only: True")
    print("v540_credential_values_read: False")
    print("v540_provider_sdk_imported: False")
    print("v540_provider_client_created: False")
    print("v540_provider_execution_executed: False")
    print("v540_audio_read: False")
    print("v540_microphone_accessed: False")
    print("v540_drc_repo_changed: False")
    print("v540_req2_authorization: ready-for-req2")
    _ok(
        "v5.4.0 REQ-1 provider execution configuration/status "
        "acceptance passed"
    )


if __name__ == "__main__":
    main()
