"""Example: observe public text session events.

This example shows how an external app can subscribe to app-facing session
events without importing internal runtime or plugin modules.
"""

from __future__ import annotations

import argparse
from typing import Sequence

from framework import FacadeError, create_text_chat_session


def run_state_events_demo(
    *,
    message: str,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    session = create_text_chat_session(
        preset="text_chat",
        character_name="default",
        provider=provider,
        model=model,
    )

    def handle_event(event) -> None:
        print(f"[event] {event.type}: {event.data}")

    def handle_state_change(event) -> None:
        print(f"[state] {event.old_state} -> {event.new_state}")

    session.on_event(handle_event)
    session.on_state_change(handle_state_change)

    print(session.ask(message))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Observe public text session events.",
    )
    parser.add_argument(
        "--message",
        default="Hello. Please answer briefly.",
        help="Message to send to the text session.",
    )
    parser.add_argument(
        "--provider",
        help="Optional direct provider override, such as openai, gemini, or grok.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override for the selected provider.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    try:
        run_state_events_demo(
            message=args.message,
            provider=args.provider,
            model=args.model,
        )
    except FacadeError as exc:
        print(f"Framework integration error: {exc}")


if __name__ == "__main__":
    main()