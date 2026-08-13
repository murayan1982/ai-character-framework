"""Provider-neutral adapter boundary for public audio-chunk streaming.

Importing this explicit module performs no provider, network, microphone,
audio-device, playback, or VTube Studio work.  The deterministic fake adapter
exists so the complete public streaming path can be exercised offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Callable, Mapping, Protocol, runtime_checkable

from .voice_input import VoiceInputResult
from .voice_input_streaming import (
    VoiceInputAudioChunk,
    VoiceInputStreamAbort,
    VoiceInputStreamConfig,
    VoiceInputStreamEnd,
    VoiceInputStreamingCapability,
)


PartialTranscriptSink = Callable[[str, float | None], None]


@runtime_checkable
class VoiceInputStreamingAdapter(Protocol):
    """Structural adapter used by :class:`VoiceInputSession` streaming input.

    Framework owns stream identity, limits, ordering, typed rejection, and
    public event correlation.  An adapter may consume an already-admitted
    chunk and synchronously publish zero or more transcript observations.
    """

    @property
    def streaming_capability(self) -> VoiceInputStreamingCapability:
        ...

    def begin_stream(self, config: VoiceInputStreamConfig) -> None:
        ...

    def accept_chunk(
        self,
        chunk: VoiceInputAudioChunk,
        *,
        emit_partial: PartialTranscriptSink,
    ) -> None:
        ...

    def finish_stream(self, marker: VoiceInputStreamEnd) -> VoiceInputResult:
        ...

    def abort_stream(self, request: VoiceInputStreamAbort) -> bool:
        ...


@dataclass(slots=True)
class DeterministicFakeVoiceInputStreamingAdapter:
    """Provider-free adapter that never reads or decodes the supplied bytes."""

    partial_transcripts: Mapping[int, str] = field(default_factory=dict, repr=False)
    final_transcript: str = field(default="fake final transcript", repr=False)
    language: str | None = None
    confidence: float | None = 1.0
    capability: VoiceInputStreamingCapability = field(
        default_factory=lambda: VoiceInputStreamingCapability(
            audio_chunk_input_supported=True,
            accepted_audio_formats=("pcm16",),
            maximum_chunk_size_bytes=8192,
            maximum_duration_ms=30_000,
            end_of_input_supported=True,
            input_abort_supported=True,
            partial_transcript_supported=True,
            final_transcript_supported=True,
            public_metadata={
                "adapter": "deterministic_fake",
                "provider_execution": False,
                "audio_content_decoded": False,
            },
        )
    )
    _active_stream_id: str | None = field(init=False, default=None, repr=False)
    _duration_ms: int = field(init=False, default=0, repr=False)
    _lock: RLock = field(init=False, default_factory=RLock, repr=False)

    def __post_init__(self) -> None:
        normalized: dict[int, str] = {}
        for sequence, text in self.partial_transcripts.items():
            if isinstance(sequence, bool) or not isinstance(sequence, int):
                raise TypeError("partial transcript sequence must be an integer")
            if sequence < 0:
                raise ValueError("partial transcript sequence must be non-negative")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("partial transcript text must be non-empty")
            normalized[sequence] = text.strip()
        if not isinstance(self.final_transcript, str) or not self.final_transcript.strip():
            raise ValueError("final_transcript must be non-empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        if not isinstance(self.capability, VoiceInputStreamingCapability):
            raise TypeError("capability must be VoiceInputStreamingCapability")
        if not self.capability.audio_chunk_input_supported:
            raise ValueError("fake streaming adapter requires supported capability")
        self.partial_transcripts = normalized
        self.final_transcript = self.final_transcript.strip()

    @property
    def streaming_capability(self) -> VoiceInputStreamingCapability:
        return self.capability

    def begin_stream(self, config: VoiceInputStreamConfig) -> None:
        with self._lock:
            if self._active_stream_id is not None:
                raise RuntimeError("Fake streaming adapter already has an active stream.")
            self._active_stream_id = config.stream_id
            self._duration_ms = 0

    def accept_chunk(
        self,
        chunk: VoiceInputAudioChunk,
        *,
        emit_partial: PartialTranscriptSink,
    ) -> None:
        with self._lock:
            if chunk.stream_id != self._active_stream_id:
                raise RuntimeError("Fake streaming adapter stream identity mismatch.")
            self._duration_ms += chunk.duration_ms or 0
            partial = self.partial_transcripts.get(chunk.sequence_number)
        if partial is not None:
            emit_partial(partial, self.confidence)

    def finish_stream(self, marker: VoiceInputStreamEnd) -> VoiceInputResult:
        with self._lock:
            if marker.stream_id != self._active_stream_id:
                raise RuntimeError("Fake streaming adapter stream identity mismatch.")
            duration_ms = self._duration_ms
            self._active_stream_id = None
            self._duration_ms = 0
        return VoiceInputResult.completed(
            self.final_transcript,
            language=self.language,
            confidence=self.confidence,
            duration_ms=duration_ms,
            public_metadata={
                "adapter": "deterministic_fake",
                "provider_execution_executed": False,
                "audio_content_decoded": False,
                "microphone_accessed": False,
            },
        )

    def abort_stream(self, request: VoiceInputStreamAbort) -> bool:
        with self._lock:
            if request.stream_id != self._active_stream_id:
                return False
            self._active_stream_id = None
            self._duration_ms = 0
            return True


__all__ = (
    "VoiceInputStreamingAdapter",
    "DeterministicFakeVoiceInputStreamingAdapter",
)
