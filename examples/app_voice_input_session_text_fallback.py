"""Host-app example: public voice-input session with text fallback.

This example shows the DRC-safe public boundary before real STT execution is
implemented. It does not import FW internals or provider SDKs.
"""

from __future__ import annotations

import framework


def main() -> None:
    events: list[str] = []

    with framework.create_voice_input_session(language="ja-JP") as session:
        session.on_event(lambda event: events.append(event["type"]))

        unavailable = session.listen_result()
        print("listen_outcome:", unavailable.outcome.value)
        print("listen_error:", unavailable.public_error_code.value)
        print("listen_status:", unavailable.public_metadata.get("provider_status"))

        fallback = session.text_fallback_result("今日は少し眠いです。")
        print("fallback_outcome:", fallback.outcome.value)
        print("fallback_text:", fallback.text)

    print("closed:", session.is_closed)
    print("events:", ",".join(events))


if __name__ == "__main__":
    main()
