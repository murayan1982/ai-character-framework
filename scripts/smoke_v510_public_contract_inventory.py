"""Mock-safe public contract inventory for FW v5.1.0.

This is an inventory smoke, not the final v5.1.0 conformance gate.
It records the current public surface before installable-SDK and stable-contract
work starts. The script intentionally avoids real provider execution.
"""

from __future__ import annotations

import inspect
import os
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


REQUIRED_PUBLIC_SYMBOLS = (
    "create_text_chat_session",
    "TextChatSessionInfo",
    "TextChatResult",
    "CapabilityStatus",
    "FrameworkCapabilities",
    "get_capabilities",
    "create_voice_output_session",
    "VoiceOutputSession",
    "VoiceOutputSessionInfo",
    "VoiceOutputRequest",
        "VoiceArtifactRef",
    "VoiceOutputResult",
)

VOICE_OUTPUT_METHOD_CANDIDATES = (
    "create_output",
    "speak",
    "synthesize",
    "synthesize_text",
    "speak_text",
    "generate_audio",
)

FORBIDDEN_IMPORT_MARKERS = (
    "tts.voice_engine",
    "elevenlabs",
    "vts",
    "vtube",
    "live2d",
)

REAL_PROVIDER_ENV_KEYS = (
    "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
    "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
)

PRIVATE_LEAK_PATTERNS = (
    re.compile(r"(?i)api[_-]?key"),
    re.compile(r"(?i)secret"),
    re.compile(r"(?i)token"),
    re.compile(r"(?i)elevenlabs"),
    re.compile(r"(?i)provider raw"),
)


class InventoryFailure(AssertionError):
    pass


def ok(message: str) -> None:
    print(f"[OK] {message}")


def info(message: str) -> None:
    print(f"[INFO] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


@contextmanager
def disabled_real_provider_execution() -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in REAL_PROVIDER_ENV_KEYS}
    try:
        for key in REAL_PROVIDER_ENV_KEYS:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InventoryFailure(message)


def assert_no_new_forbidden_imports(before_modules: set[str], after_modules: set[str]) -> None:
    new_modules = after_modules - before_modules
    offenders = sorted(
        module_name
        for module_name in new_modules
        if any(marker in module_name.lower() for marker in FORBIDDEN_IMPORT_MARKERS)
    )
    require(
        not offenders,
        "import framework eagerly imported forbidden provider/internal modules: "
        + ", ".join(offenders),
    )
    ok("import framework did not eagerly load forbidden provider/internal modules")


def public_signature(obj: object) -> str:
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "<signature unavailable>"


def get_callable_methods(obj: object, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if callable(getattr(obj, name, None))]


def check_public_symbols(framework: object) -> None:
    exports = tuple(getattr(framework, "__all__", ()))
    require(exports, "framework.__all__ is missing or empty")
    ok("framework.__all__ is present")

    missing = [name for name in REQUIRED_PUBLIC_SYMBOLS if not hasattr(framework, name)]
    require(not missing, "missing required public symbols: " + ", ".join(missing))

    missing_from_all = [name for name in REQUIRED_PUBLIC_SYMBOLS if name not in exports]
    require(
        not missing_from_all,
        "required public symbols are not exported via framework.__all__: "
        + ", ".join(missing_from_all),
    )
    ok("required v5.1.0 baseline public symbols are exported")

    for name in REQUIRED_PUBLIC_SYMBOLS:
        info(f"public symbol: {name}")


def check_factory_signatures(framework: object) -> None:
    for name in ("create_text_chat_session", "create_voice_output_session"):
        obj = getattr(framework, name)
        info(f"signature {name}{public_signature(obj)}")
    ok("public factory signatures are inventory-recorded")


def check_voice_output_contract(framework: object) -> None:
    with disabled_real_provider_execution():
        session = framework.create_voice_output_session()
        methods = get_callable_methods(session, VOICE_OUTPUT_METHOD_CANDIDATES)
        require(methods, "voice output session has none of the known public output methods")
        info("voice output callable methods: " + ", ".join(methods))

        if "speak" not in methods and "create_output" in methods:
            warn("voice output currently exposes create_output without speak; docs/API alignment should be resolved under FW-F2")

        request = framework.VoiceOutputRequest(
            text="今日は少し早めに休むとよさそうです。",
            voice_profile_id="gentle_mina_default",
            requested_audio_format="mp3",
            utterance_purpose="inventory_smoke",
            language_code="ja",
        )

        output_method_name = "create_output" if "create_output" in methods else methods[0]
        result = getattr(session, output_method_name)(request)

    for attr in (
        "request_state",
        "audio_ready",
        "audio_format",
        "audio_url",
        "audio_artifact_ref",
        "audio_handoff_kind",
        "has_audio_handoff",
        "is_generated",
    ):
        require(hasattr(result, attr), f"VoiceOutputResult is missing public attribute: {attr}")

    require(result.audio_ready is False, "mock-safe inventory voice output unexpectedly produced ready audio")
    require(result.has_audio_handoff is False, "mock-safe inventory voice output unexpectedly produced an audio handoff")
    require(result.is_generated is False, "mock-safe inventory voice output unexpectedly reports generated=True")
    require(result.audio_url is None, "mock-safe inventory voice output unexpectedly exposed audio_url")
    require(result.audio_artifact_ref is None, "mock-safe inventory voice output unexpectedly exposed audio_artifact_ref")

    public_result_text = repr(result)
    leaks = [pattern.pattern for pattern in PRIVATE_LEAK_PATTERNS if pattern.search(public_result_text)]
    require(not leaks, "VoiceOutputResult repr appears to contain private/provider details: " + ", ".join(leaks))

    ok("Voice Output public request/result path is mock-safe")


def check_readme_alignment(repo_root: Path, framework: object) -> None:
    readme_path = repo_root / "README.md"
    if not readme_path.exists():
        warn("README.md not found; docs/API alignment scan skipped")
        return

    readme_text = readme_path.read_text(encoding="utf-8", errors="replace")
    with disabled_real_provider_execution():
        session = framework.create_voice_output_session()
        methods = get_callable_methods(session, VOICE_OUTPUT_METHOD_CANDIDATES)

    if "session.speak(" in readme_text and "speak" not in methods:
        warn("README references session.speak(...) but current voice output session does not expose speak")
    else:
        ok("README voice output method reference has no known speak/create_output mismatch")


def check_examples(repo_root: Path) -> None:
    examples_dir = repo_root / "examples"
    require(examples_dir.exists(), "examples directory is missing")

    example_files = sorted(path.name for path in examples_dir.glob("*.py"))
    require(example_files, "examples directory has no Python examples")
    info("python examples: " + ", ".join(example_files))

    if "app_voice_output_integration.py" in example_files:
        ok("voice output app integration example is present")
    else:
        warn("app_voice_output_integration.py is missing; v5 voice output example path should be confirmed")


def main() -> None:
    repo_root = Path.cwd()
    require((repo_root / "framework").exists(), "run this smoke from the FW repository root")

    # When this script is executed as `python scripts/...`, Python puts the
    # scripts directory at sys.path[0]. Add the repository root explicitly so
    # this inventory can run before FW is converted to an installable package.
    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)

    before_modules = set(sys.modules)
    import framework  # noqa: PLC0415

    after_modules = set(sys.modules)
    assert_no_new_forbidden_imports(before_modules, after_modules)

    check_public_symbols(framework)
    check_factory_signatures(framework)
    check_voice_output_contract(framework)
    check_readme_alignment(repo_root, framework)
    check_examples(repo_root)

    ok("v5.1.0 public contract inventory is mock-safe")


if __name__ == "__main__":
    main()
