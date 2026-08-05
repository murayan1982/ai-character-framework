"""FW-RT6-2a Control A recursive public-safety primitive smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube
Studio, private configuration, or host-application repository operation occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
from pathlib import Path
import subprocess
import sys
from types import MappingProxyType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "463496642f87daac1d280001d0385da1277a9f42"
EXPECTED_BASELINE_PARENT = "753748d463f800647b251c788d217a5c5adc4049"
EXPECTED_BASELINE_SUBJECT = "docs/test: accept detailed capability snapshot"
EXPECTED_BASELINE_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_realtime_capability_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_public_safety_contract.md",
    "framework/public_safety.py",
    "scripts/smoke_v600_public_safety_primitives.py",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
)


def _assert(condition: bool, message: str) -> None:
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
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).splitlines()
        if line.strip()
    }


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected Control A baseline")
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == EXPECTED_BASELINE_SURFACE,
        "baseline Control D surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted Control D baseline and exact five-file Control A surface conform")


def check_public_surface() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    _assert(
        "sanitize_public_value" not in PUBLIC_API_NAMES,
        "internal public-safety helper leaked to root public API",
    )
    _assert(
        "PublicErrorClassification" not in PUBLIC_API_NAMES,
        "internal error classification leaked to root public API",
    )
    print("[OK] canonical root-public surface remains 121 names")


def check_recursive_sanitization(safety: object) -> None:
    @dataclass
    class Nested:
        label: str
        api_key: str
        payload: object

    secret = "top-secret-value"
    private_windows = r"E:\private\credentials.json"
    private_posix = "/home/operator/private.env"

    value = {
        "safe": "visible",
        "API-Key": secret,
        "nested": [
            {
                "authorization": {"token": secret},
                "path": private_windows,
                "url": "https://example.test/public/audio.mp3",
            },
            Nested(
                label="ok",
                api_key=secret,
                payload=("safe", private_posix),
            ),
        ],
    }

    sanitized = safety.sanitize_public_value(value)
    _assert(isinstance(sanitized, MappingProxyType), "top-level mapping is mutable")
    _assert(sanitized["safe"] == "visible", "safe value changed")
    _assert(sanitized["API-Key"] == safety.REDACTED_VALUE, "separator-insensitive key not redacted")

    nested = sanitized["nested"]
    _assert(isinstance(nested, tuple), "list did not become immutable tuple")
    _assert(isinstance(nested[0], MappingProxyType), "nested mapping is mutable")
    _assert(
        nested[0]["authorization"] == safety.REDACTED_VALUE,
        "secret parent value was traversed instead of redacted",
    )
    _assert(nested[0]["path"] == safety.REDACTED_PATH, "Windows path leaked")
    _assert(
        nested[0]["url"] == "https://example.test/public/audio.mp3",
        "ordinary public URL was incorrectly redacted",
    )
    _assert(isinstance(nested[1], MappingProxyType), "dataclass did not become immutable mapping")
    _assert(nested[1]["api_key"] == safety.REDACTED_VALUE, "dataclass secret leaked")
    _assert(nested[1]["payload"][1] == safety.REDACTED_PATH, "POSIX path leaked")

    _assert(secret not in repr(sanitized), "nested credential remains observable")
    _assert(private_windows not in repr(sanitized), "Windows path remains observable")
    _assert(private_posix not in repr(sanitized), "POSIX path remains observable")
    print("[OK] mapping/list/tuple/dataclass recursive sanitization and redaction conform")


def check_edge_safety(safety: object) -> None:
    cycle: list[object] = []
    cycle.append(cycle)
    sanitized_cycle = safety.sanitize_public_value(cycle)
    _assert(sanitized_cycle == (safety.REDACTED_CYCLE,), "cycle marker drift")

    deep: object = "leaf"
    for _ in range(20):
        deep = [deep]
    sanitized_deep = safety.sanitize_public_value(deep, max_depth=4)
    _assert(
        safety.REDACTED_MAX_DEPTH in repr(sanitized_deep),
        "max-depth marker missing",
    )

    _assert(
        safety.sanitize_public_value(RuntimeError("secret raw exception"))
        == safety.REDACTED_EXCEPTION,
        "raw exception object was retained",
    )
    _assert(
        safety.sanitize_public_value(b"private bytes") == safety.REDACTED_BINARY,
        "binary material was retained",
    )
    _assert(
        safety.sanitize_public_value(Path("relative/file.txt"))
        == safety.REDACTED_PATH,
        "PathLike value was retained",
    )
    _assert(
        safety.sanitize_public_value(float("nan")) == safety.REDACTED_NON_FINITE,
        "non-finite number was retained",
    )
    _assert(
        isinstance(safety.public_mapping({"items": [1, 2]}), MappingProxyType),
        "public_mapping is mutable",
    )
    print("[OK] exception, binary, path, cycle, depth, and non-finite handling conform")


def check_error_classification(safety: object) -> None:
    raw_secret = "API_KEY=private-value"
    raw_path = r"E:\private\provider_payload.json"

    cases = (
        (
            TimeoutError(f"{raw_secret} {raw_path}"),
            "timeout",
            True,
        ),
        (
            PermissionError(f"{raw_secret} {raw_path}"),
            "authentication_required",
            False,
        ),
        (
            ConnectionError(f"{raw_secret} {raw_path}"),
            "provider_unavailable",
            True,
        ),
        (
            ValueError(f"{raw_secret} {raw_path}"),
            "invalid_request",
            False,
        ),
    )

    for error, code, retryable in cases:
        classified = safety.classify_public_exception(error)
        serialized = repr(classified)
        _assert(classified.public_error_code == code, f"classification drift: {code}")
        _assert(classified.retryable is retryable, f"retryability drift: {code}")
        _assert(raw_secret not in serialized, f"raw exception secret exposed: {code}")
        _assert(raw_path not in serialized, f"raw exception path exposed: {code}")
        _assert(type(error).__name__ not in serialized, f"exception type exposed: {code}")

    fallback = safety.classify_public_exception(
        RuntimeError(f"{raw_secret} {raw_path}"),
        fallback_error_code="operation_failed",
        fallback_safe_message="The operation could not be completed.",
        fallback_retryable=True,
    )
    _assert(fallback.public_error_code == "operation_failed", "fallback code drift")
    _assert(fallback.retryable is True, "fallback retryability drift")
    _assert(raw_secret not in repr(fallback), "fallback raw secret exposed")
    _assert(raw_path not in repr(fallback), "fallback raw path exposed")
    print("[OK] safe error classification exposes no raw exception material")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs" / "v600_public_safety_contract.md").read_text(
        encoding="utf-8"
    )
    for relative in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-2a-A-PUBLIC-SAFETY-PRIMITIVES:BEGIN" in text,
            f"Control A marker missing: {relative}",
        )
        _assert(
            "existing consumer migration: DEFERRED / Control B" in text,
            f"consumer deferral missing: {relative}",
        )
        _assert(
            "TextChat raw error event correction: DEFERRED / Control C" in text,
            f"TextChat deferral missing: {relative}",
        )

    for phrase in (
        "root-public names:",
        "121 / UNCHANGED",
        "existing public consumer migration:",
        "NOT INCLUDED",
        "TextChat raw error event correction:",
        "NOT INCLUDED",
    ):
        _assert(phrase in contract, f"contract phrase missing: {phrase}")

    print("[OK] public-safety contract and truthful Control A deferrals are documented")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] public-safety primitive import stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_public_surface()
    check_import_safety()

    safety = importlib.import_module("framework.public_safety")
    check_recursive_sanitization(safety)
    check_edge_safety(safety)
    check_error_classification(safety)
    check_docs()
    check_import_safety()

    print("v600_rt6_2a_control_a_status: implemented-awaiting-review")
    print("v600_rt6_2a_control_a_exact_change_surface: True")
    print("v600_rt6_2a_control_a_root_public_names: 121 / unchanged")
    print("v600_rt6_2a_control_a_recursive_mapping_list_tuple_dataclass: True")
    print("v600_rt6_2a_control_a_secret_key_policy_centralized: True")
    print("v600_rt6_2a_control_a_private_path_redaction: True")
    print("v600_rt6_2a_control_a_raw_exception_exposed_by_utility: False")
    print("v600_rt6_2a_control_a_safe_error_classification: True")
    print("v600_rt6_2a_control_a_existing_consumer_migration: False")
    print("v600_rt6_2a_control_a_text_chat_error_event_corrected: False")
    print("v600_rt6_2a_control_a_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2a_next_control: FW-RT6-2a Control B")
    print("v600_rt6_2a_next_control_authorized: False")
    print("[OK] FW-RT6-2a Control A recursive public-safety primitives passed")


if __name__ == "__main__":
    main()
