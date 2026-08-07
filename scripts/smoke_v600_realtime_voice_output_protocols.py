"""FW-RT6-6a Control A voice-synthesis generation protocol smoke.

Offline/mock-safe. Verifies the exact five-file Control A surface, stable
``framework.realtime_voice_output`` package, work identity, result/active/cancel
models, structural provider/stage protocols, capability truthfulness, root-public
compatibility, and provider/runtime import safety without real provider,
network, microphone, playback, private configuration, or VTube Studio work.
"""

from __future__ import annotations

import argparse
from dataclasses import fields
import importlib
import inspect
from pathlib import Path
import re
import subprocess
import sys
from typing import get_type_hints

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "3c40a1bc537aaa9015235b520b3431819ec0381a"
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_voice_output_contract.md",
    "framework/realtime_voice_output.py",
    "scripts/smoke_v600_realtime_voice_output_protocols.py",
}
EXPECTED_EXPORTS = (
    "SynthesisWorkId",
    "VoiceSynthesisResultEnvelope",
    "VoiceSynthesisActiveGeneration",
    "VoiceSynthesisCancelOutcome",
    "VoiceSynthesisCancelResult",
    "VoiceSynthesisProviderAdapter",
    "VoiceSynthesisStage",
)
FORBIDDEN_IMPORTS = {
    "openai",
    "elevenlabs",
    "requests",
    "httpx",
    "pyvts",
    "websocket",
    "websockets",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "tts.voice_engine",
    "core.runtime",
    "core.pipeline",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _assert(
        completed.returncode == 0,
        "command failed: " + " ".join(command) + "\n" + completed.stdout + completed.stderr,
    )
    return completed.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    tracked = _git("diff", "--name-only", "HEAD").splitlines()
    untracked = _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {p.strip().replace("\\", "/") for p in (*tracked, *untracked) if p.strip()}


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_BASELINE, "baseline origin/main drift")
    actual = _changed_paths()
    _assert(actual == EXPECTED_SURFACE, f"Control A surface drift: {sorted(actual)!r}")
    print("[OK] baseline and exact five-file FW-RT6-6a Control A surface conform")


def check_stable_package() -> None:
    import framework

    _assert(len(framework.__all__) == 127, "root-public name count drift")
    for name in EXPECTED_EXPORTS:
        _assert(name not in framework.__all__, f"Control A leaked root-public name: {name}")
    _assert(
        "framework.realtime_voice_output" not in sys.modules,
        "root import eagerly loaded realtime_voice_output",
    )

    module = importlib.import_module("framework.realtime_voice_output")
    _assert(tuple(module.__all__) == EXPECTED_EXPORTS, "stable package export drift")
    print("[OK] stable explicit package and 127-name root compatibility conform")


def check_source_safety() -> None:
    source_path = PROJECT_ROOT / "framework/realtime_voice_output.py"
    source = source_path.read_text(encoding="utf-8")
    lowered = [line.strip().lower() for line in source.splitlines()]
    for forbidden in FORBIDDEN_IMPORTS:
        _assert(
            not any(
                line == f"import {forbidden}"
                or line.startswith(f"import {forbidden} ")
                or line.startswith(f"from {forbidden} ")
                for line in lowered
            ),
            f"forbidden provider/runtime import: {forbidden}",
        )
    for phrase in (
        're.compile(r"^fw_synthesis_[0-9a-f]{32}$")',
        "class SynthesisWorkId(str):",
        "class VoiceSynthesisResultEnvelope:",
        "result: VoiceOutputResult = field(repr=False)",
        "class VoiceSynthesisActiveGeneration:",
        "class VoiceSynthesisCancelOutcome(str, Enum):",
        "class VoiceSynthesisCancelResult:",
        "class VoiceSynthesisProviderAdapter(Protocol):",
        "class VoiceSynthesisStage(Protocol):",
    ):
        _assert(phrase in source, f"source contract marker missing: {phrase}")
    print("[OK] source is provider-neutral and required model/protocol vocabulary exists")


