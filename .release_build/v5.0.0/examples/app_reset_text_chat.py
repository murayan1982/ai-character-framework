"""Minimal reset example for the public text chat facade.

This example shows how an external app can expose a reset action without
reaching into internal runtime modules.

Live check example:

    python examples/app_reset_text_chat.py --provider openai --model gpt-4o-mini
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework import FacadeError, TextChatSession, create_text_chat_session


DEFAULT_FIRST_MESSAGE = "こんにちは。1文で短く返して。"
DEFAULT_SECOND_MESSAGE = "もう一度、短く挨拶して。"


class ResettableTextChatApp:
    """Tiny app wrapper that exposes ask and reset through the public facade."""

    def __init__(self, session: TextChatSession):
        self.session = session

    def ask(self, message: str) -> str:
        """Send one text turn through the public session."""
        return self.session.ask(message)

    def reset(self) -> None:
        """Reset provider-owned conversation state through the public session."""
        self.session.reset()


def build_app(
    *,
    provider: str | None = None,
    model: str | None = None,
) -> ResettableTextChatApp:
    """Build the app without exposing internal RuntimeConfig details."""
    session = create_text_chat_session(
        provider=provider,
        model=model,
    )
    return ResettableTextChatApp(session=session)


def run_demo(
    *,
    provider: str | None,
    model: str | None,
    first_message: str,
    second_message: str,
) -> None:
    """Run a small before/after reset demo."""
    app = build_app(provider=provider, model=model)

    print(f"Session info: {app.session.info}")

    print("\n[Before reset]")
    print(app.ask(first_message))

    app.reset()
    print("\n[Reset complete]")

    print("\n[After reset]")
    print(app.ask(second_message))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a minimal reset example through the public text chat facade.",
    )
    parser.add_argument(
        "--provider",
        help="Optional provider override, such as openai, google, gemini, xai, or grok.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override for the selected provider.",
    )
    parser.add_argument(
        "--first-message",
        default=DEFAULT_FIRST_MESSAGE,
        help="Message to send before reset.",
    )
    parser.add_argument(
        "--second-message",
        default=DEFAULT_SECOND_MESSAGE,
        help="Message to send after reset.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        run_demo(
            provider=args.provider,
            model=args.model,
            first_message=args.first_message,
            second_message=args.second_message,
        )
    except FacadeError as exc:
        print(f"[FacadeError] {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
