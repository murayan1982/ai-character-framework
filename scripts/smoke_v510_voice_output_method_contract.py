"""Mock-safe voice output method contract smoke for FW v5.1.0.

This verifies the FW-F2 alignment checkpoint:
- `speak(request)` is the preferred public voice output method.
- `create_output(request)` remains available as a v5.0 compatibility method.
- both paths keep the v5 provider-neutral, mock-safe result contract.
"""

from __future__ import annotations

import inspect
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


REAL_PROVIDER_ENV_KEYS = (
    "FRAMEWORK_VOICE_OUTPUT_REAL_TTS",
    "FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION",
)


class ContractFailure(AssertionError):
    pass


def ok(message: str) -> None:
    print(f"[OK] {message}")


def info(message: str) -> None:
    print(f"[INFO] {message}")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


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


def assert_mock_safe_result(result: object, label: str) -> None:
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
        require(hasattr(result, attr), f"{label} result missing public attribute: {attr}")

    require(result.audio_ready is False, f"{label} unexpectedly produced ready audio")
    require(result.has_audio_handoff is False, f"{label} unexpectedly produced an audio handoff")
    require(result.is_generated is False, f"{label} unexpectedly reports generated=True")
    require(result.audio_url is None, f"{label} unexpectedly exposed audio_url")
    require(result.audio_artifact_ref is None, f"{label} unexpectedly exposed audio_artifact_ref")


def assert_single_request_parameter(method: object, method_name: str) -> None:
    signature = inspect.signature(method)
    params = list(signature.parameters)
    require(
        params == ["request"],
        f"{method_name} should expose one bound parameter named request, got: {signature}",
    )
    info(f"signature {method_name}{signature}")


def check_docs_and_examples(repo_root: Path) -> None:
    contract_doc = repo_root / "docs" / "v510_voice_output_method_contract.md"
    require(contract_doc.exists(), "voice output method contract doc is missing")
    doc_text = contract_doc.read_text(encoding="utf-8", errors="replace")
    require("VoiceOutputSession.speak" in doc_text, "method contract doc does not define speak")
    require("create_output(request): v5.0 compatibility" in doc_text, "method contract doc does not preserve create_output compatibility")
    ok("voice output method contract doc is documented")

    readme_text = (repo_root / "README.md").read_text(encoding="utf-8", errors="replace")
    require("session.speak(" in readme_text, "README should show session.speak(...) as the preferred public method")
    ok("README uses the preferred voice output method name")

    example_path = repo_root / "examples" / "app_voice_output_integration.py"
    require(example_path.exists(), "voice output app integration example is missing")
    example_text = example_path.read_text(encoding="utf-8", errors="replace")
    require(".speak(" in example_text, "voice output app integration example should call session.speak(...)")
    require(".create_output(" not in example_text, "voice output app integration example should not call create_output directly")
    ok("voice output app integration example uses speak")


def main() -> None:
    repo_root = Path.cwd()
    require((repo_root / "framework").exists(), "run this smoke from the FW repository root")

    repo_root_text = str(repo_root)
    if repo_root_text not in sys.path:
        sys.path.insert(0, repo_root_text)

    import framework  # noqa: PLC0415

    with disabled_real_provider_execution():
        session = framework.create_voice_output_session()
        speak = getattr(session, "speak", None)
        create_output = getattr(session, "create_output", None)

        require(callable(speak), "VoiceOutputSession is missing preferred public method: speak")
        require(callable(create_output), "VoiceOutputSession is missing v5.0 compatibility method: create_output")
        ok("voice output exposes speak and create_output")

        assert_single_request_parameter(speak, "VoiceOutputSession.speak")
        assert_single_request_parameter(create_output, "VoiceOutputSession.create_output")

        request = framework.VoiceOutputRequest(
            text="今日は少し早めに休むとよさそうです。",
            voice_profile_id="gentle_mina_default",
            requested_audio_format="mp3",
            utterance_purpose="v510_method_contract",
            language_code="ja",
        )

        speak_result = speak(request)
        create_output_result = create_output(request)

    assert_mock_safe_result(speak_result, "speak")
    assert_mock_safe_result(create_output_result, "create_output")
    ok("voice output speak/create_output paths are mock-safe")

    check_docs_and_examples(repo_root)
    ok("voice output method contract is aligned for v5.1.0")


if __name__ == "__main__":
    main()
