"""FW-RT6-2a Control B core consumer migration smoke."""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BASELINE = "b351cf74a5b20e55a4aede8746841c05a58bfbb9"
BASELINE_PARENT = "463496642f87daac1d280001d0385da1277a9f42"
BASELINE_SUBJECT = "feat/test: add recursive public safety primitives"
BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_safety_contract.md",
    "framework/public_safety.py",
    "scripts/smoke_v600_public_safety_primitives.py",
}
MIGRATION_FILES = {
    "framework/realtime.py",
    "framework/voice_input.py",
    "framework/motion.py",
    "framework/output_control.py",
    "framework/realtime_capabilities.py",
}
SURFACE = MIGRATION_FILES | {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_safety_contract.md",
    "scripts/smoke_v600_public_safety_consumer_migration.py",
}
FORBIDDEN = (
    "elevenlabs", "pyvts", "websocket", "pyaudio", "sounddevice",
    "speech_recognition", "google.genai", "xai_sdk",
)
SECRET = "nested-private-credential"
WIN = r"E:\private\credential.json"
POSIX = "/home/operator/private.env"


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def changed() -> set[str]:
    result: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        result.update(
            line.replace("\\", "/")
            for line in git(*args).splitlines() if line.strip()
        )
    return result


def commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in git(
            "diff-tree", "--no-commit-id", "--name-only", "-r", commit
        ).splitlines() if line.strip()
    }


def repository_contract() -> None:
    check(git("rev-parse", "HEAD") == BASELINE, "unexpected baseline")
    check(git("rev-parse", f"{BASELINE}^") == BASELINE_PARENT, "parent drift")
    check(git("show", "-s", "--format=%s", BASELINE) == BASELINE_SUBJECT, "subject drift")
    check(commit_surface(BASELINE) == BASELINE_SURFACE, "Control A surface drift")
    check(changed() == SURFACE, f"unexpected Control B surface: {sorted(changed())}")
    print("[OK] accepted Control A baseline and exact nine-file Control B surface conform")


def wrapper_contract() -> None:
    for relative in sorted(MIGRATION_FILES):
        tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
        imports = [
            alias for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module == "public_safety"
            for alias in node.names
            if alias.name == "public_mapping"
            and alias.asname == "_recursive_public_mapping"
        ]
        helpers = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_public_mapping"
        ]
        check(len(imports) == 1, f"central import drift: {relative}")
        check(len(helpers) == 1, f"helper count drift: {relative}")
        helper = helpers[0]
        param = helper.args.args[0].arg
        returns = [node for node in helper.body if isinstance(node, ast.Return)]
        check(len(returns) == 1, f"return drift: {relative}")
        call = returns[0].value
        check(isinstance(call, ast.Call), f"not delegating: {relative}")
        check(
            isinstance(call.func, ast.Name)
            and call.func.id == "_recursive_public_mapping",
            f"wrong delegate: {relative}",
        )
        check(
            len(call.args) == 1
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == param,
            f"argument drift: {relative}",
        )
    print("[OK] five private compatibility helpers delegate centrally")


def payload() -> dict[str, object]:
    return {
        "safe": "visible",
        "api-key": SECRET,
        "nested": [
            {"authorization": {"token": SECRET}, "path": WIN},
            {"safe_path": POSIX, "error": RuntimeError(f"{SECRET} {WIN}")},
        ],
    }


def assert_safe(value: object, label: str) -> None:
    check(isinstance(value, MappingProxyType), f"{label}: mutable mapping")
    text = repr(value)
    for forbidden in (SECRET, WIN, POSIX, "RuntimeError"):
        check(forbidden not in text, f"{label}: leaked {forbidden}")
    check(value["api-key"] == "<redacted>", f"{label}: secret marker drift")
    check(isinstance(value["nested"], tuple), f"{label}: list not immutable")


def consumer_contract() -> None:
    from framework.motion import MotionCapability
    from framework.output_control import _public_mapping as output_mapping
    from framework.realtime import _public_mapping as realtime_mapping
    from framework.realtime_capabilities import RuntimeCapabilityState
    from framework.realtime_session import RealtimeSessionInfo
    from framework.voice_input import VoiceInputRequest
    from framework.voice_input_capability import VoiceInputCapabilities

    assert_safe(realtime_mapping(payload()), "realtime helper")
    assert_safe(output_mapping(payload()), "output helper")
    assert_safe(RealtimeSessionInfo(public_metadata=payload()).public_metadata, "realtime info")
    assert_safe(VoiceInputRequest(metadata=payload()).metadata, "voice request")
    assert_safe(VoiceInputCapabilities(public_metadata=payload()).public_metadata, "voice capability")
    assert_safe(MotionCapability(public_metadata=payload()).public_metadata, "motion capability")
    state = RuntimeCapabilityState(
        configured=True, runtime_available=True, fake_runtime=True,
        unavailable_reason=None, public_metadata=payload(),
    )
    assert_safe(state.public_metadata, "runtime capability")
    print("[OK] migrated consumers recursively redact nested private material")


def compatibility_contract() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    check(tuple(framework.__all__) == PUBLIC_API_NAMES, "__all__ drift")
    check(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    check("public_mapping" not in PUBLIC_API_NAMES, "private helper leaked")

    facade = (ROOT / "framework" / "facade.py").read_text(encoding="utf-8")
    check('"error": str(exc)' in facade, "TextChat changed outside Control C")
    check('"error_type": type(exc).__name__' in facade, "TextChat type changed outside Control C")
    print("[OK] 121-name public surface and TextChat Control C deferral conform")


def docs_contract() -> None:
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        check("FW-RT6-2a-B-CORE-CONSUMER-MIGRATION:BEGIN" in text, f"marker missing: {relative}")
        check("core compatibility helpers delegated: 5" in text, f"count missing: {relative}")
        check("DEFERRED / Control C" in text, f"deferral missing: {relative}")
    contract = (ROOT / "docs" / "v600_public_safety_contract.md").read_text(encoding="utf-8")
    check("FW-RT6-2a-B-CONTRACT:BEGIN" in contract, "contract marker missing")
    check("private helper names: PRESERVED" in contract, "compatibility missing")
    print("[OK] Control B scope and deferrals are documented")


def import_safety() -> None:
    loaded = sorted(
        name for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN)
    )
    check(not loaded, f"forbidden imports: {loaded}")
    print("[OK] migrated consumer imports stayed provider/runtime safe")


def main() -> None:
    repository_contract()
    wrapper_contract()
    import_safety()
    consumer_contract()
    compatibility_contract()
    docs_contract()
    import_safety()
    print("v600_rt6_2a_control_b_status: implemented-awaiting-review")
    print("v600_rt6_2a_control_b_exact_change_surface_count: 9")
    print("v600_rt6_2a_control_b_root_public_names: 121 / unchanged")
    print("v600_rt6_2a_control_b_core_compatibility_helpers_delegated: 5")
    print("v600_rt6_2a_control_b_nested_credential_redaction: True")
    print("v600_rt6_2a_control_b_nested_private_path_redaction: True")
    print("v600_rt6_2a_control_b_raw_exception_retained: False")
    print("v600_rt6_2a_control_b_private_helper_names_preserved: True")
    print("v600_rt6_2a_control_b_text_chat_raw_error_corrected: False")
    print("v600_rt6_2a_control_b_all_repository_metadata_paths_migrated: False")
    print("v600_rt6_2a_next_control: FW-RT6-2a Control C")
    print("v600_rt6_2a_next_control_authorized: False")
    print("[OK] FW-RT6-2a Control B consumer migration passed")


if __name__ == "__main__":
    main()
