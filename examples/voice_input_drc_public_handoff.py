"""DRC-style public voice-input handoff example for v5.3.0 STT-1f.

This example intentionally uses only the public framework facade. It simulates a
host app that has already captured microphone audio and now hands an opaque
capture ID to the framework. It does not open the microphone, read audio, upload
audio, or execute a real STT provider.
"""

from __future__ import annotations

from framework import (
    FakeVoiceInputProviderAdapter,
    VoiceInputAudioFormat,
    VoiceInputAudioSource,
    VoiceInputRequest,
    create_voice_input_session,
)


def run_drc_public_handoff_example() -> str:
    audio_format = VoiceInputAudioFormat.wav(
        sample_rate_hz=16000,
        channel_count=1,
        duration_ms=4820,
        capture_owner="host-app",
    )
    audio_source = VoiceInputAudioSource.from_opaque_id(
        "drc_capture_opaque_id",
        audio_format=audio_format,
        language="ja-JP",
        max_duration_ms=15000,
        public_metadata={
            "host_app": "DRC",
            "raw_audio_exposed": False,
            "private_artifact_cleanup_required": True,
        },
    )
    request = VoiceInputRequest(language="ja-JP", max_duration_ms=15000)
    adapter = FakeVoiceInputProviderAdapter(transcript="DRC public handoff fake transcript")

    session = create_voice_input_session()
    result = session.transcribe_audio_result(audio_source, request=request, adapter=adapter)
    return result.text


if __name__ == "__main__":
    print(run_drc_public_handoff_example())
