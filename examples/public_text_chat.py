"""Minimal public facade example.

Run after installing the SDK and setting API keys in .env:

    python examples/public_text_chat.py

This example intentionally uses only the public framework facade. It does not
launch main.py, STT, TTS, VTube Studio, or the interactive runtime loop.
"""

from __future__ import annotations

from framework import create_text_chat_session


def main() -> None:
    session = create_text_chat_session(
        preset="text_chat",
        character_name="default",
    )

    print(f"Session info: {session.info}")
    response = session.ask("こんにちは。1文で短く返して。")
    print(response)


if __name__ == "__main__":
    main()
