"""Example: inspect public text session metadata.

This example shows how an external app can inspect app-safe session metadata
without importing internal runtime modules.
"""

from __future__ import annotations

import argparse
from typing import Sequence

from framework import FacadeError, create_text_chat_session


def run_session_info_demo(
    *,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    session = create_text_chat_session(
        preset="text_chat",
        character_name="default",
        provider=provider,
        model=model,
    )

    info = session.info

    print("=== Text Chat Session Info ===")
    print(f"api_version: {info.api_version}")
    print(f"session_type: {info.session_type}")
    print(f"preset: {info.preset}")
    print(f"character_name: {info.character_name}")
    print(f"input_language_code: {info.input_language_code}")
    print(f"output_language_code: {info.output_language_code}")
    print(f"llm_mode: {info.llm_mode}")
    print(f"provider: {info.provider}")
    print(f"model: {info.model}")
    print(f"route_name: {info.route_name}")

    print()
    print("=== Capabilities ===")
    print(f"supports_streaming: {info.supports_streaming}")
    print(f"supports_reset: {info.supports_reset}")
    print(f"supports_interrupt: {info.supports_interrupt}")
    print(f"supports_events: {info.supports_events}")
    print(f"supports_close: {info.supports_close}")
    print(f"supports_voice_input: {info.supports_voice_input}")
    print(f"supports_voice_output: {info.supports_voice_output}")
    print(f"supports_live2d: {info.supports_live2d}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect public text session metadata.",
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
        run_session_info_demo(
            provider=args.provider,
            model=args.model,
        )
    except FacadeError as exc:
        print(f"Framework integration error: {exc}")


if __name__ == "__main__":
    main()