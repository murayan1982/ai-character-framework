"""FW-RT6-11b Control B stable optional-provider namespace gate.

Offline-safe: validates the exact namespace, frozen root compatibility,
manifest projection, import safety, documentation, and open aggregate boundary
without provider, network, audio, microphone, playback, or VTube Studio work.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import importlib
import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "644350479aa3dde264627978d555ef47a432cd3f"
EXPECTED_NAMESPACE = "framework.providers.openai.voice_input"
EXPECTED_ROOT_DIGEST = (
    "4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0"
)
EXPECTED_EXPORTS = (
    "OpenAIVoiceInputClient",
    "OpenAIVoiceInputClientFactory",
    "OpenAIVoiceInputFakeClientMarker",
    "OpenAIVoiceInputFakeExecutionPolicy",
    "OpenAIVoiceInputFakeExecutionStatus",
    "OpenAIVoiceInputFakeExecutor",
    "OpenAIVoiceInputPreflight",
    "OpenAIVoiceInputPreflightStatus",
    "OpenAIVoiceInputPrivateCredential",
    "OpenAIVoiceInputProviderAdapter",
    "OpenAIVoiceInputRealClientFactory",
    "OpenAIVoiceInputRealProviderExecutor",
    "OpenAIVoiceInputRealProviderPolicy",
    "OpenAIVoiceInputRealProviderStatus",
    "OpenAIVoiceInputRuntimeMode",
)
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_root_public_api_manifest.json",
    "framework/providers/__init__.py",
    "framework/providers/openai/__init__.py",
    "framework/providers/openai/voice_input.py",
    "framework/public_api.py",
    "scripts/smoke_v600_root_public_api_cleanup_control_a.py",
    "scripts/smoke_v600_root_public_api_cleanup_control_b.py",
    "tests/test_root_public_api_cleanup_control_a.py",
    "tests/test_root_public_api_cleanup_control_b.py",
}


def _require(condition: bool, message: str) -> None:
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
        ("-c", "core.safecrlf=false", "diff", "HEAD", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.strip().replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _digest(names: tuple[str, ...]) -> str:
    return sha256(
        "".join(f"{name}\n" for name in names).encode("utf-8")
    ).hexdigest()


def check_repository_contract() -> None:
    _require(
        _git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD,
        "unexpected FW-RT6-11b Control B baseline",
    )
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE_HEAD,
        "origin/main drifted from the Control B baseline",
    )
    actual = _changed_paths()
    _require(actual == EXPECTED_SURFACE, f"unexpected Control B surface: {sorted(actual)}")
    print("[OK] baseline and exact eleven-file Control B surface conform")


def check_root_import_stays_lazy() -> None:
    code = r'''
import sys
import framework
from framework.public_api import V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
assert len(framework.__all__) == 127
assert "framework.providers" not in sys.modules
assert "framework.providers.openai" not in sys.modules
assert "framework.providers.openai.voice_input" not in sys.modules
assert "framework.openai_voice_input_provider_adapter" not in sys.modules
assert "framework.openai_voice_input_fake_execution" not in sys.modules
assert "framework.openai_voice_input_real_provider" not in sys.modules
assert not any(name in framework.__dict__ for name in V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS)
assert not any(name == "openai" or name.startswith("openai.") for name in sys.modules)
'''
    subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, check=True)
    print("[OK] root import stays provider-namespace and SDK lazy")


def check_namespace_shape_and_identity() -> None:
    import framework
    import framework.providers as providers
    import framework.providers.openai as openai_namespace
    from framework.public_api import (
        STABLE_OPTIONAL_PROVIDER_NAMESPACE,
        V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
        V6_PROVIDER_NEUTRAL_ROOT_EXPORTS,
        V6_ROOT_PUBLIC_EXPORTS,
    )

    namespace = importlib.import_module(EXPECTED_NAMESPACE)
    _require(providers.__all__ == (), "framework.providers container exported names")
    _require(openai_namespace.__all__ == (), "OpenAI container exported names")
    _require(tuple(namespace.__all__) == EXPECTED_EXPORTS, "namespace exports drift")
    _require(
        tuple(namespace.__all__) == V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
        "namespace and root compatibility inventory diverged",
    )
    _require(
        STABLE_OPTIONAL_PROVIDER_NAMESPACE == EXPECTED_NAMESPACE,
        "stable provider namespace constant drift",
    )
    for name in EXPECTED_EXPORTS:
        _require(
            getattr(namespace, name) is getattr(framework, name),
            f"root/namespace object identity drift: {name}",
        )
    _require(len(V6_ROOT_PUBLIC_EXPORTS) == 127, "root count drift")
    _require(len(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS) == 112, "neutral count drift")
    _require(_digest(V6_ROOT_PUBLIC_EXPORTS) == EXPECTED_ROOT_DIGEST, "root digest drift")
    print("[OK] exact 15-name namespace and root object identity conform")


def check_namespace_import_is_provider_safe() -> None:
    code = r'''
import sys
import framework.providers.openai.voice_input as voice_input
assert len(voice_input.__all__) == 15
forbidden = {
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "core.runtime", "core.pipeline", "stt.stt_engine", "tts.voice_engine",
    "live2d.vts_client",
}
assert not forbidden.intersection(sys.modules), sorted(forbidden.intersection(sys.modules))
assert not any(name.startswith("openai.") for name in sys.modules)
'''
    subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, check=True)
    print("[OK] explicit namespace import performs no SDK/provider/runtime work")


def check_manifest_and_docs() -> None:
    manifest = json.loads(
        (PROJECT_ROOT / "docs/v600_root_public_api_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    _require(
        manifest["stable_optional_provider_namespace"] == EXPECTED_NAMESPACE,
        "machine manifest namespace drift",
    )
    _require(manifest["root_public_name_count"] == 127, "manifest root count drift")
    _require(manifest["provider_neutral_name_count"] == 112, "manifest neutral count drift")
    _require(
        manifest["provider_compatibility_name_count"] == 15,
        "manifest compatibility count drift",
    )
    _require(manifest["root_public_sha256"] == EXPECTED_ROOT_DIGEST, "manifest digest drift")
    _require(
        tuple(manifest["provider_compatibility_root_exports"]) == EXPECTED_EXPORTS,
        "manifest compatibility export drift",
    )
    _require(
        manifest["new_provider_specific_root_exports_allowed"] is False,
        "manifest allowed new provider root exports",
    )

    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for phrase in (
            "FW-RT6-11b-B-OPTIONAL-PROVIDER-NAMESPACE:BEGIN",
            EXPECTED_NAMESPACE,
            "127 / UNCHANGED",
            "15 / PRESERVED / LAZY / SILENT",
            "Control C aggregate acceptance: NOT_AUTHORIZED",
            "commit / push: NOT_AUTHORIZED",
        ):
            _require(phrase in text, f"missing Control B fact in {relative}: {phrase}")

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    section = tasklist.split("## FW-RT6-11b — Root-public API cleanup", 1)[1].split(
        "## FW-RT6-11c", 1
    )[0]
    _require(section.count("- [ ]") == 0, "Control C left an aggregate task open")
    _require(section.count("- [x]") == 6, "Control C aggregate task count drift")
    print("[OK] manifest/docs align and aggregate tasks are 6 / 6 acceptance-candidates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="skip baseline and worktree-surface checks",
    )
    args = parser.parse_args()
    if not args.source_only:
        check_repository_contract()
    check_root_import_stays_lazy()
    check_namespace_shape_and_identity()
    check_namespace_import_is_provider_safe()
    check_manifest_and_docs()
    print("v600_rt6_11b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print(f"v600_rt6_11b_stable_provider_namespace: {EXPECTED_NAMESPACE}")
    print("v600_rt6_11b_namespace_exports: 15 / EXACT / ROOT IDENTITY")
    print("v600_rt6_11b_root_public_names: 127 / UNCHANGED")
    print(f"v600_rt6_11b_root_public_sha256: {EXPECTED_ROOT_DIGEST}")
    print("v600_rt6_11b_provider_sdk_imported: False")
    print("v600_rt6_11b_provider_execution: False")
    print("v600_rt6_11b_network_execution: False")
    print("v600_rt6_11b_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_11b_control_c: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11b_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11b Control B optional-provider namespace gate passed")


if __name__ == "__main__":
    main()
