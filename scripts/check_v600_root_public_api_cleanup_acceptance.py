"""FW-RT6-11b Control C aggregate root-public cleanup acceptance gate.

The gate is offline-safe. It validates the accepted Control A/B contracts,
the exact root and optional-provider namespace inventories, task-boundary-only
semantic synchronization, and wheel membership without provider, network,
audio, microphone, playback, or real VTube Studio execution.
"""

from __future__ import annotations

import argparse
from fnmatch import fnmatchcase
from hashlib import sha256
import importlib
import json
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "727d999fd012731088fd3261c6e5b0e4bb161e94"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_root_public_api_cleanup_acceptance.py",
    "scripts/smoke_v600_root_public_api_cleanup_control_a.py",
    "scripts/smoke_v600_root_public_api_cleanup_control_b.py",
    "tests/test_root_public_api_cleanup_control_a.py",
    "tests/test_root_public_api_cleanup_control_b.py",
}
EXPECTED_TASKS = (
    "v6 root-public inventoryを固定する。",
    "provider-specific classesのroot exportを再評価する。",
    "stable optional provider namespaceを設ける場合はdocumentする。",
    "wildcard export ordering依存をなくす。",
    "exact public API manifestを生成する。",
    "docs/examples/`__all__`の差分gateを追加する。",
)
EXPECTED_NAMESPACE = "framework.providers.openai.voice_input"
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
ROOT_DIGEST = "4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0"
NEUTRAL_DIGEST = "c75717d89860716610c539d0ba6411259b3b9dd77349fd7b8c17bcdf2bdb2c3e"
COMPATIBILITY_DIGEST = (
    "4f8dd7bc622270fd5f4cbdae80d656cf21c6aed2604b5e73f465f51e457fa996"
)
FORBIDDEN_RUNTIME_MODULES = (
    "openai",
    "elevenlabs",
    "pyvts",
    "pyaudio",
    "sounddevice",
    "websocket",
    "websockets",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str], *, capture: bool = True) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=capture,
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


def _changed_paths() -> set[str]:
    paths = _git(
        "-c",
        "core.safecrlf=false",
        "diff",
        "HEAD",
        "--name-only",
    ).splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def _digest(names: tuple[str, ...]) -> str:
    return sha256(
        "".join(f"{name}\n" for name in names).encode("utf-8")
    ).hexdigest()


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact seven-file FW-RT6-11b Control C surface conform")


def check_accepted_history_and_focused_gates() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    for marker in (
        "FW-RT6-11b-A-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-11b-A-ACCEPTANCE-SYNC:END",
        "FW-RT6-11b-B-ACCEPTANCE-SYNC:BEGIN",
        "FW-RT6-11b-B-ACCEPTANCE-SYNC:END",
    ):
        _require(tasklist.count(marker) == 1, f"accepted sync marker drift: {marker}")
    for phrase in (
        "Control A implementation: ffaaa167aae595d315995ce307f44b24ac1ef37c",
        "Control A acceptance sync: 644350479aa3dde264627978d555ef47a432cd3f",
        "Control B implementation: 6cdb08ac35f2c7f4baa0b8b2a61d8e78a33b0c02",
        "Control B acceptance sync: 727d999fd012731088fd3261c6e5b0e4bb161e94",
        "Control B: COMPLETED / VERIFIED / ACCEPTED / COMMITTED / PUSHED / REMOTELY_VERIFIED / CLOSED",
    ):
        _require(phrase in tasklist, f"accepted Control A/B fact missing: {phrase}")

    control_a_test = (
        PROJECT_ROOT / "tests/test_root_public_api_cleanup_control_a.py"
    ).read_text(encoding="utf-8")
    control_b_test = (
        PROJECT_ROOT / "tests/test_root_public_api_cleanup_control_b.py"
    ).read_text(encoding="utf-8")
    _require(control_a_test.count("    def test_") == 12, "Control A test count drift")
    _require(control_b_test.count("    def test_") == 12, "Control B test count drift")
    for source, label in (
        (control_a_test, "Control A"),
        (control_b_test, "Control B"),
    ):
        _require(
            "test_control_c_closes_only_the_aggregate_task_boundary" in source,
            f"{label} Control C task-boundary sync missing",
        )

    _run(
        [sys.executable, "scripts/smoke_v600_root_public_api_cleanup_control_a.py"],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "scripts/smoke_v600_root_public_api_cleanup_control_b.py",
            "--source-only",
        ],
        capture=False,
    )
    _run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_root_public_api_cleanup_control_a",
            "tests.test_root_public_api_cleanup_control_b",
        ],
        capture=False,
    )
    print("[OK] accepted Control A/B history and 24 focused tests conform")
    print("[OK] four gate/test files receive Control C boundary-only semantic sync")


