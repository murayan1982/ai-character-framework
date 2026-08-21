"""Provider-free aggregate conformance tests for FW-RT6-14a.

Each test maps one-to-one to the twelve canonical FW-RT6-14a tasks.  The
suite executes only deterministic Framework boundaries and source contracts;
it never imports provider SDKs or performs network, microphone, playback, or
VTube Studio work.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import framework
from framework.audio.voice_output import VoiceOutputRequest
from framework.identity import GenerationId, SessionId, TurnId
from framework.interrupt_coordination import (
    InterruptAggregateOutcome,
    InterruptAggregateResult,
    InterruptSubsystem,
    InterruptSubsystemOutcome,
    InterruptSubsystemResult,
)
from framework.lifecycle import TurnOutcome
from framework.public_safety import (
    REDACTED_BINARY,
    REDACTED_EXCEPTION,
    REDACTED_PATH,
    REDACTED_VALUE,
    public_mapping,
)
from framework.realtime import RealtimeEventType
from framework.realtime_generation_gate import (
    GenerationAdvanceReason,
    RealtimeGenerationGate,
    RealtimeStageCompletionEnvelope,
    StaleCompletionReason,
)
from framework.realtime_stage import RealtimeStageContext
from framework.realtime_terminal_registry import (
    RealtimeTerminalRegistry,
    TerminalCommitStatus,
)
from framework.realtime_voice_output_queue import (
    BoundedVoiceSynthesisPendingQueue,
    VoiceSynthesisEnqueueOutcome,
    VoiceSynthesisPendingClearOutcome,
)
from framework.session_compatibility import (
    CompatibilityWarningMode,
    SessionCompatibilityMode,
    StandaloneSessionKind,
    build_session_compatibility_profile,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ROOT_MANIFEST_PATH = PROJECT_ROOT / "docs/v600_root_public_api_manifest.json"
ROOT_MANIFEST_FILE_SHA256 = (
    "e3c7bb1d2b0646d2ecec9aadf3df8c0af1329622500652daddbb3c85113d01ef"
)
ROOT_PUBLIC_SHA256 = (
    "4b0c5a17621879fac7bb9f82c85f1bb722ce36a46e534be1179b6ae3e985dbf0"
)
FORBIDDEN_PROVIDER_MODULES = {
    "openai",
    "elevenlabs",
    "pyvts",
    "websocket",
    "websockets",
    "sounddevice",
    "pyaudio",
    "live2d.vts_client",
    "tts.voice_engine",
}


def _digest_names(names: tuple[str, ...]) -> str:
    payload = "".join(f"{name}\n" for name in names).encode("utf-8")
    return sha256(payload).hexdigest()


class AggregateConformanceTests(unittest.TestCase):
    def test_01_root_public_manifest_gate(self) -> None:
        from framework.public_api import PUBLIC_API_NAMES, V6_ROOT_PUBLIC_EXPORTS

        manifest_bytes = ROOT_MANIFEST_PATH.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        self.assertEqual(sha256(manifest_bytes).hexdigest(), ROOT_MANIFEST_FILE_SHA256)
        self.assertEqual(len(PUBLIC_API_NAMES), 127)
        self.assertEqual(tuple(framework.__all__), PUBLIC_API_NAMES)
        self.assertEqual(V6_ROOT_PUBLIC_EXPORTS, tuple(sorted(PUBLIC_API_NAMES)))
        self.assertEqual(_digest_names(V6_ROOT_PUBLIC_EXPORTS), ROOT_PUBLIC_SHA256)
        self.assertEqual(manifest["root_public_exports"], list(V6_ROOT_PUBLIC_EXPORTS))
        self.assertEqual(manifest["root_public_sha256"], ROOT_PUBLIC_SHA256)

    def test_02_import_safety_gate(self) -> None:
        code = r'''
import importlib.util
import pathlib
import sys
before = set(sys.modules)
import framework
import framework.guarded_real_runtime
path = pathlib.Path("scripts/check_v600_aggregate_conformance.py")
spec = importlib.util.spec_from_file_location("_fwrt6_14a_gate", path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
loaded = set(sys.modules) - before
for name in (
    "openai", "elevenlabs", "pyvts", "websocket", "websockets",
    "sounddevice", "pyaudio", "live2d.vts_client", "tts.voice_engine",
):
    if name in loaded:
        raise AssertionError(name)
'''
        environment = dict(os.environ)
        for key in tuple(environment):
            if any(fragment in key.casefold() for fragment in ("key", "secret", "token")):
                environment.pop(key, None)
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_03_capability_truthfulness_gate(self) -> None:
        session = framework.create_realtime_session()
        try:
            snapshot = session.capabilities
            self.assertFalse(snapshot.real_runtime_enabled)
            self.assertFalse(snapshot.hard_cancel_supported)
            self.assertFalse(snapshot.tts_queue_flush_supported)
            self.assertFalse(snapshot.motion.runtime.configured)
            self.assertFalse(snapshot.motion.runtime.runtime_available)
            self.assertTrue(snapshot.text_generation.runtime.fake_runtime)
            self.assertFalse(snapshot.text_generation.runtime.real_runtime)
            self.assertFalse(snapshot.public_metadata["provider_execution_performed"])

            natural = session.natural_turn_capabilities.capabilities
            self.assertEqual(len(natural), 7)
            self.assertTrue(all(not item.supported for item in natural))
            self.assertTrue(all(item.experimental for item in natural))
            self.assertTrue(all(item.explicit_activation_required for item in natural))
            self.assertTrue(all(not item.provider_execution for item in natural))
        finally:
            session.close()

    def test_04_event_ordering_gate(self) -> None:
        session = framework.create_realtime_session()
        try:
            result = session.run_turn(input_text="aggregate-ordering")
            history = session.event_history
            self.assertIs(result.outcome, TurnOutcome.COMPLETED)
            self.assertEqual(tuple(int(event.sequence) for event in history), tuple(range(1, 10)))
            self.assertEqual(
                tuple(event.type for event in history),
                (
                    RealtimeEventType.TURN_STARTED,
                    RealtimeEventType.LISTENING_STARTED,
                    RealtimeEventType.LISTENING_COMPLETED,
                    RealtimeEventType.TRANSCRIPT_FINAL,
                    RealtimeEventType.RESPONSE_STARTED,
                    RealtimeEventType.RESPONSE_COMPLETED,
                    RealtimeEventType.SYNTHESIS_STARTED,
                    RealtimeEventType.SYNTHESIS_COMPLETED,
                    RealtimeEventType.TURN_COMPLETED,
                ),
            )
            self.assertTrue(all(event.turn_id == result.turn_id for event in history))
            self.assertTrue(
                all(event.generation_id == result.generation_id for event in history)
            )
        finally:
            session.close()

    def test_05_exactly_once_terminal_gate(self) -> None:
        registry: RealtimeTerminalRegistry[str] = RealtimeTerminalRegistry()
        turn_id = TurnId.new()
        first = registry.commit(turn_id, TurnOutcome.COMPLETED, result="first")
        duplicate = registry.commit(turn_id, TurnOutcome.COMPLETED, result="second")

        self.assertTrue(first.accepted)
        self.assertIs(first.status, TerminalCommitStatus.FIRST_TERMINAL)
        self.assertFalse(duplicate.accepted)
        self.assertIs(duplicate.status, TerminalCommitStatus.DUPLICATE_TERMINAL)
        self.assertEqual(duplicate.record.result, "first")
        self.assertEqual(len(registry.records), 1)
        self.assertEqual(registry.diagnostics.terminal_commit_count, 1)
        self.assertEqual(registry.diagnostics.duplicate_terminal_count, 1)

    def test_06_stale_rejection_gate(self) -> None:
        gate: RealtimeGenerationGate[str] = RealtimeGenerationGate()
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        envelope = RealtimeStageCompletionEnvelope(
            turn_id=turn_id,
            generation_id=generation_id,
            stage="text_generation",
            value="must-not-deliver",
        )
        self.assertEqual(gate.advance(GenerationAdvanceReason.INTERRUPT), generation_id)
        delivered: list[str] = []
        decision = gate.apply_completion(envelope, deliver=delivered.append)

        self.assertFalse(decision.accepted)
        self.assertIs(decision.stale_reason, StaleCompletionReason.RETIRED_GENERATION)
        self.assertIs(decision.retired_by, GenerationAdvanceReason.INTERRUPT)
        self.assertEqual(delivered, [])
        self.assertEqual(gate.diagnostics["stale_completion_count"], 1)

    def test_07_interrupt_reach_gate(self) -> None:
        session_id = SessionId.new()
        turn_id = TurnId.new()
        generation_id = GenerationId.new()
        results = tuple(
            InterruptSubsystemResult(
                subsystem=subsystem,
                outcome=InterruptSubsystemOutcome.UNSUPPORTED,
                session_id=session_id,
                turn_id=turn_id,
                generation_id=generation_id,
                target_reached=True,
                safe_message="The provider-neutral target was reached but is unsupported.",
            )
            for subsystem in InterruptSubsystem
        )
        aggregate = InterruptAggregateResult.from_results(
            session_id=session_id,
            turn_id=turn_id,
            subsystem_results=results,
        )

        self.assertEqual(len(results), 5)
        self.assertEqual({item.subsystem for item in results}, set(InterruptSubsystem))
        self.assertTrue(all(item.target_reached for item in results))
        self.assertTrue(all(not item.provider_hard_cancel_applied for item in results))
        self.assertIs(aggregate.outcome, InterruptAggregateOutcome.UNSUPPORTED)
        self.assertTrue(aggregate.is_terminal)

    def test_08_tts_work_control_gate(self) -> None:
        queue = BoundedVoiceSynthesisPendingQueue(max_pending_depth=1)
        context = RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
        first = queue.enqueue(
            context=context,
            request=VoiceOutputRequest(text="aggregate-tts"),
        )
        overflow = queue.enqueue(
            context=context,
            request=VoiceOutputRequest(text="aggregate-overflow"),
        )
        cleared = queue.clear_pending(context=context)

        self.assertIs(first.outcome, VoiceSynthesisEnqueueOutcome.ACCEPTED)
        self.assertIs(overflow.outcome, VoiceSynthesisEnqueueOutcome.REJECTED_FULL)
        self.assertIs(cleared.outcome, VoiceSynthesisPendingClearOutcome.CLEARED)
        self.assertEqual(cleared.cleared_count, 1)
        self.assertFalse(cleared.active_generation_cancelled)
        self.assertEqual(queue.pending_count, 0)
        self.assertEqual(queue.overflow_count, 1)

    def test_09_security_redaction_gate(self) -> None:
        secret = "aggregate-private-secret"
        safe = public_mapping(
            {
                "api_key": secret,
                "nested": {
                    "token": secret,
                    "path": r"C:\\Users\\private\\evidence.json",
                    "binary": b"private-audio",
                    "error": RuntimeError(secret),
                },
            }
        )

        self.assertEqual(safe["api_key"], REDACTED_VALUE)
        self.assertEqual(safe["nested"]["token"], REDACTED_VALUE)
        self.assertEqual(safe["nested"]["path"], REDACTED_PATH)
        self.assertEqual(safe["nested"]["binary"], REDACTED_BINARY)
        self.assertEqual(safe["nested"]["error"], REDACTED_EXCEPTION)
        self.assertNotIn(secret, repr(safe))

    def test_10_compatibility_gate(self) -> None:
        profiles = {
            kind: build_session_compatibility_profile(kind)
            for kind in StandaloneSessionKind
        }
        self.assertEqual(len(profiles), 5)
        self.assertTrue(
            all(profile.warning_mode is CompatibilityWarningMode.SILENT for profile in profiles.values())
        )
        self.assertTrue(all(profile.factory_signature_preserved for profile in profiles.values()))
        self.assertTrue(all(not profile.runtime_execution_performed for profile in profiles.values()))
        self.assertIs(
            profiles[StandaloneSessionKind.REALTIME].mode,
            SessionCompatibilityMode.V5_SKELETON,
        )
        self.assertTrue(
            all(
                profile.mode is SessionCompatibilityMode.V5_STANDALONE
                for kind, profile in profiles.items()
                if kind is not StandaloneSessionKind.REALTIME
            )
        )

    def test_11_full_unit_suite_gate_contract(self) -> None:
        from scripts import check_v600_aggregate_conformance as gate

        self.assertEqual(gate.UNIT_TEST_PATTERN, "test*.py")
        self.assertEqual(gate.EXPECTED_DEDICATED_TEST_COUNT, 12)
        self.assertEqual(gate.EXPECTED_FULL_UNIT_COUNT, 828)
        self.assertTrue(callable(gate.run_full_unit_suite))

    def test_12_full_smoke_suite_gate_contract(self) -> None:
        from scripts import check_v600_aggregate_conformance as gate

        smoke_files = tuple(sorted((PROJECT_ROOT / "scripts").glob("smoke_v600_*.py")))
        self.assertEqual(len(smoke_files), gate.EXPECTED_TRACKED_SMOKE_FILE_COUNT)
        self.assertEqual(len(gate.CURRENT_SMOKE_COMMANDS), 11)
        self.assertEqual(len(set(gate.CURRENT_SMOKE_COMMANDS)), 11)
        for relative_path, arguments in gate.CURRENT_SMOKE_COMMANDS:
            self.assertTrue((PROJECT_ROOT / relative_path).is_file(), relative_path)
            self.assertIsInstance(arguments, tuple)
        self.assertEqual(
            len(smoke_files) - len(gate.CURRENT_STANDALONE_SMOKE_FILES),
            gate.EXPECTED_HISTORICAL_SMOKE_FILE_COUNT,
        )


if __name__ == "__main__":
    unittest.main()
