"""Minimal public facade example.

Run from the project root after setting API keys in .env:

    python examples/public_text_chat.py

This example intentionally uses only the public framework facade. It does not
launch main.py, STT, TTS, VTube Studio, or the interactive runtime loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
