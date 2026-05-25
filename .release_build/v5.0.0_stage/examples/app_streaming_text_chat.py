"""Streaming text chat example for the public facade.

Run from the project root after setting API keys in .env:

    python examples/app_streaming_text_chat.py --provider openai --model gpt-4o-mini

This example demonstrates `session.ask_stream(...)` with only public framework
imports. It does not launch main.py, STT, TTS, VTube Studio, or the full runtime
loop.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterator, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework import FacadeError, TextChatSessionInfo, create_text_chat_session


class StreamingTextChatApp:
    """Tiny app wrapper that exposes a streaming text reply method."""

    def __init__(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        character_name: str = "default",
    ):
        self._session = create_text_chat_session(
            preset="text_chat",
            character_name=character_name,
            provider=provider,
            model=model,
        )

    @property
    def session_info(self) -> TextChatSessionInfo:
        """Expose public framework session metadata to the app layer."""
        return self._session.info

    def stream_reply(self, user_text: str) -> Iterator[str]:
        """Yield assistant response chunks for application-level streaming UI."""
        yield from self._session.ask_stream(user_text)


def build_app(
    *,
    provider: str | None = None,
    model: str | None = None,
    character_name: str = "default",
) -> StreamingTextChatApp:
    """Create the streaming app wrapper with only public framework APIs."""
    return StreamingTextChatApp(
        provider=provider,
        model=model,
        character_name=character_name,
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a streaming text chat integration example.",
    )
    parser.add_argument(
        "--provider",
        help="Optional LLM provider override, such as openai, gemini, or grok.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override for the selected provider.",
    )
    parser.add_argument(
        "--message",
        default="こんにちは。1文で短く返して。",
        help="Message to stream through the framework text chat session.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        app = build_app(
            provider=args.provider,
            model=args.model,
        )
        print(f"Session info: {app.session_info}")
        print("Streaming response:")
        for chunk in app.stream_reply(args.message):
            print(chunk, end="", flush=True)
        print()
    except FacadeError as e:
        print(f"[Facade Error] {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
