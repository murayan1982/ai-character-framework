"""FW-RT6-3a Control A provider-neutral stage protocol smoke.

Offline/mock-safe: verifies the exact five-file Control A surface, the stable
``framework.realtime_stage`` package, public-safe stage correlation envelopes,
structural fake stage implementations, common method signatures, root-public
compatibility, and provider/runtime import safety without provider, network,
microphone, playback, real VTube Studio, private configuration, DRC repository,
or root-draft stash execution.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
from pathlib import Path
import subprocess
import sys
from typing import Any, get_type_hints

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "6fe95075e1c9ae9e62150eb9844edfe9f004a8e2"
EXPECTED_BASELINE_PARENT = "aee53d77840f49450d9319a1ff5208cec7471757"
EXPECTED_BASELINE_SUBJECT = "docs/test: accept realtime generation gate"

EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_stage_protocol_contract.md",
    "framework/realtime_stage.py",
    "scripts/smoke_v600_realtime_stage_protocols.py",
}

STABLE_PACKAGE_EXPORTS = (
    "RealtimeStageKind",
    "RealtimeStageContext",
    "RealtimeStageResultEnvelope",
    "VoiceInputStage",
    "TextGenerationStage",
    "VoiceOutputStage",
    "MotionStage",
)

PROTOCOL_NAMES = (
    "VoiceInputStage",
    "TextGenerationStage",
    "VoiceOutputStage",
    "MotionStage",
)

FORBIDDEN_IMPORTS = {
    "core.runtime",
    "core.session",
    "core.pipeline",
    "stt.stt_engine",
    "tts.voice_engine",
    "elevenlabs",
    "openai",
    "pyvts",
    "websocket",
    "websockets",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "live2d.vts_client",
}

FORBIDDEN_PUBLIC_PROTOCOL_FRAGMENTS = (
    "providerclient",
    "provider_client",
    "cancelhandle",
    "cancel_handle",
    "rawpayload",
    "raw_payload",
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
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
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] exact five-file Control A surface and baseline conform")


def check_stable_package_shape() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    before = tuple(framework.__all__)
    _assert(before == PUBLIC_API_NAMES, "root-public manifest drift before stage import")
    _assert(len(before) == 121, "Control A must preserve the 121-name root surface")
    _assert(
        not hasattr(framework, "RealtimeStageContext"),
        "Control A must not add stage names to framework root",
    )

    module = importlib.import_module("framework.realtime_stage")
    _assert(
        tuple(module.__all__) == STABLE_PACKAGE_EXPORTS,
        "stable stage package export order drift",
    )
    for name in STABLE_PACKAGE_EXPORTS:
        _assert(hasattr(module, name), f"stable stage package missing {name}")

    _assert(tuple(framework.__all__) == before, "stage import changed root-public names")
    _assert(
        not hasattr(framework, "RealtimeStageContext"),
        "stage package import leaked names into framework root",
    )
    loaded_forbidden = sorted(name for name in FORBIDDEN_IMPORTS if name in sys.modules)
    _assert(
        not loaded_forbidden,
        f"stage package import loaded forbidden runtime/provider modules: {loaded_forbidden}",
    )
    print("[OK] stable public stage package is additive and root-import safe")


def check_context_and_envelope_contract() -> None:
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.realtime_stage import (
        RealtimeStageContext,
        RealtimeStageKind,
        RealtimeStageResultEnvelope,
    )
    from framework.text_chat_result import TextChatResult

    session_id = SessionId.new()
    turn_id = TurnId.new()
    generation_id = GenerationId.new()
    context = RealtimeStageContext(
        session_id=session_id,
        turn_id=turn_id,
        generation_id=generation_id,
        public_metadata={
            "nested": {
                "api_key": "must-not-survive",
                "private_path": "E:\\private\\runtime\\audio.wav",
            },
            "source": "fake",
        },
    )
    _assert(context.session_id is session_id, "session identity changed")
    _assert(context.turn_id is turn_id, "turn identity changed")
    _assert(context.generation_id is generation_id, "generation identity changed")
    nested = context.public_metadata["nested"]
    _assert(isinstance(nested, dict) or hasattr(nested, "__getitem__"), "nested metadata lost")
    _assert(nested["api_key"] == "<redacted>", "nested credential was not redacted")
    _assert(
        nested["private_path"] == "<redacted:path>",
        "private path was not redacted",
    )

    result = TextChatResult.completed("safe fake response")
    envelope = RealtimeStageResultEnvelope(
        stage_kind=RealtimeStageKind.TEXT_GENERATION,
        context=context,
        result=result,
        public_metadata={"token": "secret", "fake": True},
    )
    _assert(envelope.result is result, "stage result identity changed")
    _assert(envelope.session_id is session_id, "envelope session identity drift")
    _assert(envelope.turn_id is turn_id, "envelope turn identity drift")
    _assert(envelope.generation_id is generation_id, "envelope generation identity drift")
    _assert(envelope.public_metadata["token"] == "<redacted>", "envelope secret leaked")
    _assert("safe fake response" not in repr(envelope), "stage result leaked through repr")

    try:
        RealtimeStageResultEnvelope(
            stage_kind=RealtimeStageKind.VOICE_INPUT,
            context=context,
            result=result,
        )
    except TypeError:
        pass
    else:
        raise AssertionError("stage/result type mismatch was accepted")

    for bad in (None, "", "fw_generation_invalid"):
        try:
            RealtimeStageContext(
                session_id=session_id,
                turn_id=turn_id,
                generation_id=bad,  # type: ignore[arg-type]
            )
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError("invalid generation identity was accepted")

    print("[OK] stage context and result envelope preserve safe correlation")


def _protocol_method_shape(protocol: type[Any]) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(inspect.signature(getattr(protocol, method)).parameters)
        for method in ("preflight", "capability", "start", "cancel", "close")
    )


def check_protocol_signatures_and_provider_neutrality() -> None:
    from framework import realtime_stage

    expected_shapes = (
        ("self",),
        ("self",),
        ("self", "context", "request"),
        ("self", "context"),
        ("self",),
    )
    for name in PROTOCOL_NAMES:
        protocol = getattr(realtime_stage, name)
        _assert(
            _protocol_method_shape(protocol) == expected_shapes,
            f"{name} common lifecycle signature drift",
        )
        _assert(isinstance(getattr(protocol, "stage_kind"), property), f"{name}.stage_kind drift")
        annotations: list[str] = []
        for method_name in ("preflight", "capability", "start", "cancel", "close"):
            hints = get_type_hints(getattr(protocol, method_name))
            annotations.extend(str(value).lower() for value in hints.values())
        joined = " ".join(annotations).replace(" ", "")
        for fragment in FORBIDDEN_PUBLIC_PROTOCOL_FRAGMENTS:
            _assert(fragment not in joined, f"{name} exposes provider-specific annotation: {fragment}")

    source = (PROJECT_ROOT / "framework" / "realtime_stage.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_from = {
        (node.module or "").lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    _assert(not imported_roots, f"unexpected absolute imports: {sorted(imported_roots)}")
    for module_name in imported_from:
        for fragment in FORBIDDEN_PUBLIC_PROTOCOL_FRAGMENTS:
            _assert(fragment not in module_name, f"provider module imported: {module_name}")

    _assert("def cancel(self, *, context: RealtimeStageContext) -> bool" in source, "cancel contract drift")
    _assert("def close(self) -> None" in source, "close contract drift")
    print("[OK] four stage protocols share provider-neutral lifecycle signatures")


def check_structural_fake_stages() -> None:
    from framework.audio.voice_output import VoiceOutputRequest, VoiceOutputResult
    from framework.identity import GenerationId, SessionId, TurnId
    from framework.motion import MotionIntent, MotionRequest, MotionResult
    from framework.realtime import RealtimeTurn
    from framework.realtime_capabilities import (
        RealtimeMotionCapability,
        RealtimeVoiceInputCapability,
        RealtimeVoiceOutputCapability,
        RuntimeCapabilityState,
        TextGenerationCapability,
    )
    from framework.realtime_stage import (
        MotionStage,
        RealtimeStageContext,
        RealtimeStageKind,
        RealtimeStageResultEnvelope,
        TextGenerationStage,
        VoiceInputStage,
        VoiceOutputStage,
    )
    from framework.text_chat_result import TextChatResult
    from framework.voice_input import VoiceInputRequest, VoiceInputResult

    runtime = RuntimeCapabilityState(
        configured=True,
        runtime_available=True,
        fake_runtime=True,
        unavailable_reason=None,
    )
    context = RealtimeStageContext(
        session_id=SessionId.new(),
        turn_id=TurnId.new(),
        generation_id=GenerationId.new(),
        public_metadata={"runtime": "fake"},
    )

    class FakeVoiceInput:
        stage_kind = RealtimeStageKind.VOICE_INPUT
        closed = False

        def preflight(self) -> RealtimeVoiceInputCapability:
            return self.capability()

        def capability(self) -> RealtimeVoiceInputCapability:
            return RealtimeVoiceInputCapability(
                runtime=runtime,
                final_transcript_supported=True,
            )

        def start(
            self,
            *,
            context: RealtimeStageContext,
            request: VoiceInputRequest,
        ) -> RealtimeStageResultEnvelope[VoiceInputResult]:
            return RealtimeStageResultEnvelope(
                stage_kind=self.stage_kind,
                context=context,
                result=VoiceInputResult.completed("fake transcript", language=request.language),
            )

        def cancel(self, *, context: RealtimeStageContext) -> bool:
            return not self.closed

        def close(self) -> None:
            self.closed = True

    class FakeTextGeneration:
        stage_kind = RealtimeStageKind.TEXT_GENERATION
        closed = False

        def preflight(self) -> TextGenerationCapability:
            return self.capability()

        def capability(self) -> TextGenerationCapability:
            return TextGenerationCapability(
                runtime=runtime,
                streaming_supported=True,
            )

        def start(
            self,
            *,
            context: RealtimeStageContext,
            request: RealtimeTurn,
        ) -> RealtimeStageResultEnvelope[TextChatResult]:
            return RealtimeStageResultEnvelope(
                stage_kind=self.stage_kind,
                context=context,
                result=TextChatResult.completed(f"fake:{request.input_text}"),
            )

        def cancel(self, *, context: RealtimeStageContext) -> bool:
            return not self.closed

        def close(self) -> None:
            self.closed = True

    class FakeVoiceOutput:
        stage_kind = RealtimeStageKind.VOICE_OUTPUT
        closed = False

        def preflight(self) -> RealtimeVoiceOutputCapability:
            return self.capability()

        def capability(self) -> RealtimeVoiceOutputCapability:
            return RealtimeVoiceOutputCapability(
                runtime=runtime,
                generation_cancel_supported=True,
                audio_formats=("wav",),
            )

        def start(
            self,
            *,
            context: RealtimeStageContext,
            request: VoiceOutputRequest,
        ) -> RealtimeStageResultEnvelope[VoiceOutputResult]:
            return RealtimeStageResultEnvelope(
                stage_kind=self.stage_kind,
                context=context,
                result=VoiceOutputResult(
                    request_state="fake_completed",
                    audio_ready=False,
                    message=f"fake:{len(request.text)}",
                ),
            )

        def cancel(self, *, context: RealtimeStageContext) -> bool:
            return not self.closed

        def close(self) -> None:
            self.closed = True

    class FakeMotion:
        stage_kind = RealtimeStageKind.MOTION
        closed = False

        def preflight(self) -> RealtimeMotionCapability:
            return self.capability()

        def capability(self) -> RealtimeMotionCapability:
            return RealtimeMotionCapability(
                runtime=runtime,
                request_cancel_supported=True,
                provider_neutral_intent_supported=True,
            )

        def start(
            self,
            *,
            context: RealtimeStageContext,
            request: MotionRequest,
        ) -> RealtimeStageResultEnvelope[MotionResult]:
            return RealtimeStageResultEnvelope(
                stage_kind=self.stage_kind,
                context=context,
                result=MotionResult.completed(
                    request=request,
                    session_id=context.session_id,
                ),
            )

        def cancel(self, *, context: RealtimeStageContext) -> bool:
            return not self.closed

        def close(self) -> None:
            self.closed = True

    stages = (
        (FakeVoiceInput(), VoiceInputStage, VoiceInputRequest(language="ja"), VoiceInputResult),
        (
            FakeTextGeneration(),
            TextGenerationStage,
            RealtimeTurn(
                session_id=context.session_id,
                turn_id=context.turn_id,
                input_text="hello",
            ),
            TextChatResult,
        ),
        (FakeVoiceOutput(), VoiceOutputStage, VoiceOutputRequest(text="hello"), VoiceOutputResult),
        (FakeMotion(), MotionStage, MotionRequest(intent=MotionIntent.IDLE_MOTION), MotionResult),
    )

    for stage, protocol, request, result_type in stages:
        _assert(isinstance(stage, protocol), f"{protocol.__name__} structural fake failed")
        preflight = stage.preflight()
        capability = stage.capability()
        _assert(preflight.runtime.fake_runtime, "fake preflight did not report fake runtime")
        _assert(capability.runtime.fake_runtime, "fake capability did not report fake runtime")
        envelope = stage.start(context=context, request=request)
        _assert(envelope.context is context, "fake stage lost context identity")
        _assert(isinstance(envelope.result, result_type), "fake stage result type drift")
        _assert(stage.cancel(context=context) is True, "fake stage cancel was not accepted")
        stage.close()
        stage.close()
        _assert(stage.cancel(context=context) is False, "closed fake stage accepted cancellation")

    print("[OK] structural fake stages satisfy all four protocol contracts")


def _load_script(relative_path: str, module_name: str) -> Any:
    path = PROJECT_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"could not load regression script: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_prior_runtime_regressions() -> None:
    generation = _load_script(
        "scripts/check_v600_realtime_generation_gate_acceptance.py",
        "_rt6_3a_generation_regression",
    )
    for name in (
        "check_source_contract",
        "check_public_compatibility",
        "check_aggregate_docs",
        "check_historical_runtime_behavior",
        "check_manifest_and_version_gates",
        "check_import_safety",
    ):
        getattr(generation, name)()

    terminal = _load_script(
        "scripts/check_v600_realtime_terminal_registry_acceptance.py",
        "_rt6_3a_terminal_regression",
    )
    for name in (
        "check_source_contract",
        "check_public_compatibility",
        "check_aggregate_docs",
        "check_historical_runtime_behavior",
        "check_import_safety",
    ):
        getattr(terminal, name)()

    print("[OK] accepted generation and terminal runtime behavior remains conformant")


def check_docs_and_deferred_boundaries() -> None:
    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_stage_protocol_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "FW-RT6-3a Control A",
        "framework.realtime_stage",
        "RealtimeStageContext",
        "RealtimeStageResultEnvelope",
        "VoiceInputStage",
        "TextGenerationStage",
        "VoiceOutputStage",
        "MotionStage",
        "RealtimeSession injection: DEFERRED / Control B",
        "root-public names: 121 / UNCHANGED",
        "provider / network / microphone / playback / real VTS execution: False",
        "DRC repository accessed or changed: False",
        "root-draft stash accessed or changed: False",
        "Control B: NOT_AUTHORIZED",
        "commit / push: NOT_AUTHORIZED",
    ):
        _assert(phrase in contract, f"stage contract missing: {phrase}")

    for relative in ("docs/public_facade.md", "docs/app_integration_contract.md"):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-3a-A-STAGE-PROTOCOL-FOUNDATION:BEGIN" in text
            and "FW-RT6-3a-A-STAGE-PROTOCOL-FOUNDATION:END" in text,
            f"{relative} stage protocol marker missing",
        )
        _assert(
            "stable public package" in text
            and "RealtimeSession injection" in text,
            f"{relative} stable-package/deferred boundary missing",
        )

    tasklist = (PROJECT_ROOT / "docs" / "v600_tasklist.md").read_text(encoding="utf-8")
    _assert(
        "next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED" in tasklist,
        "accepted baseline tasklist marker drift",
    )
    _assert("- [ ] `VoiceInputStage` protocol" in tasklist, "Control A over-synced aggregate tasklist")
    print("[OK] docs record Control A without overclaiming injection or aggregate acceptance")


def check_prior_public_compatibility() -> None:
    commands = (
        "scripts/smoke_v600_public_api_manifest.py",
        "scripts/smoke_v600_version_metadata.py",
        "scripts/smoke_public_facade.py",
        "scripts/smoke_app_sdk.py",
    )
    for relative in commands:
        completed = subprocess.run(
            [sys.executable, relative],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        _assert(
            completed.returncode == 0,
            f"prior compatibility smoke failed: {relative}\n{completed.stdout}{completed.stderr}",
        )
    print("[OK] root-public, version, facade, and app SDK compatibility remain conformant")


def main() -> None:
    check_repository_contract()
    check_stable_package_shape()
    check_context_and_envelope_contract()
    check_protocol_signatures_and_provider_neutrality()
    check_structural_fake_stages()
    check_docs_and_deferred_boundaries()
    check_prior_public_compatibility()
    check_prior_runtime_regressions()
    print("v600_rt6_3a_control_a_status: implemented-awaiting-review")
    print("v600_rt6_3a_control_a_exact_change_surface_count: 5")
    print("v600_rt6_3a_control_a_stable_public_package: framework.realtime_stage")
    print("v600_rt6_3a_control_a_root_public_names: 121 / unchanged")
    print("v600_rt6_3a_control_a_stage_protocol_count: 4")
    print("v600_rt6_3a_control_a_common_methods: preflight/capability/start/cancel/close")
    print("v600_rt6_3a_control_a_stage_context: session/turn/generation")
    print("v600_rt6_3a_control_a_result_repr_exposes_value: False")
    print("v600_rt6_3a_control_a_provider_specific_public_objects: False")
    print("v600_rt6_3a_control_a_realtime_session_injection: deferred-control-b")
    print("v600_rt6_3a_control_a_real_orchestration: False")
    print("v600_rt6_3a_control_a_provider_network_microphone_playback_real_vts_execution: False")
    print("v600_rt6_3a_control_a_drc_repository_accessed_or_changed: False")
    print("v600_rt6_3a_control_a_root_draft_stash_accessed_or_changed: False")
    print("v600_rt6_3a_control_b_authorized: False")
    print("[OK] FW-RT6-3a Control A provider-neutral stage protocol foundation conforms")


if __name__ == "__main__":
    main()
