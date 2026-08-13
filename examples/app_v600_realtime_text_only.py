"""Provider-free text-only introduction to the public realtime session."""

from __future__ import annotations

import framework


def run_text_only(input_text: str = "今日は少し眠いです。") -> tuple[str, str, bool]:
    """Run one deterministic provider-free turn and return public facts."""
    with framework.create_realtime_session() as session:
        result = session.run_turn(input_text=input_text)
        return (
            session.compatibility_profile.mode.value,
            result.outcome.value,
            bool(result.public_metadata.get("mock_runtime")),
        )


def main() -> None:
    mode, outcome, mock_runtime = run_text_only()
    print("compatibility_mode:", mode)
    print("turn_outcome:", outcome)
    print("mock_runtime:", mock_runtime)
    print("provider_execution_performed:", False)


if __name__ == "__main__":
    main()
