"""Provider-free unit tests for subscriber delivery and bounded history."""

from __future__ import annotations

from dataclasses import dataclass
import unittest

from framework.identity import EventSequence
from framework.realtime_event_hub import (
    EventHubClosedError,
    RealtimeEventHub,
)


@dataclass(frozen=True, slots=True)
class _Event:
    sequence: EventSequence
    label: str


class _StepClock:
    def __init__(self, *values: float) -> None:
        self._values = iter(values)

    def __call__(self) -> float:
        return next(self._values)


class RealtimeEventHubTests(unittest.TestCase):
    def test_canonical_delivery_is_sequenced_and_retained(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub(history_limit=4)
        delivered: list[_Event] = []
        hub.subscribe(delivered.append)

        first = hub.emit(lambda sequence: _Event(sequence, "first"))
        second = hub.emit(lambda sequence: _Event(sequence, "second"))

        self.assertEqual((first.sequence, second.sequence), (1, 2))
        self.assertEqual(delivered, [first, second])
        self.assertEqual(hub.event_history, (first, second))
        self.assertEqual(hub.diagnostics.emitted_event_count, 2)

    def test_unsubscribe_prevents_future_delivery(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub()
        delivered: list[_Event] = []
        token = hub.subscribe(delivered.append)

        self.assertTrue(hub.unsubscribe(token))
        self.assertFalse(hub.unsubscribe(token))
        hub.emit(lambda sequence: _Event(sequence, "ignored"))

        self.assertEqual(delivered, [])
        self.assertEqual(hub.subscriber_count, 0)

    def test_legacy_projection_has_same_sequence(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub()
        canonical: list[_Event] = []
        legacy: list[_Event] = []
        hub.subscribe(canonical.append)
        hub.subscribe(legacy.append, legacy=True)

        event = hub.emit(
            lambda sequence: _Event(sequence, "canonical"),
            legacy_projector=lambda current: _Event(
                current.sequence,
                "legacy",
            ),
        )

        self.assertEqual(canonical, [event])
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0].sequence, event.sequence)
        self.assertEqual(legacy[0].label, "legacy")

    def test_callback_failure_is_isolated(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub()
        delivered: list[_Event] = []

        def failing_callback(event: _Event) -> None:
            raise RuntimeError(event.label)

        hub.subscribe(failing_callback)
        hub.subscribe(delivered.append)

        event = hub.emit(lambda sequence: _Event(sequence, "safe"))

        self.assertEqual(delivered, [event])
        self.assertEqual(hub.diagnostics.callback_error_count, 1)

    def test_slow_callback_is_counted_with_injected_clock(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub(
            slow_callback_seconds=0.5,
            clock=_StepClock(0.0, 1.0),
        )
        hub.subscribe(lambda event: None)

        hub.emit(lambda sequence: _Event(sequence, "slow"))

        self.assertEqual(hub.diagnostics.slow_callback_count, 1)

    def test_overflow_is_bounded_and_non_silent(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub(history_limit=3)
        delivered: list[_Event] = []
        hub.subscribe(delivered.append)

        hub.emit(lambda sequence: _Event(sequence, "one"))
        hub.emit(lambda sequence: _Event(sequence, "two"))
        third = hub.emit(lambda sequence: _Event(sequence, "three"))
        fourth = hub.emit(
            lambda sequence: _Event(sequence, "four"),
            overflow_event_factory=lambda sequence, first_dropped, count: _Event(
                sequence,
                f"overflow:{int(first_dropped or 0)}:{count}",
            ),
        )

        history = hub.event_history
        self.assertEqual(
            tuple(event.sequence for event in history),
            (third.sequence, fourth.sequence, EventSequence(5)),
        )
        self.assertEqual(
            tuple(event.label for event in history),
            ("three", "four", "overflow:1:2"),
        )
        self.assertEqual(
            tuple(event.sequence for event in delivered),
            (1, 2, 3, 4, 5),
        )
        self.assertEqual(hub.diagnostics.emitted_event_count, 5)
        self.assertEqual(hub.diagnostics.history_overflow_count, 2)

    def test_close_is_idempotent_and_rejects_later_work(self) -> None:
        hub: RealtimeEventHub[_Event] = RealtimeEventHub()
        hub.subscribe(lambda event: None)

        self.assertTrue(hub.close())
        self.assertFalse(hub.close())
        self.assertTrue(hub.is_closed)
        self.assertEqual(hub.subscriber_count, 0)

        with self.assertRaises(EventHubClosedError):
            hub.subscribe(lambda event: None)
        with self.assertRaises(EventHubClosedError):
            hub.emit(lambda sequence: _Event(sequence, "closed"))

        self.assertEqual(
            hub.diagnostics.rejected_after_close_count,
            1,
        )


if __name__ == "__main__":
    unittest.main()
