"""Example: app-side voice output integration through the public FW boundary.

This example mirrors a host app such as Daily Rhythm Companion (DRC). The app
passes only provider-neutral voice output intent to FW:

- text
- voice_profile_id
- requested_audio_format
- utterance_purpose
- language_code

Provider selection, provider voice IDs, API keys, model IDs, SDK calls, and
audio artifact creation remain FW responsibilities. Importing this file and
running the default demo are safe without provider credentials.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework import (  # noqa: E402
    VoiceOutputRequest,
    VoiceOutputResult,
    VoiceOutputSessionInfo,
    create_voice_output_session,
)


DEFAULT_DRC_VOICE_PROFILE_ID = "gentle_mina_default"
DEFAULT_DRC_AUDIO_FORMAT = "mp3"
DEFAULT_DRC_LANGUAGE_CODE = "ja"


@dataclass(frozen=True)
class DailyAdviceVoiceOutput:
    """Small host-app DTO that contains only app-owned voice intent."""

    text: str
    voice_profile_id: str = DEFAULT_DRC_VOICE_PROFILE_ID
    requested_audio_format: str = DEFAULT_DRC_AUDIO_FORMAT
    language_code: str = DEFAULT_DRC_LANGUAGE_CODE
    utterance_purpose: str = "daily_advice"


class DailyRhythmCompanionVoiceOutputBridge:
    """DRC-style wrapper around the public FW voice output boundary.

    The wrapper intentionally does not accept or store provider names, provider
    voice IDs, API keys, model IDs, or provider-specific options. Those remain
    FW-side responsibilities behind create_voice_output_session().
    """

    def __init__(
        self,
        *,
        project_root: str | Path | None = None,
        default_voice_profile_id: str = DEFAULT_DRC_VOICE_PROFILE_ID,
        real_tts_enabled: bool | None = False,
        artifact_dir: str | Path | None = None,
    ) -> None:
        self._session = create_voice_output_session(
            project_root=project_root,
            default_voice_profile_id=default_voice_profile_id,
            real_tts_enabled=real_tts_enabled,
            artifact_dir=artifact_dir,
        )

    def session_info(self) -> VoiceOutputSessionInfo:
        """Return app-safe voice output metadata for UI/status display."""
        return self._session.info()

    def build_request(self, voice_output: DailyAdviceVoiceOutput) -> VoiceOutputRequest:
        """Convert host-app intent into FW's provider-neutral request model."""
        return VoiceOutputRequest(
            text=voice_output.text,
            voice_profile_id=voice_output.voice_profile_id,
            requested_audio_format=voice_output.requested_audio_format,
            utterance_purpose=voice_output.utterance_purpose,
            language_code=voice_output.language_code,
        )

    def create_daily_advice_audio(
        self,
        voice_output: DailyAdviceVoiceOutput,
    ) -> VoiceOutputResult:
        """Ask FW to create audio, or return safe unavailable when unconfigured."""
        return self._session.create_output(self.build_request(voice_output))


def build_drc_voice_output_bridge(
    *,
    project_root: str | Path | None = None,
    real_tts_enabled: bool | None = False,
    artifact_dir: str | Path | None = None,
) -> DailyRhythmCompanionVoiceOutputBridge:
    """Create the DRC-style bridge using only public FW APIs."""
    return DailyRhythmCompanionVoiceOutputBridge(
        project_root=project_root,
        real_tts_enabled=real_tts_enabled,
        artifact_dir=artifact_dir,
    )


def build_sample_daily_advice_output(
    text: str = "今日は少し早めに休むとよさそうです。",
) -> DailyAdviceVoiceOutput:
    """Build a DRC-style request payload without provider-specific details."""
    return DailyAdviceVoiceOutput(text=text)


def run_voice_output_integration_demo(
    *,
    text: str = "今日は少し早めに休むとよさそうです。",
    real_tts_enabled: bool | None = False,
    project_root: str | Path | None = None,
    artifact_dir: str | Path | None = None,
) -> VoiceOutputResult:
    """Run one app-style voice output request through the public boundary.

    With the default ``real_tts_enabled=False``, this returns safe ``unavailable``
    without importing provider SDKs or requiring API keys. Passing
    ``real_tts_enabled=True`` only opts into real synthesis intent; provider
    credentials and voice IDs are still resolved inside FW, not in the app.
    """
    bridge = build_drc_voice_output_bridge(
        project_root=project_root,
        real_tts_enabled=real_tts_enabled,
        artifact_dir=artifact_dir,
    )
    voice_output = build_sample_daily_advice_output(text)
    return bridge.create_daily_advice_audio(voice_output)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a provider-neutral app voice output integration demo.",
    )
    parser.add_argument(
        "--text",
        default="今日は少し早めに休むとよさそうです。",
        help="Text to pass as host-app voice output intent.",
    )
    parser.add_argument(
        "--real-tts",
        action="store_true",
        help=(
            "Opt into real FW-owned TTS execution. Provider settings, voice IDs, "
            "API keys, and model IDs are still not supplied by this app example."
        ),
    )
    parser.add_argument(
        "--artifact-dir",
        help="Optional FW-owned output artifact directory for explicit real runs.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    bridge = build_drc_voice_output_bridge(
        project_root=PROJECT_ROOT,
        real_tts_enabled=args.real_tts,
        artifact_dir=args.artifact_dir,
    )
    result = bridge.create_daily_advice_audio(build_sample_daily_advice_output(args.text))

    print("=== Voice Output Session Info ===")
    print(bridge.session_info())
    print()
    print("=== Voice Output Result ===")
    print(f"request_state: {result.request_state}")
    print(f"audio_ready: {result.audio_ready}")
    print(f"audio_format: {result.audio_format}")
    print(f"audio_url: {result.audio_url}")
    print(f"audio_artifact_ref: {result.audio_artifact_ref}")
    print(f"message: {result.message}")
    print(f"public_metadata: {dict(result.public_metadata)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
