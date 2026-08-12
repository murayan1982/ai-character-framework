"""FW-RT6-11b Control A root-public inventory and drift gate.

Offline-safe: validates the canonical source, deterministic JSON projection,
provider-compatibility isolation, public examples, and contract documentation
without provider, network, audio, microphone, playback, or VTube Studio work.
"""

from __future__ import annotations

import ast
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MANIFEST_PATH = PROJECT_ROOT / "docs" / "v600_root_public_api_manifest.json"
CONTRACT_PATHS = (
    PROJECT_ROOT / "docs" / "public_facade.md",
    PROJECT_ROOT / "docs" / "app_integration_contract.md",
)
CONTROL_A_MARKERS = (
    "<!-- FW-RT6-11b-A-ROOT-PUBLIC-CLEANUP:BEGIN -->",
    "<!-- FW-RT6-11b-A-ROOT-PUBLIC-CLEANUP:END -->",
)
ROOT_PUBLIC_DIGEST = (
    "4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0"
)
PROVIDER_NEUTRAL_DIGEST = (
    "c75717d89860716610c539d0ba6411259b3b9dd77349fd7b8c17bcdf2bdb2c3e"
)
PROVIDER_COMPATIBILITY_DIGEST = (
    "4f8dd7bc622270fd5f4cbdae80d656cf21c6aed2604b5e73f465f51e457fa996"
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _digest(names: Iterable[str]) -> str:
    payload = "".join(f"{name}\n" for name in names).encode("utf-8")
    return sha256(payload).hexdigest()


def _manifest_from_source() -> dict[str, object]:
    from framework.public_api import (
        ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION,
        ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT,
        V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
        V6_PROVIDER_NEUTRAL_ROOT_EXPORTS,
        V6_ROOT_PUBLIC_EXPORTS,
    )

    return {
        "schema_version": ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION,
        "generated_from": "framework.public_api.PUBLIC_API_NAMES",
        "root_wildcard_ordering_contract": (
            ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT
        ),
        "stable_optional_provider_namespace": None,
        "new_provider_specific_root_exports_allowed": False,
        "root_public_name_count": len(V6_ROOT_PUBLIC_EXPORTS),
        "provider_neutral_name_count": len(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS),
        "provider_compatibility_name_count": len(
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
        ),
        "root_public_sha256": _digest(V6_ROOT_PUBLIC_EXPORTS),
        "provider_neutral_sha256": _digest(
            V6_PROVIDER_NEUTRAL_ROOT_EXPORTS
        ),
        "provider_compatibility_sha256": _digest(
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
        ),
        "root_public_exports": list(V6_ROOT_PUBLIC_EXPORTS),
        "provider_neutral_root_exports": list(
            V6_PROVIDER_NEUTRAL_ROOT_EXPORTS
        ),
        "provider_compatibility_root_exports": list(
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
        ),
    }


def check_canonical_source_and_root_surface() -> None:
    import framework
    from framework.public_api import (
        PROVIDER_COMPAT_LAZY_EXPORTS,
        PUBLIC_API_NAMES,
        ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION,
        ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT,
        V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS,
        V6_PROVIDER_NEUTRAL_ROOT_EXPORTS,
        V6_ROOT_PUBLIC_EXPORTS,
    )

    _require(
        tuple(framework.__all__) == PUBLIC_API_NAMES,
        "current wildcard order changed instead of being preserved",
    )
    _require(len(PUBLIC_API_NAMES) == 127, "root-public count drift")
    _require(
        len(PUBLIC_API_NAMES) == len(set(PUBLIC_API_NAMES)),
        "duplicate root-public name",
    )
    _require(
        V6_ROOT_PUBLIC_EXPORTS == tuple(sorted(PUBLIC_API_NAMES)),
        "v6 canonical root inventory is not sorted and order-independent",
    )
    _require(
        V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
        == tuple(sorted(PROVIDER_COMPAT_LAZY_EXPORTS)),
        "v5 provider compatibility classification drift",
    )
    _require(
        set(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS).isdisjoint(
            V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
        ),
        "provider-neutral and compatibility inventories overlap",
    )
    _require(
        set(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS)
        | set(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS)
        == set(V6_ROOT_PUBLIC_EXPORTS),
        "provider-neutral and compatibility inventories do not partition root",
    )
    _require(
        ROOT_PUBLIC_API_MANIFEST_SCHEMA_VERSION
        == "v6.root_public_api_manifest",
        "manifest schema drift",
    )
    _require(
        ROOT_PUBLIC_WILDCARD_ORDERING_CONTRACT == "non_contractual",
        "wildcard ordering contract drift",
    )
    _require(_digest(V6_ROOT_PUBLIC_EXPORTS) == ROOT_PUBLIC_DIGEST, "root digest drift")
    _require(
        _digest(V6_PROVIDER_NEUTRAL_ROOT_EXPORTS) == PROVIDER_NEUTRAL_DIGEST,
        "provider-neutral digest drift",
    )
    _require(
        _digest(V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS)
        == PROVIDER_COMPATIBILITY_DIGEST,
        "provider compatibility digest drift",
    )

    print("[OK] v6 root inventory is frozen as 127 unordered names")


def check_machine_readable_manifest() -> None:
    actual = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = _manifest_from_source()
    _require(actual == expected, "generated root-public JSON manifest drift")
    _require(actual["root_public_name_count"] == 127, "JSON root count drift")
    _require(
        actual["provider_neutral_name_count"] == 112,
        "JSON provider-neutral count drift",
    )
    _require(
        actual["provider_compatibility_name_count"] == 15,
        "JSON provider compatibility count drift",
    )
    _require(
        actual["stable_optional_provider_namespace"] is None,
        "Control A must not establish a provider namespace",
    )
    _require(
        actual["new_provider_specific_root_exports_allowed"] is False,
        "new provider-specific root exports must remain prohibited",
    )

    print("[OK] machine-readable manifest exactly matches its canonical source")


def check_provider_compatibility_is_lazy() -> None:
    code = r'''
import sys
import framework
from framework.public_api import V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS

eager = sorted(
    name for name in V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS
    if name in framework.__dict__
)
if eager:
    raise AssertionError(f"provider compatibility exports loaded eagerly: {eager}")
for name in V5_PROVIDER_COMPATIBILITY_ROOT_EXPORTS:
    if getattr(framework, name) is None:
        raise AssertionError(f"provider compatibility export resolved to None: {name}")
forbidden = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "core.runtime",
    "core.pipeline",
    "stt.stt_engine",
    "tts.voice_engine",
    "live2d.vts_client",
}
loaded = sorted(forbidden.intersection(sys.modules))
if loaded:
    raise AssertionError(f"provider/runtime modules loaded: {loaded}")
print("lazy-provider-compatibility-pass")
'''
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    _require(
        completed.returncode == 0,
        "lazy provider compatibility subprocess failed:\n"
        + completed.stdout
        + completed.stderr,
    )
    _require(
        "lazy-provider-compatibility-pass" in completed.stdout,
        "lazy provider compatibility subprocess did not complete",
    )
    _require(
        not (PROJECT_ROOT / "framework" / "providers.py").exists()
        and not (PROJECT_ROOT / "framework" / "providers").exists(),
        "Control A must not create an uncontracted provider namespace",
    )

    print("[OK] 15 v5 provider compatibility exports remain root-lazy and isolated")


def check_public_api_source_import_safety() -> None:
    path = PROJECT_ROOT / "framework" / "public_api.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from_roots = {
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    unexpected = sorted((imported_roots | imported_from_roots) - {"__future__", "types"})
    _require(
        not unexpected,
        f"canonical public manifest imported runtime/provider modules: {unexpected}",
    )

    print("[OK] canonical manifest source remains names-only and import-safe")


def check_examples_against_root_manifest() -> None:
    from framework.public_api import V6_ROOT_PUBLIC_EXPORTS

    public_names = set(V6_ROOT_PUBLIC_EXPORTS)
    missing: list[str] = []
    wildcard_imports: list[str] = []
    example_count = 0
    referenced_names: set[str] = set()

    for path in sorted((PROJECT_ROOT / "examples").glob("*.py")):
        example_count += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        root_aliases = {"framework"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "framework":
                        root_aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module == "framework":
                for alias in node.names:
                    if alias.name == "*":
                        wildcard_imports.append(str(path.relative_to(PROJECT_ROOT)))
                    else:
                        referenced_names.add(alias.name)
                        if alias.name not in public_names:
                            missing.append(f"{path.name}:{alias.name}")

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in root_aliases
                and not node.attr.startswith("__")
            ):
                referenced_names.add(node.attr)
                if node.attr not in public_names:
                    missing.append(f"{path.name}:{node.attr}")

    _require(example_count > 0, "public example inventory is empty")
    _require(not wildcard_imports, f"public examples use wildcard imports: {wildcard_imports}")
    _require(not missing, f"public examples reference names outside manifest: {missing}")
    _require(referenced_names, "public examples reference no root-public names")

    print("[OK] public examples have no wildcard or root-manifest drift")


def check_contract_docs() -> None:
    required_facts = (
        "v6.root_public_api_manifest",
        "docs/v600_root_public_api_manifest.json",
        "127",
        "112",
        "15",
        ROOT_PUBLIC_DIGEST,
        "stable optional provider namespace",
        "Control B: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    )
    for path in CONTRACT_PATHS:
        text = path.read_text(encoding="utf-8")
        for marker in CONTROL_A_MARKERS:
            _require(marker in text, f"missing Control A marker in {path.name}: {marker}")
        for fact in required_facts:
            _require(fact in text, f"missing manifest fact in {path.name}: {fact}")

    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(
        encoding="utf-8"
    )
    section = tasklist.split("## FW-RT6-11b — Root-public API cleanup", 1)[1].split(
        "## FW-RT6-11c", 1
    )[0]
    _require(section.count("- [ ]") == 6, "Control A must not close aggregate tasks")
    _require(section.count("- [x]") == 0, "Control A changed aggregate task state")

    print("[OK] docs/export facts align and aggregate task state remains 0 / 6")


def main() -> None:
    check_canonical_source_and_root_surface()
    check_machine_readable_manifest()
    check_provider_compatibility_is_lazy()
    check_public_api_source_import_safety()
    check_examples_against_root_manifest()
    check_contract_docs()
    print("v600_rt6_11b_control_a_status: implemented-awaiting-review")
    print("v600_rt6_11b_root_public_names: 127 / unchanged")
    print("v600_rt6_11b_provider_neutral_names: 112")
    print("v600_rt6_11b_provider_compatibility_names: 15 / preserved / lazy")
    print(f"v600_rt6_11b_root_public_sha256: {ROOT_PUBLIC_DIGEST}")
    print("v600_rt6_11b_wildcard_order_contract: non_contractual")
    print("v600_rt6_11b_stable_optional_provider_namespace: none")
    print("v600_rt6_11b_docs_example_export_drift: PASS")
    print("v600_rt6_11b_provider_execution: False")
    print("v600_rt6_11b_network_execution: False")
    print("v600_rt6_11b_control_b: NOT_AUTHORIZED")
    print("v600_rt6_11b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
