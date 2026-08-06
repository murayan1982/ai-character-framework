"""FW-RT6-2b Control A realtime event-hub primitive smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or host-application repository operation occurs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
from threading import Lock, Thread

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "89c0ba7ccf150658c5bace612e68bce876db4223"
EXPECTED_BASELINE_PARENT = "888d689fcf894fa7fa83eb6d0daa18b41f77726a"
EXPECTED_BASELINE_SUBJECT = "docs/test: accept recursive public safety"
EXPECTED_BASELINE_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_public_safety_acceptance.py",
    "scripts/smoke_v600_public_api_manifest.py",
    "scripts/smoke_v600_version_metadata.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_event_hub_contract.md",
    "framework/realtime_event_hub.py",
    "scripts/smoke_v600_realtime_event_hub_primitives.py",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    "elevenlabs",
    "pyvts",
    "websocket",
    "pyaudio",
    "sounddevice",
    "speech_recognition",
    "google.genai",
    "xai_sdk",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        paths.update(
            line.replace("\\", "/")
            for line in _git(*args).splitlines()
            if line.strip()
        )
    return paths


def _commit_surface(commit: str) -> set[str]:
    return {
        line.replace("\\", "/")
        for line in _git(
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            commit,
        ).splitlines()
        if line.strip()
    }


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^")
        == EXPECTED_BASELINE_PARENT,
        "baseline parent drift",
    )
    _assert(
        _git("show", "-s", "--format=%s", EXPECTED_BASELINE)
        == EXPECTED_BASELINE_SUBJECT,
        "baseline subject drift",
    )
    _assert(
        _commit_surface(EXPECTED_BASELINE) == EXPECTED_BASELINE_SURFACE,
        "Control D baseline surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control A surface: {sorted(_changed_paths())}",
    )
    print("[OK] accepted FW-RT6-2a baseline and exact five-file Control A surface conform")


@dataclass(frozen=True)
class _FakeEvent:
    sequence: object
    label: str
    dropped_sequence: object = None
    overflow_count: int = 0


def _event(label: str):
    return lambda sequence: _FakeEvent(sequence=sequence, label=label)


def _overflow(sequence, dropped_sequence, overflow_count):
    return _FakeEvent(
        sequence=sequence,
        label="overflow",
        dropped_sequence=dropped_sequence,
        overflow_count=overflow_count,
    )


def check_tokens_and_projection() -> None:
    from framework.realtime_event_hub import (
        EventSubscriptionToken,
        RealtimeEventHub,
    )

    hub = RealtimeEventHub[_FakeEvent](history_limit=8)
    canonical: list[tuple[int, str]] = []
    legacy: list[tuple[int, str]] = []

    canonical_token = hub.subscribe(
        lambda event: canonical.append((int(event.sequence), event.label))
    )
    legacy_token = hub.subscribe(
        lambda event: legacy.append((int(event.sequence), event.label)),
        legacy=True,
    )
    _assert(isinstance(canonical_token, EventSubscriptionToken), "canonical token type drift")
    _assert(isinstance(legacy_token, EventSubscriptionToken), "legacy token type drift")
    _assert(canonical_token != legacy_token, "subscription tokens collided")

    hub.emit(
        _event("one"),
        legacy_projector=lambda event: (
            _FakeEvent(event.sequence, f"legacy:{event.label}")
        ),
    )
    _assert(canonical == [(1, "one")], "canonical callback drift")
    _assert(legacy == [(1, "legacy:one")], "legacy projection drift")
    _assert(hub.unsubscribe(canonical_token) is True, "canonical unsubscribe failed")
    _assert(hub.unsubscribe(canonical_token) is False, "duplicate unsubscribe should be false")

    hub.emit(
        _event("two"),
        legacy_projector=lambda event: (
            _FakeEvent(event.sequence, f"legacy:{event.label}")
        ),
    )
    _assert(canonical == [(1, "one")], "unregistered canonical callback fired")
    _assert(legacy[-1] == (2, "legacy:two"), "legacy callback stopped unexpectedly")
    _assert(hub.subscriber_count == 1, "subscriber count drift")
    print("[OK] opaque registration tokens and canonical/legacy unregistration conform")


def check_callback_isolation_and_slow_policy() -> None:
    from framework.realtime_event_hub import RealtimeEventHub

    class FakeClock:
        def __init__(self) -> None:
            self.value = 0.0

        def __call__(self) -> float:
            return self.value

    clock = FakeClock()
    hub = RealtimeEventHub[_FakeEvent](
        history_limit=8,
        slow_callback_seconds=0.5,
        clock=clock,
    )
    delivered: list[str] = []

    def broken(_event_value: _FakeEvent) -> None:
        raise RuntimeError("private callback failure")

    def slow(event_value: _FakeEvent) -> None:
        clock.value += 1.0
        delivered.append(event_value.label)

    hub.subscribe(broken)
    hub.subscribe(slow)
    hub.emit(_event("first"))
    hub.emit(_event("second"))

    diagnostics = hub.diagnostics
    _assert(delivered == ["first", "second"], "healthy callback delivery drift")
    _assert(diagnostics.callback_error_count == 2, "callback failures escaped or were missed")
    _assert(diagnostics.slow_callback_count == 2, "slow callback policy counter drift")
    _assert(hub.subscriber_count == 2, "slow callback was silently evicted")
    print("[OK] callback exceptions are isolated and slow subscribers follow fixed retain-and-account policy")


def check_history_and_overflow() -> None:
    from framework.realtime_event_hub import RealtimeEventHub

    hub = RealtimeEventHub[_FakeEvent](history_limit=3)
    delivered: list[_FakeEvent] = []
    hub.subscribe(delivered.append)

    hub.emit(_event("one"), overflow_event_factory=_overflow)
    hub.emit(_event("two"), overflow_event_factory=_overflow)
    hub.emit(_event("three"), overflow_event_factory=_overflow)
    hub.emit(_event("four"), overflow_event_factory=_overflow)

    history = hub.event_history
    _assert(len(history) == 3, "bounded history size drift")
    _assert(
        [int(event.sequence) for event in history] == [3, 4, 5],
        "bounded history ordering drift",
    )
    _assert(
        [event.label for event in delivered]
        == ["one", "two", "three", "four", "overflow"],
        "overflow diagnostic delivery drift",
    )
    overflow = delivered[-1]
    _assert(int(overflow.dropped_sequence) == 1, "first dropped sequence drift")
    _assert(overflow.overflow_count == 2, "overflow count drift")
    diagnostics = hub.diagnostics
    _assert(diagnostics.history_overflow_count == 2, "history overflow counter drift")
    _assert(diagnostics.emitted_event_count == 5, "diagnostic event count drift")
    print("[OK] bounded history emits sequenced non-silent overflow diagnostics")


def check_concurrent_and_reentrant_order() -> None:
    from framework.realtime_event_hub import RealtimeEventHub

    hub = RealtimeEventHub[_FakeEvent](history_limit=512)
    observed: list[int] = []
    observed_lock = Lock()

    def record(event: _FakeEvent) -> None:
        with observed_lock:
            observed.append(int(event.sequence))

    hub.subscribe(record)

    def worker(worker_index: int) -> None:
        for event_index in range(20):
            hub.emit(_event(f"{worker_index}:{event_index}"))

    threads = [Thread(target=worker, args=(index,)) for index in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    _assert(observed == list(range(1, 161)), "concurrent callback order is not monotonic")
    _assert(
        [int(event.sequence) for event in hub.event_history]
        == list(range(1, 161)),
        "concurrent history order is not monotonic",
    )

    reentrant = RealtimeEventHub[_FakeEvent](history_limit=8)
    labels: list[str] = []

    def reentrant_callback(event: _FakeEvent) -> None:
        labels.append(event.label)
        if event.label == "outer":
            reentrant.emit(_event("inner"))

    reentrant.subscribe(reentrant_callback)
    reentrant.emit(_event("outer"))
    _assert(labels == ["outer", "inner"], "reentrant emission order drift")
    _assert(
        [int(event.sequence) for event in reentrant.event_history] == [1, 2],
        "reentrant sequence drift",
    )
    print("[OK] concurrent and reentrant emission remains serialized and monotonic")


def check_close_rejection() -> None:
    from framework.realtime_event_hub import (
        EventHubClosedError,
        RealtimeEventHub,
    )

    hub = RealtimeEventHub[_FakeEvent](history_limit=4)
    hub.subscribe(lambda _event_value: None)
    _assert(hub.close() is True, "first close should succeed")
    _assert(hub.close() is False, "second close should be idempotent")
    _assert(hub.is_closed is True, "closed state missing")
    _assert(hub.subscriber_count == 0, "close retained callbacks")

    try:
        hub.emit(_event("late"))
    except EventHubClosedError:
        pass
    else:
        raise AssertionError("post-close emission was accepted")

    try:
        hub.subscribe(lambda _event_value: None)
    except EventHubClosedError:
        pass
    else:
        raise AssertionError("post-close registration was accepted")

    _assert(hub.event_history == (), "post-close event entered history")
    _assert(
        hub.diagnostics.rejected_after_close_count == 1,
        "post-close emission rejection counter drift",
    )
    print("[OK] close is idempotent and rejects later emission/registration")


def check_public_surface_and_docs() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public count drift")
    for name in (
        "EventHubClosedError",
        "EventSubscriptionToken",
        "EventHubDiagnostics",
        "RealtimeEventHub",
    ):
        _assert(name not in PUBLIC_API_NAMES, f"Control A primitive leaked to root API: {name}")

    for relative in (
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-2b-A-EVENT-HUB-PRIMITIVES:BEGIN" in text,
            f"Control A marker missing: {relative}",
        )
        _assert(
            "RealtimeSession adoption: DEFERRED / Control B" in text,
            f"Control B deferral missing: {relative}",
        )

    contract = (
        PROJECT_ROOT / "docs" / "v600_realtime_event_hub_contract.md"
    ).read_text(encoding="utf-8")
    for phrase in (
        "synchronous serialized delivery",
        "callback exception escapes emitter: False",
        "slow subscriber automatic eviction: False",
        "history overflow silent: False",
        "post-close emission accepted: False",
    ):
        _assert(phrase in contract, f"contract phrase missing: {phrase}")

    print("[OK] 121-name root surface and Control A documentation conform")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] event-hub primitive imports stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_import_safety()
    check_tokens_and_projection()
    check_callback_isolation_and_slow_policy()
    check_history_and_overflow()
    check_concurrent_and_reentrant_order()
    check_close_rejection()
    check_public_surface_and_docs()
    check_import_safety()

    print("v600_rt6_2b_control_a_status: implemented-awaiting-review")
    print("v600_rt6_2b_control_a_exact_change_surface_count: 5")
    print("v600_rt6_2b_control_a_root_public_names: 121 / unchanged")
    print("v600_rt6_2b_control_a_realtime_session_changed: False")
    print("v600_rt6_2b_control_a_sequence_monotonic: PASS")
    print("v600_rt6_2b_control_a_subscription_token: True")
    print("v600_rt6_2b_control_a_callback_exception_breaks_emitter: False")
    print("v600_rt6_2b_control_a_bounded_history: True")
    print("v600_rt6_2b_control_a_slow_subscriber_policy: synchronous-serialized-retain-and-account")
    print("v600_rt6_2b_control_a_silent_overflow: False")
    print("v600_rt6_2b_control_a_concurrent_emission_serialized: True")
    print("v600_rt6_2b_control_a_post_close_emission_accepted: False")
    print("v600_rt6_2b_control_a_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2b_next_control: FW-RT6-2b Control B")
    print("v600_rt6_2b_next_control_authorized: False")
    print("[OK] FW-RT6-2b Control A realtime event-hub primitives passed")


if __name__ == "__main__":
    main()
