"""Private session-owned audio-chunk ordering and limit runtime."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Mapping
from uuid import uuid4

from .backpressure import (
    BackpressureAdmissionResult,
    BackpressureBoundary,
    BackpressureCapability,
    BackpressureControlResult,
    BackpressureOverflowEvent,
    BackpressureRejectionCode,
    BackpressureSnapshot,
)
from .backpressure_runtime import BoundedBackpressureRuntime
from .voice_input import VoiceInputResult
from .voice_input_streaming import (
    VoiceInputAudioChunk,
    VoiceInputStreamAbort,
    VoiceInputStreamConfig,
    VoiceInputStreamEnd,
    VoiceInputStreamOperationKind,
    VoiceInputStreamOperationResult,
    VoiceInputStreamRejectionCode,
    VoiceInputStreamingCapability,
)
from .voice_input_streaming_adapter import VoiceInputStreamingAdapter


PartialDelivery = Callable[[str, int, str, float | None], None]


@dataclass(slots=True)
class _ActiveStream:
    config: VoiceInputStreamConfig
    expected_sequence_number: int = 0
    duration_ms: int = 0


class VoiceInputStreamRuntime:
    """Validate ordered streams with bounded audio-input admission."""

    def __init__(
        self,
        *,
        on_partial: PartialDelivery,
        on_backpressure_overflow: Callable[[BackpressureOverflowEvent], None]
        | None = None,
        maximum_in_flight_audio_chunks: int = 1,
    ) -> None:
        self._on_partial = on_partial
        self._adapter: VoiceInputStreamingAdapter | None = None
        self._capability = VoiceInputStreamingCapability()
        self._active: _ActiveStream | None = None
        self._last_terminal: tuple[str, str] | None = None
        self._closed = False
        self._lock = RLock()
        self._audio_backpressure = BoundedBackpressureRuntime(
            boundary=BackpressureBoundary.AUDIO_INPUT,
            maximum_pending_count=1,
            maximum_in_flight_count=maximum_in_flight_audio_chunks,
            on_overflow=on_backpressure_overflow,
            public_metadata={
                "owner": "VoiceInputStreamRuntime",
                "payload_retained": False,
            },
        )

    @property
    def capability(self) -> VoiceInputStreamingCapability:
        with self._lock:
            return self._capability

    @property
    def active_stream_id(self) -> str | None:
        with self._lock:
            return self._active.config.stream_id if self._active is not None else None

    @property
    def backpressure_capability(self) -> BackpressureCapability:
        return self._audio_backpressure.capability

    @property
    def backpressure_snapshot(self) -> BackpressureSnapshot:
        return self._audio_backpressure.snapshot

    @property
    def last_backpressure_result(self) -> BackpressureAdmissionResult | None:
        return self._audio_backpressure.last_rejection

    def pause_backpressure(self) -> BackpressureControlResult:
        return self._audio_backpressure.pause()

    def resume_backpressure(self) -> BackpressureControlResult:
        return self._audio_backpressure.resume()

    def configure(self, adapter: VoiceInputStreamingAdapter) -> VoiceInputStreamingCapability:
        required = (
            "streaming_capability",
            "begin_stream",
            "accept_chunk",
            "finish_stream",
            "abort_stream",
        )
        if any(not hasattr(adapter, name) for name in required):
            raise TypeError("adapter must implement VoiceInputStreamingAdapter")
        capability = adapter.streaming_capability
        if not isinstance(capability, VoiceInputStreamingCapability):
            raise TypeError("adapter streaming_capability has the wrong type")
        if not capability.audio_chunk_input_supported:
            raise ValueError("configured adapter must support audio chunk input")
        if not capability.partial_transcript_supported:
            raise ValueError("Control B adapter must support partial transcripts")
        with self._lock:
            if self._closed:
                raise RuntimeError("Voice input stream runtime is closed.")
            if self._active is not None:
                raise RuntimeError("Cannot reconfigure an active audio stream.")
            self._adapter = adapter
            self._capability = capability
            return capability

    def begin(self, config: VoiceInputStreamConfig) -> bool:
        if not isinstance(config, VoiceInputStreamConfig):
            raise TypeError("config must be VoiceInputStreamConfig")
        with self._lock:
            adapter = self._adapter
            if self._closed or adapter is None or self._active is not None:
                return False
            if config.audio_format.encoding not in self._capability.accepted_audio_formats:
                return False
            try:
                adapter.begin_stream(config)
            except Exception:
                return False
            self._active = _ActiveStream(config=config)
            self._last_terminal = None
            return True

    @staticmethod
    def _rejected(
        *,
        kind: VoiceInputStreamOperationKind,
        stream_id: str,
        code: VoiceInputStreamRejectionCode,
        message: str,
        sequence_number: int | None = None,
        next_expected: int | None = None,
        retryable: bool = False,
        terminal: bool = False,
        public_metadata: Mapping[str, object] | None = None,
    ) -> VoiceInputStreamOperationResult:
        return VoiceInputStreamOperationResult(
            kind=kind,
            accepted=False,
            stream_id=stream_id,
            rejection_code=code,
            safe_message=message,
            sequence_number=sequence_number,
            next_expected_sequence_number=next_expected,
            retryable=retryable,
            terminal=terminal,
            public_metadata=public_metadata or {},
        )

    def _terminal_rejection(
        self,
        *,
        kind: VoiceInputStreamOperationKind,
        stream_id: str,
        sequence_number: int | None,
    ) -> VoiceInputStreamOperationResult | None:
        if self._last_terminal is None or self._last_terminal[0] != stream_id:
            return None
        state = self._last_terminal[1]
        code = (
            VoiceInputStreamRejectionCode.ALREADY_ENDED
            if state == "ended"
            else VoiceInputStreamRejectionCode.ALREADY_ABORTED
        )
        return self._rejected(
            kind=kind,
            stream_id=stream_id,
            code=code,
            message=f"Audio stream has already {state}.",
            sequence_number=sequence_number,
            terminal=True,
        )

    @staticmethod
    def _abort_adapter_safely(
        adapter: VoiceInputStreamingAdapter,
        *,
        stream_id: str,
        last_sequence_number: int | None,
        reason: str,
    ) -> None:
        """Best-effort adapter cleanup without exposing provider exceptions."""

        try:
            adapter.abort_stream(
                VoiceInputStreamAbort(
                    stream_id=stream_id,
                    reason=reason,
                    last_sequence_number=last_sequence_number,
                )
            )
        except Exception:
            pass

    def send(self, chunk: VoiceInputAudioChunk) -> VoiceInputStreamOperationResult:
        """Admit one chunk without waiting when the in-flight slot is occupied."""

        if not isinstance(chunk, VoiceInputAudioChunk):
            raise TypeError("chunk must be VoiceInputAudioChunk")
        item_id = f"audio_{uuid4().hex}"
        admission = self._audio_backpressure.admit_item(
            item_id,
            start_immediately=True,
            public_metadata={
                "stream_id": chunk.stream_id,
                "sequence_number": chunk.sequence_number,
            },
        )
        if not admission.accepted:
            closed = admission.rejection_code is BackpressureRejectionCode.CLOSED
            return self._rejected(
                kind=chunk.kind,
                stream_id=chunk.stream_id,
                code=(
                    VoiceInputStreamRejectionCode.SESSION_CLOSED
                    if closed
                    else VoiceInputStreamRejectionCode.NOT_SUPPORTED
                ),
                message=(
                    "Voice input session is closed."
                    if closed
                    else "Audio input backpressure rejected the chunk."
                ),
                sequence_number=chunk.sequence_number,
                retryable=admission.retryable,
                terminal=closed,
                public_metadata={
                    "boundary": BackpressureBoundary.AUDIO_INPUT.value,
                    "backpressure_rejection_code": admission.rejection_code.value,
                    "dropped": admission.dropped,
                },
            )
        try:
            return self._send_admitted(chunk)
        finally:
            if not self._audio_backpressure.complete(item_id):
                raise AssertionError("accepted audio admission lost in-flight ownership")

    def _send_admitted(
        self,
        chunk: VoiceInputAudioChunk,
    ) -> VoiceInputStreamOperationResult:
        if not isinstance(chunk, VoiceInputAudioChunk):
            raise TypeError("chunk must be VoiceInputAudioChunk")
        with self._lock:
            if self._closed:
                return self._rejected(
                    kind=chunk.kind,
                    stream_id=chunk.stream_id,
                    code=VoiceInputStreamRejectionCode.SESSION_CLOSED,
                    message="Voice input session is closed.",
                    sequence_number=chunk.sequence_number,
                    terminal=True,
                )
            terminal = self._terminal_rejection(
                kind=chunk.kind,
                stream_id=chunk.stream_id,
                sequence_number=chunk.sequence_number,
            )
            if terminal is not None:
                return terminal
            active = self._active
            adapter = self._adapter
            if active is None or adapter is None or chunk.stream_id != active.config.stream_id:
                return self._rejected(
                    kind=chunk.kind,
                    stream_id=chunk.stream_id,
                    code=VoiceInputStreamRejectionCode.INVALID_STREAM_ID,
                    message="Audio stream is not active.",
                    sequence_number=chunk.sequence_number,
                )
            expected = active.expected_sequence_number
            if chunk.sequence_number != expected:
                return self._rejected(
                    kind=chunk.kind,
                    stream_id=chunk.stream_id,
                    code=VoiceInputStreamRejectionCode.OUT_OF_ORDER,
                    message="Audio chunk sequence is out of order.",
                    sequence_number=chunk.sequence_number,
                    next_expected=expected,
                    retryable=True,
                )
            if chunk.byte_count > (self._capability.maximum_chunk_size_bytes or 0):
                return self._rejected(
                    kind=chunk.kind,
                    stream_id=chunk.stream_id,
                    code=VoiceInputStreamRejectionCode.CHUNK_TOO_LARGE,
                    message="Audio chunk exceeds the configured size limit.",
                    sequence_number=chunk.sequence_number,
                    next_expected=expected,
                    retryable=True,
                )
            if chunk.duration_ms is None or (
                active.duration_ms + chunk.duration_ms
                > (self._capability.maximum_duration_ms or 0)
            ):
                return self._rejected(
                    kind=chunk.kind,
                    stream_id=chunk.stream_id,
                    code=VoiceInputStreamRejectionCode.DURATION_EXCEEDED,
                    message="Audio chunk duration is missing or exceeds the stream limit.",
                    sequence_number=chunk.sequence_number,
                    next_expected=expected,
                    retryable=True,
                )

        def emit_partial(text: str, confidence: float | None) -> None:
            if not isinstance(text, str) or not text.strip():
                raise ValueError("partial transcript text must be non-empty")
            if confidence is not None and not 0.0 <= confidence <= 1.0:
                raise ValueError("partial transcript confidence is invalid")
            with self._lock:
                current = self._active
                if current is None or current.config.stream_id != chunk.stream_id:
                    return
            self._on_partial(
                chunk.stream_id,
                chunk.sequence_number,
                text.strip(),
                confidence,
            )

        # Provider work runs outside the runtime lock. The bounded controller
        # owns the one in-flight slot while abort/close may proceed cooperatively.
        try:
            adapter.accept_chunk(chunk, emit_partial=emit_partial)
        except Exception:
            self._abort_adapter_safely(
                adapter,
                stream_id=chunk.stream_id,
                last_sequence_number=(expected - 1 if expected > 0 else None),
                reason="adapter_chunk_failed",
            )
            with self._lock:
                if self._active is active:
                    self._last_terminal = (chunk.stream_id, "aborted")
                    self._active = None
                    return self._rejected(
                        kind=chunk.kind,
                        stream_id=chunk.stream_id,
                        code=VoiceInputStreamRejectionCode.NOT_SUPPORTED,
                        message="Audio chunk adapter rejected the operation.",
                        sequence_number=chunk.sequence_number,
                        terminal=True,
                    )
                terminal = self._terminal_rejection(
                    kind=chunk.kind,
                    stream_id=chunk.stream_id,
                    sequence_number=chunk.sequence_number,
                )
                if terminal is None:
                    raise AssertionError("stream changed without a terminal state")
                return terminal

        with self._lock:
            if self._active is not active:
                terminal = self._terminal_rejection(
                    kind=chunk.kind,
                    stream_id=chunk.stream_id,
                    sequence_number=chunk.sequence_number,
                )
                if terminal is None:
                    raise AssertionError("stream changed without a terminal state")
                return terminal
            active.expected_sequence_number += 1
            active.duration_ms += chunk.duration_ms
            return VoiceInputStreamOperationResult.accepted_operation(
                kind=chunk.kind,
                stream_id=chunk.stream_id,
                sequence_number=chunk.sequence_number,
                next_expected_sequence_number=active.expected_sequence_number,
            )

    def end(
        self,
        marker: VoiceInputStreamEnd,
    ) -> tuple[VoiceInputStreamOperationResult, VoiceInputResult | None]:
        if not isinstance(marker, VoiceInputStreamEnd):
            raise TypeError("marker must be VoiceInputStreamEnd")
        with self._lock:
            if self._closed:
                return (
                    self._rejected(
                        kind=marker.kind,
                        stream_id=marker.stream_id,
                        code=VoiceInputStreamRejectionCode.SESSION_CLOSED,
                        message="Voice input session is closed.",
                        sequence_number=marker.sequence_number,
                        terminal=True,
                    ),
                    None,
                )
            terminal = self._terminal_rejection(
                kind=marker.kind,
                stream_id=marker.stream_id,
                sequence_number=marker.sequence_number,
            )
            if terminal is not None:
                return terminal, None
            active = self._active
            adapter = self._adapter
            if active is None or adapter is None or marker.stream_id != active.config.stream_id:
                return (
                    self._rejected(
                        kind=marker.kind,
                        stream_id=marker.stream_id,
                        code=VoiceInputStreamRejectionCode.INVALID_STREAM_ID,
                        message="Audio stream is not active.",
                        sequence_number=marker.sequence_number,
                    ),
                    None,
                )
            expected = active.expected_sequence_number
            if marker.sequence_number != expected:
                return (
                    self._rejected(
                        kind=marker.kind,
                        stream_id=marker.stream_id,
                        code=VoiceInputStreamRejectionCode.OUT_OF_ORDER,
                        message="End-of-input sequence is out of order.",
                        sequence_number=marker.sequence_number,
                        next_expected=expected,
                        retryable=True,
                    ),
                    None,
                )
            try:
                result = adapter.finish_stream(marker)
            except Exception:
                self._abort_adapter_safely(
                    adapter,
                    stream_id=marker.stream_id,
                    last_sequence_number=(expected - 1 if expected > 0 else None),
                    reason="adapter_finalize_failed",
                )
                self._last_terminal = (marker.stream_id, "aborted")
                self._active = None
                return (
                    self._rejected(
                        kind=marker.kind,
                        stream_id=marker.stream_id,
                        code=VoiceInputStreamRejectionCode.NOT_SUPPORTED,
                        message="Audio stream finalization failed.",
                        sequence_number=marker.sequence_number,
                        terminal=True,
                    ),
                    None,
                )
            if not isinstance(result, VoiceInputResult) or not result.is_completed:
                self._abort_adapter_safely(
                    adapter,
                    stream_id=marker.stream_id,
                    last_sequence_number=(expected - 1 if expected > 0 else None),
                    reason="adapter_final_result_invalid",
                )
                self._last_terminal = (marker.stream_id, "aborted")
                self._active = None
                return (
                    self._rejected(
                        kind=marker.kind,
                        stream_id=marker.stream_id,
                        code=VoiceInputStreamRejectionCode.NOT_SUPPORTED,
                        message="Audio stream produced no final transcript.",
                        sequence_number=marker.sequence_number,
                        terminal=True,
                    ),
                    None,
                )
            self._last_terminal = (marker.stream_id, "ended")
            self._active = None
            return (
                VoiceInputStreamOperationResult.accepted_operation(
                    kind=marker.kind,
                    stream_id=marker.stream_id,
                    sequence_number=marker.sequence_number,
                    next_expected_sequence_number=marker.sequence_number + 1,
                    terminal=True,
                ),
                result,
            )

    def abort(self, request: VoiceInputStreamAbort) -> VoiceInputStreamOperationResult:
        if not isinstance(request, VoiceInputStreamAbort):
            raise TypeError("request must be VoiceInputStreamAbort")
        with self._lock:
            if self._closed:
                return self._rejected(
                    kind=request.kind,
                    stream_id=request.stream_id,
                    code=VoiceInputStreamRejectionCode.SESSION_CLOSED,
                    message="Voice input session is closed.",
                    terminal=True,
                )
            terminal = self._terminal_rejection(
                kind=request.kind,
                stream_id=request.stream_id,
                sequence_number=request.last_sequence_number,
            )
            if terminal is not None:
                return terminal
            active = self._active
            adapter = self._adapter
            if active is None or adapter is None or request.stream_id != active.config.stream_id:
                return self._rejected(
                    kind=request.kind,
                    stream_id=request.stream_id,
                    code=VoiceInputStreamRejectionCode.INVALID_STREAM_ID,
                    message="Audio stream is not active.",
                )
            accepted = False
            if self._capability.input_abort_supported:
                try:
                    accepted = bool(adapter.abort_stream(request))
                except Exception:
                    accepted = False
            if not accepted:
                return self._rejected(
                    kind=request.kind,
                    stream_id=request.stream_id,
                    code=VoiceInputStreamRejectionCode.NOT_SUPPORTED,
                    message="Audio stream abort is not supported.",
                    next_expected=active.expected_sequence_number,
                )
            self._last_terminal = (request.stream_id, "aborted")
            self._active = None
            return VoiceInputStreamOperationResult.accepted_operation(
                kind=request.kind,
                stream_id=request.stream_id,
                sequence_number=request.last_sequence_number,
                next_expected_sequence_number=active.expected_sequence_number,
                terminal=True,
            )

    def close(self) -> None:
        # Close admission first so no caller can acquire a new in-flight slot
        # while stream cleanup is waiting on the adapter boundary.
        self._audio_backpressure.close()
        with self._lock:
            if self._closed:
                return
            active = self._active
            adapter = self._adapter
            if active is not None and adapter is not None:
                try:
                    adapter.abort_stream(
                        VoiceInputStreamAbort(
                            stream_id=active.config.stream_id,
                            reason="session_closed",
                            last_sequence_number=(
                                active.expected_sequence_number - 1
                                if active.expected_sequence_number > 0
                                else None
                            ),
                        )
                    )
                except Exception:
                    pass
                self._last_terminal = (active.config.stream_id, "aborted")
            self._active = None
            self._closed = True
