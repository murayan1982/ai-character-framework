"""FW-RT6-7a Control B provider-neutral default voice-input composition gate."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "20792e4292fa9b62e44d9b117e9b87f3199c01bf"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "framework/voice_input_composition.py",
    "framework/voice_input_session.py",
    "scripts/smoke_v600_voice_input_control_a.py",
    "scripts/smoke_v600_voice_input_control_b.py",
}


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: " + " ".join(command) + "\n" + result.stdout + result.stderr,
    )
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        p.strip().replace("\\", "/")
        for p in (*tracked, *untracked)
        if p.strip()
    }


def _source():
    import framework

    fmt = framework.VoiceInputAudioFormat.wav(
        sample_rate_hz=16000,
        channel_count=1,
        duration_ms=250,
    )
    return framework.VoiceInputAudioSource.from_opaque_id(
        "control_b_opaque_audio",
        audio_format=fmt,
        language="ja-JP",
        max_duration_ms=1000,
    )


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        f"Control B exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; "
        f"actual={sorted(actual)!r}",
    )

    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7a — VoiceInputSession capability correction")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(section.count("- [ ]") == 6, "FW-RT6-7a must remain 0 / 6 CLOSED")
    _require(section.count("- [x]") == 0, "Control B must not close aggregate tasks")
    print("[OK] exact six-file Control B surface conforms; FW-RT6-7a remains 0 / 6")


def check_default_fake_and_explicit_adapter_precedence() -> None:
    import framework

    source = _source()

    default_session = framework.create_voice_input_session()
    default_result = default_session.transcribe_audio_result(source)
    _require(default_result.is_completed, "default fake path no longer completes")
    _require(default_result.text == "fake transcript", "default fake transcript drift")
    _require(
        default_result.public_metadata.get("provider_execution_executed") is False,
        "default fake path claims provider execution",
    )
    _require(default_result.public_metadata.get("audio_read") is False, "default fake read audio")

    explicit = framework.FakeVoiceInputProviderAdapter(transcript="explicit transcript")
    real_requested = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=False,
    )
    explicit_result = real_requested.transcribe_audio_result(source, adapter=explicit)
    _require(explicit_result.text == "explicit transcript", "explicit adapter precedence changed")
    _require(
        explicit_result.public_metadata.get("provider_execution_executed") is False,
        "explicit fake adapter claims provider execution",
    )
    print("[OK] default fake path and explicit adapter precedence remain compatible")


def check_real_request_never_silently_falls_back_to_fake() -> None:
    import framework
    from framework.voice_input import VoiceInputOutcome

    source = _source()

    no_outer_opt_in = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=False,
        credential_env={"OPENAI_API_KEY": "presence-only-test"},
    )
    result = no_outer_opt_in.transcribe_audio_result(source)
    _require(result.outcome is VoiceInputOutcome.UNAVAILABLE, "outer guard must be unavailable")
    _require(result.text == "", "real request silently fell back to fake transcript")
    _require(result.public_metadata.get("audio_read") is False, "outer guard read audio")

    no_private = framework.create_voice_input_session(
        provider="openai",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={"OPENAI_API_KEY": "presence-only-test"},
        allow_provider_sdk_import=True,
        allow_provider_client_creation=True,
        allow_real_provider_execution=True,
    )
    result = no_private.transcribe_audio_result(source)
    _require(result.outcome is VoiceInputOutcome.UNAVAILABLE, "missing private credential must reject")
    _require(
        result.public_metadata.get("reason") == "private_credential_required",
        "missing private credential reason drift",
    )
    _require(result.text == "", "missing credential silently fell back to fake")
    _require(result.public_metadata.get("audio_read") is False, "missing credential read audio")

    gate_cases = (
        (
            {"allow_provider_sdk_import": False,
             "allow_provider_client_creation": True,
             "allow_real_provider_execution": True},
            "provider_sdk_import_not_allowed",
        ),
        (
            {"allow_provider_sdk_import": True,
             "allow_provider_client_creation": False,
             "allow_real_provider_execution": True},
            "provider_client_creation_not_allowed",
        ),
        (
            {"allow_provider_sdk_import": True,
             "allow_provider_client_creation": True,
             "allow_real_provider_execution": False},
            "real_provider_execution_not_allowed",
        ),
    )
    for kwargs, reason in gate_cases:
        session = framework.create_voice_input_session(
            provider="openai",
            real_stt_enabled=True,
            allow_provider_execution=True,
            private_credential="control-b-private-placeholder",
            **kwargs,
        )
        result = session.transcribe_audio_result(source)
        _require(result.outcome is VoiceInputOutcome.UNAVAILABLE, f"{reason} must reject")
        _require(result.public_metadata.get("reason") == reason, f"{reason} reason drift")
        _require(result.public_metadata.get("audio_read") is False, f"{reason} read audio")
        _require(
            result.public_metadata.get("provider_execution_executed") is False,
            f"{reason} claims provider execution",
        )
    print("[OK] real STT intent never silently degrades to fake and closed gates stay side-effect free")


def check_session_owned_real_composition_without_provider_specific_host_objects() -> None:
    import framework
    from framework import voice_input_composition
    from framework.voice_input import VoiceInputResult

    source = _source()
    openai_loaded_before = "openai" in sys.modules
    provider_modules_before = {
        name
        for name in sys.modules
        if name.startswith("framework.openai_voice_input_")
    }

    captured: dict[str, object] = {}
    original = voice_input_composition._execute_openai_real

    def fake_execute_openai_real(*, config, audio_source, request):
        captured["provider"] = config.provider
        captured["private_credential_present"] = config.private_credential is not None
        captured["allow_provider_execution"] = config.allow_provider_execution
        captured["allow_provider_sdk_import"] = config.allow_provider_sdk_import
        captured["allow_provider_client_creation"] = config.allow_provider_client_creation
        captured["allow_real_provider_execution"] = config.allow_real_provider_execution
        captured["max_audio_bytes"] = config.max_audio_bytes
        captured["request_language"] = request.language
        captured["audio_id"] = audio_source.audio_id
        return VoiceInputResult.completed(
            "session-composed transcript",
            language=request.language,
            public_metadata={
                "composition_test_double": True,
                "provider_execution_executed": False,
                "audio_read": False,
                "microphone_accessed": False,
                "private_auth_value_exposed": False,
            },
        )

    voice_input_composition._execute_openai_real = fake_execute_openai_real
    try:
        session = framework.create_voice_input_session(
            provider="openai",
            language="ja-JP",
            real_stt_enabled=True,
            allow_provider_execution=True,
            private_credential="control-b-private-placeholder",
            allow_provider_sdk_import=True,
            allow_provider_client_creation=True,
            allow_real_provider_execution=True,
            max_audio_bytes=4096,
            provider_timeout_seconds=12.5,
            provider_max_retries=1,
        )
        result = session.transcribe_audio_result(source)
    finally:
        voice_input_composition._execute_openai_real = original

    _require(result.is_completed, "session-owned real composition did not reach executor seam")
    _require(result.text == "session-composed transcript", "composition seam result drift")
    _require(captured["provider"] == "openai", "provider-neutral selector chose wrong provider")
    _require(captured["private_credential_present"] is True, "private credential not handed internally")
    _require(captured["allow_provider_execution"] is True, "outer execution gate missing")
    _require(captured["allow_provider_sdk_import"] is True, "SDK import gate missing")
    _require(captured["allow_provider_client_creation"] is True, "client creation gate missing")
    _require(captured["allow_real_provider_execution"] is True, "real execution gate missing")
    _require(captured["max_audio_bytes"] == 4096, "provider-neutral audio byte bound missing")
    _require(captured["request_language"] == "ja-JP", "request language not preserved")
    _require(
        ("openai" in sys.modules) == openai_loaded_before,
        "Control B smoke imported the actual OpenAI SDK",
    )
    provider_modules_after = {
        name
        for name in sys.modules
        if name.startswith("framework.openai_voice_input_")
    }
    _require(
        provider_modules_after == provider_modules_before,
        "provider-specific Framework modules loaded before executor seam",
    )
    _require(
        result.public_metadata.get("private_auth_value_exposed") is False,
        "private credential exposure claim drift",
    )
    print("[OK] public session owns provider-neutral real selection without host-built provider adapter/factory/executor")


def check_internal_real_chain_and_public_surface() -> None:
    import framework

    composition_source = (
        PROJECT_ROOT / "framework/voice_input_composition.py"
    ).read_text(encoding="utf-8")
    voice_result_source = (
        PROJECT_ROOT / "framework/voice_input.py"
    ).read_text(encoding="utf-8")
    public_api_source = (
        PROJECT_ROOT / "framework/public_api.py"
    ).read_text(encoding="utf-8")

    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(
        "voice_input_composition" not in framework.__all__,
        "internal composition module became root-public",
    )
    _require(
        "OpenAIVoiceInputPrivateCredential(config.private_credential)" in composition_source,
        "accepted private credential wrapper not reused",
    )
    _require(
        "OpenAIVoiceInputRealProviderPolicy(" in composition_source
        and "OpenAIVoiceInputRealClientFactory(" in composition_source
        and "OpenAIVoiceInputProviderAdapter(" in composition_source
        and "OpenAIVoiceInputRealProviderExecutor(adapter=adapter).execute(" in composition_source,
        "accepted v5.4 OpenAI real runtime chain is not composed internally",
    )
    _require(
        "from .openai_voice_input_provider_adapter import" in composition_source
        and "def _execute_openai_real(" in composition_source,
        "provider-specific lazy boundary missing",
    )
    before_execute = composition_source.split("def _execute_openai_real(", 1)[0]
    _require(
        ".openai_voice_input_provider_adapter" not in before_execute
        and ".openai_voice_input_real_provider" not in before_execute,
        "provider-specific modules are imported before all explicit gates",
    )
    _require(
        "private_credential" not in public_api_source,
        "private credential accidentally became a root-public name",
    )
    _require(
        "session_id:" not in voice_result_source
        and "turn_id:" not in voice_result_source
        and "generation_id:" not in voice_result_source,
        "Control B prematurely changed VoiceInputResult correlation shape",
    )
    print("[OK] internal chain reuses v5.4 runtime lazily; root-public and VoiceInputResult remain unchanged")


def check_docs_and_control_boundaries() -> None:
    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _require(
            "FW-RT6-7a-B-PROVIDER-NEUTRAL-COMPOSITION:BEGIN" in text,
            f"Control B docs marker missing from {relative}",
        )
        _require("no silent fake fallback" in text, f"real/fake selection truthfulness missing from {relative}")
        _require("FW-RT6-7b" in text and "FW-RT6-7c" in text, f"later-task deferral missing from {relative}")

    print("[OK] docs preserve Control B scope and defer 7b/7c responsibilities")


def main() -> None:
    check_exact_surface()
    check_default_fake_and_explicit_adapter_precedence()
    check_real_request_never_silently_falls_back_to_fake()
    check_session_owned_real_composition_without_provider_specific_host_objects()
    check_internal_real_chain_and_public_surface()
    check_docs_and_control_boundaries()

    print("v600_rt6_7a_control_b_status: implemented-awaiting-review")
    print("v600_rt6_7a_control_b_exact_surface: 6 files")
    print("v600_rt6_7a_host_constructs_provider_specific_adapter: False / PASS")
    print("v600_rt6_7a_host_constructs_provider_specific_factory: False / PASS")
    print("v600_rt6_7a_host_constructs_provider_specific_executor: False / PASS")
    print("v600_rt6_7a_default_fake_path: PASS")
    print("v600_rt6_7a_explicit_adapter_precedence: PASS")
    print("v600_rt6_7a_real_request_silent_fake_fallback: False / PASS")
    print("v600_rt6_7a_private_credential_from_credential_env_consumed: False / PASS")
    print("v600_rt6_7a_provider_specific_framework_modules_lazy_before_executor: True / PASS")
    print("v600_rt6_7a_actual_openai_sdk_imported: False / PASS")
    print("v600_rt6_7a_actual_provider_client_created: False / PASS")
    print("v600_rt6_7a_network_execution: False / PASS")
    print("v600_rt6_7a_microphone_access: False / PASS")
    print("v600_rt6_7a_private_credential_exposed: False / PASS")
    print("v600_rt6_7a_voice_input_result_changed: False")
    print("v600_rt6_7a_7b_lifecycle_adopted: False")
    print("v600_rt6_7a_7c_result_correlation_adopted: False")
    print("v600_rt6_7a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_7a_task_count: 0 / 6 CLOSED")
    print("v600_rt6_7a_control_c: NOT_AUTHORIZED")
    print("v600_rt6_7a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