def check_models() -> None:
    from framework.audio.voice_output import VoiceOutputResult
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import RealtimeStageContext
    from framework.realtime_voice_output import (
        SynthesisWorkId,
        VoiceSynthesisActiveGeneration,
        VoiceSynthesisCancelOutcome,
        VoiceSynthesisCancelResult,
        VoiceSynthesisResultEnvelope,
    )

    work_id = SynthesisWorkId.new()
    _assert(re.fullmatch(r"fw_synthesis_[0-9a-f]{32}", str(work_id)) is not None, "work ID format drift")
    _assert(SynthesisWorkId.parse(str(work_id)) == work_id, "work ID parse drift")
    for invalid in ("", " fw_synthesis_" + "0" * 32, "fw_synthesis_ABC", str(GenerationId.new())):
        try:
            SynthesisWorkId.parse(invalid)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid synthesis work ID accepted: {invalid!r}")

    context = RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
    )
    work_id_2 = SynthesisWorkId.new()
    _assert(work_id != work_id_2, "two work items reused the same identity")
    _assert(context.generation_id == context.generation_id, "generation context drift")

    result = VoiceOutputResult(
        request_state="generated",
        audio_ready=True,
        audio_url="https://example.invalid/private-audio",
    )
    envelope = VoiceSynthesisResultEnvelope(context=context, work_id=work_id, result=result)
    _assert(
        tuple(field.name for field in fields(VoiceSynthesisResultEnvelope)) == ("context", "work_id", "result"),
        "result envelope fields drift",
    )
    _assert("private-audio" not in repr(envelope), "result envelope repr leaked output handoff")
    _assert(envelope.generation_id == context.generation_id, "result generation identity drift")

    active = VoiceSynthesisActiveGeneration(context=context, work_id=work_id)
    _assert(
        tuple(field.name for field in fields(VoiceSynthesisActiveGeneration)) == ("context", "work_id"),
        "active-generation fields drift",
    )
    active_repr = repr(active).lower()
    for forbidden in ("voiceoutputrequest", "voiceoutputresult", "artifact", "provider", "model", "voice_id"):
        _assert(forbidden not in active_repr, f"active snapshot leaked {forbidden}")

    _assert(
        tuple(item.name for item in VoiceSynthesisCancelOutcome) == (
            "REQUESTED",
            "COMPLETED",
            "TIMED_OUT",
            "NO_ACTIVE_GENERATION",
            "WORK_MISMATCH",
            "ALREADY_TERMINAL",
            "UNSUPPORTED",
            "ALREADY_CLOSED",
            "FAILED",
        ),
        "cancel outcome vocabulary drift",
    )
    _assert(
        tuple(field.name for field in fields(VoiceSynthesisCancelResult)) == (
            "outcome",
            "context",
            "work_id",
            "cooperative_cancel_requested",
            "cooperative_cancel_completed",
            "provider_hard_cancel_applied",
            "provider_hard_cancel_unsupported",
            "artifact_invalidated",
            "future_delivery_suppressed",
            "safe_message",
            "retryable",
            "public_metadata",
        ),
        "cancel-result fields drift",
    )
    cancel = VoiceSynthesisCancelResult(
        outcome=VoiceSynthesisCancelOutcome.REQUESTED,
        context=context,
        work_id=work_id,
        cooperative_cancel_requested=True,
        public_metadata={"api_key": "private-secret", "reason": "safe"},
    )
    _assert(cancel.cooperative_cancel_requested, "cooperative cancel request lost")
    _assert(not cancel.cooperative_cancel_completed, "requested cancel claimed completion")
    _assert(not cancel.provider_hard_cancel_applied, "cooperative cancel implied provider hard cancel")
    _assert(not cancel.provider_hard_cancel_unsupported, "requested cancel implied provider hard-cancel unsupported")
    _assert(not cancel.artifact_invalidated, "requested cancel implied artifact invalidation")
    _assert(not cancel.future_delivery_suppressed, "requested cancel implied future suppression")
    _assert("private-secret" not in repr(dict(cancel.public_metadata)), "cancel metadata leaked secret")
    print("[OK] synthesis identity/result/active/cancel models conform")


def check_protocols() -> None:
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.realtime_capabilities import RealtimeVoiceOutputCapability
    from framework.realtime_stage import RealtimeStageContext
    from framework.realtime_voice_output import (
        VoiceSynthesisProviderAdapter,
        VoiceSynthesisStage,
    )

    adapter_capability = inspect.signature(VoiceSynthesisProviderAdapter.capability)
    adapter_synthesize = inspect.signature(VoiceSynthesisProviderAdapter.synthesize)
    _assert(tuple(adapter_capability.parameters) == ("self",), "adapter capability signature drift")
    _assert(tuple(adapter_synthesize.parameters) == ("self", "request"), "adapter synthesize signature drift")

    hints = get_type_hints(VoiceSynthesisProviderAdapter.synthesize)
    _assert(hints["request"] is VoiceOutputRequest, "adapter request type drift")
    _assert(hints["return"] is VoiceOutputResult, "adapter result type drift")
    cap_hints = get_type_hints(VoiceSynthesisProviderAdapter.capability)
    _assert(cap_hints["return"] is RealtimeVoiceOutputCapability, "adapter capability type drift")

    start = inspect.signature(VoiceSynthesisStage.start)
    cancel = inspect.signature(VoiceSynthesisStage.cancel)
    _assert(tuple(start.parameters) == ("self", "context", "request"), "stage start signature drift")
    _assert(start.parameters["context"].kind is inspect.Parameter.KEYWORD_ONLY, "start context must be keyword-only")
    _assert(start.parameters["request"].kind is inspect.Parameter.KEYWORD_ONLY, "start request must be keyword-only")
    _assert(tuple(cancel.parameters) == ("self", "context", "work_id"), "stage cancel signature drift")
    _assert(cancel.parameters["context"].kind is inspect.Parameter.KEYWORD_ONLY, "cancel context must be keyword-only")
    _assert(cancel.parameters["work_id"].kind is inspect.Parameter.KEYWORD_ONLY, "cancel work_id must be keyword-only")
    _assert(cancel.parameters["work_id"].default is None, "cancel work_id default drift")

    source = (PROJECT_ROOT / "framework/realtime_voice_output.py").read_text(encoding="utf-8")
    adapter_section = source[source.index("class VoiceSynthesisProviderAdapter"):source.index("class VoiceSynthesisStage")]
    for forbidden in ("SessionId", "TurnId", "GenerationId", "SynthesisWorkId", "RealtimeStageContext"):
        _assert(forbidden not in adapter_section, f"provider adapter receives Framework correlation: {forbidden}")

    capability = RealtimeVoiceOutputCapability()
    _assert(not capability.generation_cancel_supported, "default generation cancel overclaim")
    _assert(not capability.provider_hard_cancel_supported, "default provider hard cancel overclaim")
    print("[OK] provider/stage signatures and capability truthfulness conform")


