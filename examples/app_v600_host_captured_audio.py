"""Provider-free host-captured audio handoff through the public Framework root.

The host has already captured the audio and supplies only an opaque ID.  This
example neither opens a microphone nor reads audio bytes or a private path.
"""

from __future__ import annotations

import framework


def run_host_captured_audio() -> tuple[str, str, str, bool, bool, bool]:
    """Transcribe one opaque host capture with the deterministic fake adapter."""

    audio_format = framework.VoiceInputAudioFormat.wav(
        sample_rate_hz=16000,
        channel_count=1,
        duration_ms=800,
        capture_owner="host",
    )
    audio_source = framework.VoiceInputAudioSource.from_opaque_id(
        "host_capture_demo",
        audio_format=audio_format,
        language="ja-JP",
        public_metadata={"raw_audio_exposed": False},
    )
    adapter = framework.FakeVoiceInputProviderAdapter(
        transcript="host captured fake transcript",
    )

    with framework.create_voice_input_session(language="ja-JP") as session:
        result = session.transcribe_audio_result(
            audio_source,
            adapter=adapter,
        )

    return (
        result.outcome.value,
        result.text,
        audio_source.source_kind.value,
        bool(result.public_metadata.get("provider_execution_executed")),
        bool(result.public_metadata.get("audio_read")),
        bool(result.public_metadata.get("microphone_accessed")),
    )


def main() -> None:
    outcome, transcript, source_kind, provider, audio_read, microphone = (
        run_host_captured_audio()
    )
    print("voice_input_outcome:", outcome)
    print("transcript:", transcript)
    print("audio_source_kind:", source_kind)
    print("provider_execution_performed:", provider)
    print("audio_read_performed:", audio_read)
    print("microphone_accessed:", microphone)


if __name__ == "__main__":
    main()
