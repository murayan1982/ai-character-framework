"""Minimal app-style integration example for the public text chat facade.

Run from the project root after setting API keys in .env:

    python examples/minimal_app_text_chat.py

Optional provider/model override:

    python examples/minimal_app_text_chat.py --provider openai --model gpt-4o-mini

This example shows the smallest shape an external application might use:
- create the framework session during app startup
- expose an app-level reply() method
- catch public facade errors at the app boundary

It intentionally does not launch main.py, STT, TTS, VTube Studio, or the full
interactive runtime loop.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework import FacadeError, TextChatSessionInfo, create_text_chat_session


class MinimalTextChatApp:
    """Tiny application wrapper around the framework text chat facade."""

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
        """Expose public framework session metadata to the application layer."""
        return self._session.info

    def reply(self, user_text: str) -> str:
        """Return one assistant response for application-level user input."""
        return self._session.ask(user_text)

    def reset_conversation(self) -> None:
        """Reset the underlying framework session."""
        self._session.reset()


def build_app(
    *,
    provider: str | None = None,
    model: str | None = None,
    character_name: str = "default",
) -> MinimalTextChatApp:
    """Create the app wrapper with only public framework APIs."""
    return MinimalTextChatApp(
        provider=provider,
        model=model,
        character_name=character_name,
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal app-style text chat integration example.",
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
        help="Message to send to the framework text chat session.",
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
        print(app.reply(args.message))
    except FacadeError as e:
        print(f"[Facade Error] {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
