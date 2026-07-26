"""Host-app example: public voice-input missing-credential handling.

This example uses `credential_env={}` to make the preflight deterministic and
mock-safe. No real STT provider is imported or executed.
"""

from __future__ import annotations

import framework


def main() -> None:
    session = framework.create_voice_input_session(
        provider="google",
        real_stt_enabled=True,
        allow_provider_execution=True,
        credential_env={},
    )

    result = session.listen_result()

    print("provider_status:", session.info.provider_status.value)
    print("outcome:", result.outcome.value)
    print("error_code:", result.public_error_code.value)
    print("retryable:", result.retryable)
    print("safe_message:", result.safe_message)


if __name__ == "__main__":
    main()
