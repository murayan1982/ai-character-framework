"""Explicit host fallback after an unavailable v6 unified-runtime request.

The Framework never silently converts the explicit request to mock success.
This example shows a host making a separate, visible provider-free fallback
choice. Importing this module performs no session or runtime work.
"""

from __future__ import annotations

import framework


def run_with_explicit_fallback(
    input_text: str = "オフラインの案内をお願いします。",
) -> tuple[str, str, str, str, bool]:
    """Return the requested-mode rejection and explicit fallback observation."""

    with framework.create_realtime_session(real_runtime_enabled=True) as requested:
        requested_mode = requested.compatibility_profile.mode.value
        construction_status = requested.construction_result.status.value
        requested_result = requested.run_turn(input_text=input_text)

    if requested_result.outcome.value != "rejected":
        raise RuntimeError("the example expects unavailable unified orchestration")
    if requested_result.public_metadata.get("mock_runtime") is not False:
        raise RuntimeError("an explicit unified request must not silently use mock")

    with framework.create_realtime_session() as fallback:
        fallback_result = fallback.run_turn(input_text=input_text)
        fallback_mode = fallback.compatibility_profile.mode.value
        fallback_is_mock = bool(
            fallback_result.public_metadata.get("mock_runtime")
        )

    return (
        requested_mode,
        construction_status,
        requested_result.outcome.value,
        fallback_mode,
        fallback_is_mock,
    )


def main() -> None:
    (
        requested_mode,
        construction_status,
        requested_outcome,
        fallback_mode,
        fallback_is_mock,
    ) = run_with_explicit_fallback()
    print("requested_mode:", requested_mode)
    print("construction_status:", construction_status)
    print("requested_outcome:", requested_outcome)
    print("fallback_selected_by_host:", True)
    print("fallback_mode:", fallback_mode)
    print("fallback_mock_runtime:", fallback_is_mock)
    print("provider_execution_performed:", False)


if __name__ == "__main__":
    main()
