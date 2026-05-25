"""App-level error handling example for the public text chat facade.

Run from the project root:

    python examples/app_error_handling.py

The default offline demo intentionally triggers facade errors without creating
provider clients or calling external LLM APIs.

Optional live check after setting API keys in .env:

    python examples/app_error_handling.py --live --provider openai --model gpt-4o-mini

This example shows the recommended application boundary:
- import only from the public framework package
- catch FacadeError or its public subclasses
- keep framework integration failures separate from the rest of the app
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework import (  # noqa: E402
    FacadeConfigError,
    FacadeError,
    FacadeProviderError,
    create_text_chat_session,
)


def run_invalid_preset_demo() -> None:
    """Show how an app can catch text-facade configuration errors."""
    try:
        create_text_chat_session(
            preset="voice_vts",
            character_name="default",
        )
    except FacadeConfigError as exc:
        print("[OK] Caught FacadeConfigError for a non-text preset")
        print(f"     {exc}")
        return

    raise RuntimeError("voice_vts should be rejected by the text chat facade")


def run_invalid_provider_demo() -> None:
    """Show how an app can catch provider/model selection errors."""
    try:
        create_text_chat_session(
            preset="text_chat",
            character_name="default",
            provider="unknown-provider",
        )
    except FacadeProviderError as exc:
        print("[OK] Caught FacadeProviderError for an unknown provider")
        print(f"     {exc}")
        return

    raise RuntimeError("unknown-provider should be rejected by the text chat facade")


def run_live_turn(
    message: str,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Run one optional live turn using the same public error boundary."""
    session = create_text_chat_session(
        preset="text_chat",
        character_name="default",
        provider=provider,
        model=model,
    )
    print(f"Session info: {session.info}")
    print(session.ask(message))


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Demonstrate app-level facade error handling.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one live text chat turn instead of the offline error demos.",
    )
    parser.add_argument(
        "--provider",
        help="Optional LLM provider override for --live, such as openai, gemini, or grok.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override for the selected provider in --live mode.",
    )
    parser.add_argument(
        "--message",
        default="こんにちは。1文で短く返して。",
        help="Message to send in --live mode.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])

    try:
        if args.live:
            run_live_turn(
                args.message,
                provider=args.provider,
                model=args.model,
            )
        else:
            run_invalid_preset_demo()
            run_invalid_provider_demo()
    except FacadeError as exc:
        print(f"[Facade Error] {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
