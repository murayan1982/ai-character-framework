"""Host-app example: public realtime closed-session behavior.

This example verifies that a host app receives a typed provider-neutral closed
result instead of relying on exceptions or framework internals.
"""

from __future__ import annotations

import framework


def main() -> None:
    session = framework.create_realtime_session()
    session.close()

    result = session.run_turn(input_text="after close")

    print("session_closed:", session.is_closed)
    print("session_state:", session.state.value)
    print("result_outcome:", result.outcome.value)
    print("error_code:", result.public_error_code.value)
    print("retryable:", result.retryable)


if __name__ == "__main__":
    main()