def check_existing_contracts_unchanged() -> None:
    from framework import (
        VoiceOutputRequest,
        VoiceOutputResult,
        VoiceOutputSession,
        VoiceSynthesisRequest,
        VoiceSynthesisResult,
    )
    from framework.realtime_stage import VoiceOutputStage

    for value in (
        VoiceOutputRequest,
        VoiceOutputResult,
        VoiceOutputSession,
        VoiceSynthesisRequest,
        VoiceSynthesisResult,
        VoiceOutputStage,
    ):
        _assert(value is not None, "existing voice-output contract missing")
    print("[OK] existing voice-output/session/stage contracts remain importable")


def check_regressions() -> None:
    for command in (
        [sys.executable, "scripts/smoke_v600_public_api_manifest.py"],
        [sys.executable, "scripts/smoke_v600_version_metadata.py"],
        [sys.executable, "scripts/smoke_app_sdk.py"],
        [sys.executable, "scripts/check_v600_text_chat_compatibility_acceptance.py", "--source-only"],
    ):
        _run(command)
    print("[OK] root-public/version/app SDK/FW-RT6-5c accepted regressions conform")


def check_docs() -> None:
    contract = (PROJECT_ROOT / "docs/v600_realtime_voice_output_contract.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    integration = (PROJECT_ROOT / "docs/app_integration_contract.md").read_text(encoding="utf-8")
    for marker in (
        EXPECTED_BASELINE,
        "framework.realtime_voice_output",
        "fw_synthesis_<32 lowercase hex>",
        "VoiceSynthesisActiveGeneration",
        "VoiceSynthesisProviderAdapter",
        "VoiceSynthesisStage",
        "NO_ACTIVE_GENERATION",
        "WORK_MISMATCH",
        "ALREADY_CLOSED",
        "RealtimeVoiceOutputCapability",
        "DEFERRED / Control B",
        "127 / UNCHANGED",
        "exact change surface:\n5 files",
        "NOT_AUTHORIZED",
    ):
        _assert(marker in contract, f"contract marker missing: {marker}")
    for text in (facade, integration):
        _assert("FW-RT6-6a-A-VOICE-SYNTHESIS-PROTOCOL:BEGIN" in text, "integration doc marker missing")
        _assert("framework.realtime_voice_output" in text, "stable package docs missing")
        _assert("127 / UNCHANGED" in text, "root-public compatibility docs missing")
    print("[OK] Control A contract/public integration docs conform")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()

    if not args.source_only:
        check_git_surface()
    check_stable_package()
    check_source_safety()
    check_models()
    check_protocols()
    check_existing_contracts_unchanged()
    check_regressions()
    check_docs()

    print("v600_rt6_6a_control_a_status: implemented-awaiting-review")
    print("v600_rt6_6a_control_a_exact_surface: 5 files")
    print("v600_rt6_6a_baseline_head: " + EXPECTED_BASELINE)
    print("v600_rt6_6a_stable_package: framework.realtime_voice_output")
    print("v600_rt6_6a_work_id_format: fw_synthesis_<32 lowercase hex>")
    print("v600_rt6_6a_identity: session / turn / generation / work")
    print("v600_rt6_6a_active_generation_fields: context / work_id")
    print("v600_rt6_6a_provider_adapter_receives_framework_ids: False")
    print("v600_rt6_6a_capability_source: RealtimeVoiceOutputCapability")
    print("v600_rt6_6a_provider_hard_cancel_overclaim: False")
    print("v600_rt6_6a_root_public_names: 127 / UNCHANGED")
    print("v600_rt6_6a_existing_voice_output_contracts_changed: False")
    print("v600_rt6_6a_provider_execution: False")
    print("v600_rt6_6a_network_execution: False")
    print("v600_rt6_6a_microphone_access: False")
    print("v600_rt6_6a_playback_execution: False")
    print("v600_rt6_6a_real_vts_execution: False")
    print("v600_rt6_6a_control_b: NOT_AUTHORIZED")
    print("v600_rt6_6a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