def check_root_manifest_and_namespace() -> None:
    import framework
    import framework.providers as provider_container
    import framework.providers.openai as openai_container
    from framework.public_api import (
        PUBLIC_API_NAMES,
        ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION,
        ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT,
        STABLE_OPTIONAL_PROVIDER_NAMESPACE,
        V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
        V6_PROVIDER_NEUTRAL_ROOT_EXPORTS,
        V6_ROOT_PUBLIC_EXPORTS,
    )

    namespace = importlib.import_module(EXPECTED_NAMESPACE)
    _require(tuple(framework.__all__) == PUBLIC_API_NAMES, "wildcard order drift")
    _require(V6_ROOT_PUBLIC_EXPORTS == tuple(sorted(PUBLIC_API_NAMES)), "sorted root drift")
    _require(len(V6_ROOT_PUBLIC_EXPORTS) == 127, "root-public count drift")
    _require(len(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS) == 112, "neutral count drift")
    _require(len(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS) == 15, "compatibility count drift")
    _require(_digest(V6_ROOT_PUBLIC_EXPORTS) == ROOT_DIGEST, "root digest drift")
    _require(_digest(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS) == NEUTRAL_DIGEST, "neutral digest drift")
    _require(
        _digest(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS) == COMPATIBILITY_DIGEST,
        "compatibility digest drift",
    )
    _require(ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT == "non_contractual", "order contract drift")
    _require(STABLE_OPTIONAL_PROVIDER_NAMESPACE == EXPECTED_NAMESPACE, "namespace constant drift")
    _require(provider_container.__all__ == (), "provider container exported objects")
    _require(openai_container.__all__ == (), "OpenAI container exported objects")
    _require(tuple(namespace.__all__) == EXPECTED_EXPORTS, "namespace exports drift")
    _require(
        tuple(namespace.__all__) == V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
        "namespace/root compatibility inventory drift",
    )
    for name in EXPECTED_EXPORTS:
        _require(
            getattr(namespace, name) is getattr(framework, name),
            f"namespace/root identity drift: {name}",
        )

    manifest = json.loads(
        (PROJECT_ROOT / "docs/v600_root_public_api_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    expected_manifest = {
        "schema_version": ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION,
        "generated_from": "framework.public_api.PUBLIC_API_NAMES",
        "root_wildcard_ordering_contract": ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT,
        "stable_optional_provider_namespace": STABLE_OPTIONAL_PROVIDER_NAMESPACE,
        "new_provider_specific_root_exports_allowed": False,
        "root_public_name_count": 127,
        "provider_neutral_name_count": 112,
        "provider_compatibility_name_count": 15,
        "root_public_sha256": ROOT_DIGEST,
        "provider_neutral_sha256": NEUTRAL_DIGEST,
        "provider_compatibility_sha256": COMPATIBILITY_DIGEST,
        "root_public_exports": list(V6_ROOT_PUBLIC_EXPORTS),
        "provider_neutral_root_exports": list(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS),
        "provider_compatibility_root_exports": list(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS),
    }
    _require(manifest == expected_manifest, "machine-readable manifest drift")

    root_probe = r'''
import sys
import framework
assert len(framework.__all__) == 127
assert "framework.providers" not in sys.modules
assert "framework.providers.openai.voice_input" not in sys.modules
assert not any(name == "openai" or name.startswith("openai.") for name in sys.modules)
'''
    namespace_probe = r'''
import sys
import framework.providers.openai.voice_input as voice_input
assert len(voice_input.__all__) == 15
forbidden = {"openai", "elevenlabs", "pyvts", "pyaudio", "sounddevice", "websocket", "websockets"}
assert not forbidden.intersection(sys.modules)
assert not any(name.startswith("openai.") for name in sys.modules)
'''
    _run([sys.executable, "-c", root_probe])
    _run([sys.executable, "-c", namespace_probe])
    for module_name in FORBIDDEN_RUNTIME_MODULES:
        _require(module_name not in sys.modules, f"runtime module escaped: {module_name}")
    print("[OK] canonical 127-name manifest and three fixed digests conform")
    print("[OK] stable 15-name namespace, root identity, and import safety conform")


def check_docs_tasks_and_unchanged_boundaries() -> None:
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    app_contract = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(
        encoding="utf-8"
    )
    for marker in (
        "FW-RT6-11b-C-ROOT-PUBLIC-ACCEPTANCE:BEGIN",
        "FW-RT6-11b-C-ROOT-PUBLIC-ACCEPTANCE:END",
    ):
        _require(facade.count(marker) == 1, f"public contract marker drift: {marker}")
    for marker in (
        "FW-RT6-11b-C-AGGREGATE-ACCEPTANCE:BEGIN",
        "FW-RT6-11b-C-AGGREGATE-ACCEPTANCE:END",
    ):
        _require(tasklist.count(marker) == 1, f"tasklist marker drift: {marker}")

    aggregate_text = facade.split(
        "<!-- FW-RT6-11b-C-ROOT-PUBLIC-ACCEPTANCE:BEGIN -->", 1
    )[1].split(
        "<!-- FW-RT6-11b-C-ROOT-PUBLIC-ACCEPTANCE:END -->", 1
    )[0] + tasklist.split(
        "<!-- FW-RT6-11b-C-AGGREGATE-ACCEPTANCE:BEGIN -->", 1
    )[1].split(
        "<!-- FW-RT6-11b-C-AGGREGATE-ACCEPTANCE:END -->", 1
    )[0]
    for phrase in (
        "exact corrective Control C surface: 7 files",
        "Control A/B gate/test semantic sync: 4 files / CONTROL_C BOUNDARY ONLY",
        "runtime source changed by Control C: False",
        "machine-readable manifest changed by Control C: False",
        "application-integration contract changed by Control C: False",
        "framework root-public names: 127 / UNCHANGED / PASS",
        "stable optional provider namespace: framework.providers.openai.voice_input / PASS",
        "docs/example/export drift: PASS",
        "offline wheel provider-namespace membership: PASS",
        "FW-RT6-11b tasks: 6 / 6 ACCEPTED-CANDIDATE",
        "FW-RT6-11b final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-11c migration guide and examples: NOT_AUTHORIZED",
        "Control C commit / push: NOT_AUTHORIZED",
    ):
        _require(phrase in aggregate_text, f"aggregate phrase missing: {phrase}")

    section = tasklist.split("## FW-RT6-11b — Root-public API cleanup", 1)[1].split(
        "## FW-RT6-11c", 1
    )[0]
    _require(section.count("- [x]") == 6, "accepted-candidate count drift")
    _require(section.count("- [ ]") == 0, "FW-RT6-11b task remains open")
    for task in EXPECTED_TASKS:
        _require(task in section, f"FW-RT6-11b task missing: {task}")

    _require("FW-RT6-11b-B-OPTIONAL-PROVIDER-NAMESPACE:BEGIN" in app_contract, "accepted app contract missing")
    _require("FW-RT6-11b-C-" not in app_contract, "Control C changed app integration contract")
    for unchanged in (
        "framework/public_api.py",
        "docs/v600_root_public_api_manifest.json",
        "framework/providers/__init__.py",
        "framework/providers/openai/__init__.py",
        "framework/providers/openai/voice_input.py",
        "docs/app_integration_contract.md",
    ):
        _require(unchanged not in EXPECTED_SURFACE, f"unchanged boundary escaped: {unchanged}")
    print("[OK] six FW-RT6-11b tasks are aggregate acceptance-candidates")
    print("[OK] runtime, manifest, namespace, and application boundaries stay unchanged")


def check_accepted_regression_gates() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [
            sys.executable,
            "scripts/check_v600_session_compatibility_acceptance.py",
            "--source-only",
        ],
        [sys.executable, "scripts/smoke_v530_lazy_provider_adapter_fake.py"],
        [sys.executable, "scripts/smoke_v540_openai_adapter_client_injection_contract.py"],
        [sys.executable, "scripts/smoke_v540_openai_fake_execution_boundary.py"],
        [sys.executable, "scripts/smoke_v540_openai_real_provider_runtime.py"],
    ):
        _run(command, capture=False)
    print("[OK] accepted manifest, compatibility, and v5.3/v5.4 gates conform")


