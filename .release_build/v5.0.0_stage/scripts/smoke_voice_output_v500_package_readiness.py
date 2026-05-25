"""Smoke checks for v5.0.0 voice output package readiness.

This script is intentionally mock-safe. It validates the final public package
readiness docs and release-surface wiring without provider credentials,
provider SDK imports, provider network calls, or generated audio artifacts.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


REQUIRED_V500_COMMANDS = [
    "python -m compileall -q .",
    "python scripts/smoke_public_facade.py",
    "python scripts/smoke_app_sdk.py",
    "python scripts/smoke_voice_output_real_tts_opt_in_boundary.py",
    "python scripts/smoke_voice_output_artifact_result_contract.py",
    "python scripts/smoke_voice_output_real_provider_execution_guard.py",
    "python scripts/smoke_voice_output_host_app_handoff.py",
    "python scripts/smoke_voice_output_v500_release_readiness.py",
    "python scripts/smoke_voice_output_v500_package_readiness.py",
    "python scripts/check_release_package.py",
    "python examples/app_voice_output_integration.py",
]

REQUIRED_PACKAGE_ITEMS = [
    "docs/RELEASE_NOTES.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
    "docs/roadmap_feature_v5.0.0.md",
    "docs/voice_output_real_tts_opt_in_checklist.md",
    "docs/voice_output_artifact_result_contract.md",
    "docs/voice_output_real_provider_execution_guard.md",
    "docs/voice_output_v500_release_readiness_checklist.md",
    "docs/host_app_voice_output_integration_handoff.md",
    "docs/voice_output_v500_package_readiness.md",
    "examples/app_voice_output_integration.py",
    "scripts/smoke_voice_output_real_tts_opt_in_boundary.py",
    "scripts/smoke_voice_output_artifact_result_contract.py",
    "scripts/smoke_voice_output_real_provider_execution_guard.py",
    "scripts/smoke_voice_output_host_app_handoff.py",
    "scripts/smoke_voice_output_v500_release_readiness.py",
    "scripts/smoke_voice_output_v500_package_readiness.py",
    "scripts/check_release_package.py",
]


FORBIDDEN_README_PHRASES = [
    "v5.0.0 focuses on Realtime Voice Runtime",
]


REQUIRED_README_PHRASES = [
    "v5.0.0 focuses on Public Voice Output / TTS Boundary Foundation",
    "mock-safe public voice output boundary",
    "not the full realtime voice runtime release",
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _assert_contains(text: str, phrase: str, context: str) -> None:
    _assert(phrase in text, f"{context} is missing: {phrase}")


def check_package_readiness_doc() -> None:
    text = _read("docs/voice_output_v500_package_readiness.md")
    required_phrases = [
        "v5.0.0 Voice Output Package Readiness",
        "Public Voice Output / TTS Boundary Foundation",
        "mock-safe public voice output boundary",
        "does not package DRC real Web audio evidence",
        "What this package proves",
        "What this package does not prove",
        "Verification command set",
        "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
        "DRC real_tts_web_audio_output: NOT_ACCEPTED",
        "DRC v2.0.0: NOT_RELEASED",
        "scripts/smoke_voice_output_v500_package_readiness.py",
    ]

    for phrase in required_phrases:
        _assert_contains(text, phrase, "package readiness doc")

    for command in REQUIRED_V500_COMMANDS:
        _assert_contains(text, command, "package readiness verification command set")

    print("[OK] voice output v5.0.0 package readiness doc is documented")


def check_release_notes_are_finalized() -> None:
    text = _read("docs/RELEASE_NOTES.md")
    required_phrases = [
        "Release scope",
        "Public Voice Output / TTS Boundary Foundation",
        "mock-safe public boundary release",
        "not a DRC real Web audio evidence release",
        "Package readiness",
        "voice_output_v500_package_readiness.md",
        "scripts/smoke_voice_output_v500_package_readiness.py",
        "DRC real_tts_web_audio_output: NOT_ACCEPTED",
        "DRC v2.0.0: NOT_RELEASED",
    ]

    for phrase in required_phrases:
        _assert_contains(text, phrase, "release notes")

    for command in REQUIRED_V500_COMMANDS:
        _assert_contains(text, command, "release notes verification command set")

    print("[OK] v5.0.0 release notes are package-ready")


def check_readme_v5_scope_is_current() -> None:
    text = _read("README.md")

    for phrase in REQUIRED_README_PHRASES:
        _assert_contains(text, phrase, "README v5.0.0 scope")

    for phrase in FORBIDDEN_README_PHRASES:
        _assert(phrase not in text, f"README still contains stale v5.0.0 scope: {phrase}")

    print("[OK] README v5.0.0 scope is current")


def check_release_package_policy_has_v500_commands() -> None:
    text = _read("docs/release_package_policy.md")

    _assert_contains(text, "v5.0.0 mock-safe package verification", "release package policy")
    for command in REQUIRED_V500_COMMANDS:
        _assert_contains(text, command, "release package policy verification command set")

    print("[OK] release package policy includes v5.0.0 verification commands")


def check_release_readiness_references_package_smoke() -> None:
    text = _read("docs/voice_output_v500_release_readiness_checklist.md")

    required_phrases = [
        "voice_output_v500_package_readiness.md",
        "python scripts/smoke_voice_output_v500_package_readiness.py",
        "package-readiness smoke",
    ]
    for phrase in required_phrases:
        _assert_contains(text, phrase, "release readiness checklist")

    print("[OK] release readiness checklist references package smoke")


def check_release_package_check_includes_package_items() -> None:
    text = _read("scripts/check_release_package.py")

    for item in REQUIRED_PACKAGE_ITEMS:
        _assert_contains(text, item, "release package check")

    print("[OK] release package check includes v5.0.0 package readiness items")


def check_package_items_exist() -> None:
    missing = [item for item in REQUIRED_PACKAGE_ITEMS if not (PROJECT_ROOT / item).is_file()]
    _assert(not missing, f"Missing v5.0.0 package items: {missing}")
    print("[OK] v5.0.0 package readiness items exist")


def main() -> int:
    checks = [
        check_package_items_exist,
        check_package_readiness_doc,
        check_release_notes_are_finalized,
        check_readme_v5_scope_is_current,
        check_release_package_policy_has_v500_commands,
        check_release_readiness_references_package_smoke,
        check_release_package_check_includes_package_items,
    ]

    for check in checks:
        check()

    print("[OK] voice output v5.0.0 package readiness is mock-safe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
