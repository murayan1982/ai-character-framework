from __future__ import annotations

import inspect
import unittest

import framework
from framework.identity import GenerationId, SessionId, TurnId
from framework.realtime import RealtimeTurn
from framework.realtime_capabilities import TextGenerationCapability
from framework.realtime_stage import RealtimeStageContext, RealtimeStageKind, TextGenerationStage
from framework.realtime_text_generation import (
    CancelableTextGenerationStage,
    ProviderNeutralTextGenerationStream,
    TextGenerationCancelReason,
    TextGenerationCancellationToken,
    TextGenerationStream,
)


CONTROL_B_EXPORT_PREFIX = (
    "TextGenerationCancelReason",
    "TextGenerationCancellationToken",
    "TextGenerationDeltaEnvelope",
    "TextGenerationStreamCloseOutcome",
    "TextGenerationStreamCloseResult",
    "TextGenerationCompletedTurn",
    "TextGenerationHistorySink",
    "TextGenerationStream",
    "ProviderNeutralTextGenerationStream",
)

LEGACY_STAGE_EXPORTS = (
    "RealtimeStageKind",
    "RealtimeStageContext",
    "RealtimeStageResultEnvelope",
    "VoiceInputStage",
    "TextGenerationStage",
    "VoiceOutputStage",
    "MotionStage",
)


class _LegacyTextGenerationStage:
    @property
    def stage_kind(self):
        return RealtimeStageKind.TEXT_GENERATION

    def preflight(self):
        return TextGenerationCapability()

    def capability(self):
        return TextGenerationCapability()

    def start(self, *, context, request):
        raise NotImplementedError

    def cancel(self, *, context):
        return True

    def close(self):
        return None


class _CancelableStage:
    def __init__(self, capability: TextGenerationCapability) -> None:
        self._capability = capability
        self.open_calls = 0
        self.close_calls = 0
        self.last_context = None
        self.last_request = None
        self.last_token = None

    @property
    def stage_kind(self):
        return RealtimeStageKind.TEXT_GENERATION

    def preflight(self):
        return self._capability

    def capability(self):
        return self._capability

    def open_stream(self, *, context, request, cancellation_token):
        self.open_calls += 1
        self.last_context = context
        self.last_request = request
        self.last_token = cancellation_token
        return ProviderNeutralTextGenerationStream(
            context=context,
            capability=self._capability,
            source=iter((('first', ()), ('second', ()))),
            user_input=request.input_text,
            cancellation_token=cancellation_token,
        )

    def close(self):
        self.close_calls += 1


class CancelableTextGenerationStageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = RealtimeStageContext(
            session_id=SessionId.new(),
            turn_id=TurnId.new(),
            generation_id=GenerationId.new(),
        )
        self.turn = RealtimeTurn(
            turn_id=self.context.turn_id,
            session_id=self.context.session_id,
            input_text="hidden input",
        )
        self.capability = TextGenerationCapability(
            streaming_supported=True,
            cooperative_cancel_supported=True,
            provider_hard_cancel_supported=False,
        )

    def test_control_c_adds_one_stable_package_suffix_only(self) -> None:
        import framework.realtime_text_generation as module

        self.assertEqual(tuple(module.__all__[:9]), CONTROL_B_EXPORT_PREFIX)
        self.assertEqual(module.__all__[9], "CancelableTextGenerationStage")

    def test_root_public_surface_remains_127_and_has_no_stage_name(self) -> None:
        self.assertEqual(len(framework.__all__), 127)
        self.assertNotIn("CancelableTextGenerationStage", framework.__all__)

    def test_existing_realtime_stage_exports_remain_exactly_unchanged(self) -> None:
        import framework.realtime_stage as stage_module

        self.assertEqual(tuple(stage_module.__all__), LEGACY_STAGE_EXPORTS)
        self.assertNotIn("CancelableTextGenerationStage", stage_module.__all__)

    def test_existing_text_generation_stage_contract_remains_legacy_compatible(self) -> None:
        legacy = _LegacyTextGenerationStage()
        self.assertIsInstance(legacy, TextGenerationStage)
        self.assertFalse(isinstance(legacy, CancelableTextGenerationStage))
        self.assertEqual(
            tuple(inspect.signature(TextGenerationStage.start).parameters),
            ("self", "context", "request"),
        )
        self.assertEqual(
            tuple(inspect.signature(TextGenerationStage.cancel).parameters),
            ("self", "context"),
        )

    def test_cancelable_stage_is_structurally_runtime_checkable(self) -> None:
        stage = _CancelableStage(self.capability)
        self.assertIsInstance(stage, CancelableTextGenerationStage)
        self.assertFalse(isinstance(stage, TextGenerationStage))

    def test_open_stream_uses_keyword_only_context_request_and_token(self) -> None:
        signature = inspect.signature(CancelableTextGenerationStage.open_stream)
        self.assertEqual(
            tuple(signature.parameters),
            ("self", "context", "request", "cancellation_token"),
        )
        for name in ("context", "request", "cancellation_token"):
            self.assertIs(
                signature.parameters[name].kind,
                inspect.Parameter.KEYWORD_ONLY,
            )

    def test_open_stream_preserves_context_request_token_and_capability(self) -> None:
        stage = _CancelableStage(self.capability)
        token = TextGenerationCancellationToken()
        stream = stage.open_stream(
            context=self.context,
            request=self.turn,
            cancellation_token=token,
        )
        self.assertIsInstance(stream, TextGenerationStream)
        self.assertEqual(stage.last_context, self.context)
        self.assertEqual(stage.last_request, self.turn)
        self.assertIs(stage.last_token, token)
        self.assertIs(stream.cancellation_token, token)
        self.assertIs(stage.capability(), self.capability)
        self.assertIs(stream.capability, self.capability)

    def test_capability_is_single_hard_cancel_source_of_truth(self) -> None:
        stage = _CancelableStage(self.capability)
        token = TextGenerationCancellationToken()
        stream = stage.open_stream(
            context=self.context,
            request=self.turn,
            cancellation_token=token,
        )
        self.assertFalse(stage.capability().provider_hard_cancel_supported)
        self.assertFalse(stream.capability.provider_hard_cancel_supported)
        self.assertTrue(stream.request_cancel(TextGenerationCancelReason.INTERRUPT))
        self.assertFalse(stream.capability.provider_hard_cancel_supported)

    def test_stage_stream_cancel_suppresses_future_deltas(self) -> None:
        stage = _CancelableStage(self.capability)
        token = TextGenerationCancellationToken()
        stream = stage.open_stream(
            context=self.context,
            request=self.turn,
            cancellation_token=token,
        )
        self.assertEqual(next(stream).text, "first")
        self.assertTrue(token.request_cancel(TextGenerationCancelReason.INTERRUPT))
        self.assertEqual(list(stream), [])
        self.assertEqual(stream.delivered_delta_count, 1)

    def test_stage_close_is_independent_of_stream_hard_cancel_claims(self) -> None:
        stage = _CancelableStage(self.capability)
        token = TextGenerationCancellationToken()
        stream = stage.open_stream(
            context=self.context,
            request=self.turn,
            cancellation_token=token,
        )
        stage.close()
        self.assertEqual(stage.close_calls, 1)
        self.assertFalse(stream.capability.provider_hard_cancel_supported)
        stream.close()


if __name__ == "__main__":
    unittest.main()