def check_offline_wheel_membership() -> None:
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    _require(
        'build-backend = "setuptools.build_meta"' in pyproject,
        "wheel build backend drift",
    )
    _require(
        "[tool.setuptools.packages.find]" in pyproject,
        "setuptools package discovery contract missing",
    )
    package_section = pyproject.split("[tool.setuptools.packages.find]", 1)[1].split(
        "[tool.setuptools.package-data]", 1
    )[0]
    _require('where = ["."]' in package_section, "package discovery root drift")
    _require('"framework*"' in package_section, "framework package include drift")
    _require("namespaces = false" in package_section, "namespace package policy drift")

    include_patterns = ("framework*",)
    discovered = {
        ".".join(path.parent.relative_to(PROJECT_ROOT).parts)
        for path in PROJECT_ROOT.rglob("__init__.py")
        if path.parent != PROJECT_ROOT
    }
    selected = {
        package
        for package in discovered
        if any(fnmatchcase(package, pattern) for pattern in include_patterns)
    }
    for package in (
        "framework",
        "framework.providers",
        "framework.providers.openai",
    ):
        _require(package in selected, f"provider wheel package not discovered: {package}")
    for member in (
        "framework/providers/__init__.py",
        "framework/providers/openai/__init__.py",
        "framework/providers/openai/voice_input.py",
    ):
        _require(
            (PROJECT_ROOT / member).is_file(),
            f"provider wheel member missing from source: {member}",
        )
    _require(
        not (PROJECT_ROOT / "framework/providers.py").exists(),
        "flat providers module conflicts with package discovery",
    )
    print(
        "[OK] offline setuptools wheel discovery includes the complete "
        "stable provider namespace"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_exact_surface()
    check_accepted_history_and_focused_gates()
    check_root_manifest_and_namespace()
    check_docs_tasks_and_unchanged_boundaries()
    check_accepted_regression_gates()
    check_offline_wheel_membership()

    print("v600_rt6_11b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_11b_control_c_status: IMPLEMENTED / AWAITING_REVIEW")
    print("v600_rt6_11b_control_c_exact_surface: 7 files / CORRECTIVE")
    print("v600_rt6_11b_runtime_changed_by_control_c: False")
    print("v600_rt6_11b_manifest_changed_by_control_c: False")
    print("v600_rt6_11b_root_public_names: 127 / UNCHANGED")
    print(f"v600_rt6_11b_root_public_sha256: {ROOT_DIGEST}")
    print(f"v600_rt6_11b_stable_provider_namespace: {EXPECTED_NAMESPACE}")
    print("v600_rt6_11b_namespace_exports: 15 / EXACT / ROOT IDENTITY")
    print("v600_rt6_11b_existing_gate_test_sync: 4 files / CONTROL_C BOUNDARY ONLY")
    print("v600_rt6_11b_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_11b_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_11c: NOT_AUTHORIZED")
    print("v600_rt6_11b_control_c_commit_push: NOT_AUTHORIZED")
    print("[OK] FW-RT6-11b Control C aggregate root-public cleanup gate passed")


if __name__ == "__main__":
    main()
