"""Example: request interruption from an external app.

This example demonstrates the public `session.interrupt()` boundary.

In v4.0.0, interruption is a limited app-facing boundary. It can stop the public
text facade from yielding future chunks after the interrupt request is observed,
but it does not guarantee provider-level LLM cancellation.
"""

from __future__ import annotations

import argparse
import threading
import time
from typing import Sequence

from framework import FacadeError, create_text_chat_session


def run_interrupt_demo(
    *,
    message: str,
    interrupt_after_seconds: float,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    session = create_text_chat_session(
        preset="text_chat",
        character_name="default",
        provider=provider,
        model=model,
    )

    def request_interrupt() -> None:
        time.sleep(interrupt_after_seconds)
        accepted = session.interrupt()
        print()
        print(f"[interrupt requested] accepted={accepted}")

    interrupt_thread = threading.Thread(target=request_interrupt, daemon=True)
    interrupt_thread.start()

    print("=== Streaming response ===")
    for chunk in session.ask_stream(message):
        print(chunk, end="", flush=True)

    print()
    print("=== Done ===")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Request interruption through the public text session API.",
    )
    parser.add_argument(
        "--message",
        default=(
            "Please write a long but simple explanation of how external apps "
            "can use a text chat session."
        ),
        help="Message to send to the text session.",
    )
    parser.add_argument(
        "--interrupt-after-seconds",
        type=float,
        default=1.0,
        help="Seconds to wait before requesting interruption.",
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
        run_interrupt_demo(
            message=args.message,
            interrupt_after_seconds=args.interrupt_after_seconds,
            provider=args.provider,
            model=args.model,
        )
    except FacadeError as exc:
        print(f"Framework integration error: {exc}")


if __name__ == "__main__":
    main()