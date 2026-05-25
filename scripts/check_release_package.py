from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "README.md",
    "LICENSE.txt",
    ".env.example",
    "requirements.txt",
    "install.bat",
    "run.bat",
    "main.py",
    "docs/RELEASE_NOTES.md",
    "docs/release_package_policy.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
    "docs/roadmap_feature_v4.0.0.md",
    "docs/roadmap_feature_v5.0.0.md",
    "docs/voice_output_real_tts_opt_in_checklist.md",
    "docs/voice_output_artifact_result_contract.md",
    "docs/voice_output_real_provider_execution_guard.md",
    "docs/voice_output_v500_release_readiness_checklist.md",
    "scripts/smoke_app_sdk.py",
    "scripts/smoke_voice_output_real_tts_opt_in_boundary.py",
    "scripts/smoke_voice_output_artifact_result_contract.py",
    "scripts/smoke_voice_output_real_provider_execution_guard.py",
    "scripts/smoke_voice_output_v500_release_readiness.py",
]

REQUIRED_DIRS = [
    "characters",
    "config",
    "core",
    "docs",
    "examples",
    "framework",
    "live2d",
    "llm",
    "plugins",
    "presets",
    "registry",
    "scripts",
    "stt",
    "tts",
    "utils",
]

FORBIDDEN_PATH_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "dist",
    "build",
}

FORBIDDEN_FILE_PATTERNS = [
    re.compile(r"^\.env$"),
    re.compile(r".*\.pyc$"),
    re.compile(r".*\.log$"),
    re.compile(r"release_checklist_.*\.md$"),
]

PUBLIC_DOCS = [
    "README.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
    "docs/RELEASE_NOTES.md",
    "docs/roadmap_feature_v4.0.0.md",
    "docs/roadmap_feature_v5.0.0.md",
    "docs/voice_output_real_tts_opt_in_checklist.md",
    "docs/voice_output_artifact_result_contract.md",
    "docs/voice_output_real_provider_execution_guard.md",
    "docs/voice_output_v500_release_readiness_checklist.md",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_required_files(errors: list[str]) -> None:
    for item in REQUIRED_FILES:
        path = ROOT / item
        if not path.is_file():
            fail(errors, f"Missing required file: {item}")


def check_required_dirs(errors: list[str]) -> None:
    for item in REQUIRED_DIRS:
        path = ROOT / item
        if not path.is_dir():
            fail(errors, f"Missing required directory: {item}")


def check_forbidden_paths(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        relative_parts = path.relative_to(ROOT).parts

        for part in relative_parts:
            if part in FORBIDDEN_PATH_PARTS:
                fail(errors, f"Forbidden path found: {rel(path)}")
                break

        if not path.is_file():
            continue

        name = path.name
        for pattern in FORBIDDEN_FILE_PATTERNS:
            if pattern.match(name):
                fail(errors, f"Forbidden file found: {rel(path)}")
                break


def check_public_doc_references(errors: list[str]) -> None:
    forbidden_text_patterns = [
        re.compile(r"RELEASE_NOTES_v\d+\.\d+\.\d+\.md"),
        re.compile(r"release_checklist_.*\.md"),
    ]

    for item in PUBLIC_DOCS:
        path = ROOT / item
        if not path.is_file():
            continue

        text = path.read_text(encoding="utf-8")

        for pattern in forbidden_text_patterns:
            for match in pattern.finditer(text):
                fail(
                    errors,
                    f"Forbidden public doc reference in {item}: {match.group(0)}",
                )


def check_local_markdown_links(errors: list[str]) -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]+)?\)")
    inline_path_pattern = re.compile(r"`([^`]+\.md)`")

    for item in PUBLIC_DOCS:
        path = ROOT / item
        if not path.is_file():
            continue

        text = path.read_text(encoding="utf-8")
        candidates: list[str] = []

        candidates.extend(match.group(1) for match in link_pattern.finditer(text))
        candidates.extend(match.group(1) for match in inline_path_pattern.finditer(text))

        for target in candidates:
            if target.startswith(("http://", "https://", "mailto:")):
                continue

            if target.startswith("#"):
                continue

            target_path = (path.parent / target).resolve()

            try:
                target_path.relative_to(ROOT)
            except ValueError:
                fail(errors, f"Markdown reference points outside repo: {item} -> {target}")
                continue

            if not target_path.exists():
                fail(errors, f"Missing Markdown reference: {item} -> {target}")


def main() -> int:
    errors: list[str] = []

    check_required_files(errors)
    check_required_dirs(errors)
    check_public_doc_references(errors)
    check_local_markdown_links(errors)

    if errors:
        print("[release-package-check] FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    print("[release-package-check] OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())