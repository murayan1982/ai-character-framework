"""Host-app example: public voice-input capability preflight.

This example is mock-safe. It does not import or execute any real STT provider.
"""

from __future__ import annotations

import framework


def main() -> None:
    capabilities = framework.get_voice_input_capabilities()

    print("voice_input_session:", capabilities.supports_voice_input_session)
    print("text_fallback:", capabilities.supports_text_fallback)
    print("real_stt:", capabilities.supports_real_stt)
    print("provider_status:", capabilities.provider_status.value)
    print("safe_message:", capabilities.safe_message)


if __name__ == "__main__":
    main()
