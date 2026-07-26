"""Minimal app-style TextChatResult example.

This example is mock-safe to import. It only calls the provider if executed and
configured in the local environment, matching the existing text chat examples.
"""

from __future__ import annotations

import argparse

from framework import create_text_chat_session


def main() -> None:
    parser = argparse.ArgumentParser(description="TextChatResult app integration example")
    parser.add_argument("--message", default="こんにちは。1文で短く返して。")
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    session = create_text_chat_session(provider=args.provider, model=args.model)
    result = session.ask_result(args.message)

    print("=== Text Chat Result ===")
    print(f"outcome: {result.outcome}")
    print(f"text: {result.text}")
    print(f"public_error_code: {result.public_error_code}")
    print(f"safe_message: {result.safe_message}")
    print(f"retryable: {result.retryable}")


if __name__ == "__main__":
    main()
