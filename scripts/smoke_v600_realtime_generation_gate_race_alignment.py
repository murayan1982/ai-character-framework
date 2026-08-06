"""FW-RT6-2d Control C generation race and VTS alignment smoke.

Offline/mock-safe: uses only in-memory threads and an injected fake async VTS
client. It does not import real pyvts, open a network connection, use a
microphone, play audio, execute real motion, read private configuration, or
access a host-application repository.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE = "56ca83965f288d0c591a3969c45cb92b820a380a"
EXPECTED_BASELINE_PARENT = "e3f5ce7088596e1f2ceaa3c504a16b35c47863b8"
EXPECTED_BASELINE_SUBJECT = "refactor/test: adopt realtime generation gate"
EXPECTED_BASELINE_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_generation_gate_contract.md",
    "framework/realtime_session.py",
    "scripts/smoke_v600_realtime_generation_gate_primitives.py",
    "scripts/smoke_v600_realtime_generation_gate_session_adoption.py",
}
EXPECTED_SURFACE = {
    "docs/app_integration_contract.md",
    "docs/public_facade.md",
    "docs/v600_realtime_generation_gate_contract.md",
    "scripts/smoke_v600_realtime_generation_gate_primitives.py",
    "scripts/smoke_v600_realtime_generation_gate_session_adoption.py",
    "scripts/smoke_v600_realtime_generation_gate_race_alignment.py",
}
RUNTIME_PATHS = (
    "framework/realtime_session.py",
    "framework/realtime_generation_gate.py",
    "framework/realtime_event_hub.py",
    "framework/realtime_terminal_registry.py",
    "framework/vtube_studio_pyvts_transport.py",
    "framework/vtube_studio_transport.py",
)
PROVIDER_MODULE_PREFIXES = (
    "elevenlabs",
    "pyvts",
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


def _assert_runtime_unchanged() -> None:
    for relative in RUNTIME_PATHS:
        working = _git("hash-object", relative)
        committed = _git("rev-parse", f"HEAD:{relative}")
        _assert(working == committed, f"runtime source changed: {relative}")


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE, "unexpected baseline")
    _assert(
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
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
        "accepted Control B surface drift",
    )
    _assert(
        _changed_paths() == EXPECTED_SURFACE,
        f"unexpected Control C surface: {sorted(_changed_paths())}",
    )
    _assert_runtime_unchanged()
    print("[OK] accepted Control B baseline and exact six-file docs/test-only Control C surface conform")


def _start_generation(session: Any, framework: Any) -> tuple[Any, Any]:
    turn_id = framework.TurnId.new()
    generation_id = session._start_turn_generation(turn_id)
    return turn_id, generation_id


def _envelope(
    Envelope: Any,
    *,
    turn_id: Any,
    generation_id: Any,
    stage: str,
    value: Any,
) -> Any:
    return Envelope(
        turn_id=turn_id,
        generation_id=generation_id,
        stage=stage,
        value=value,
    )


def _thread_call(
    target: Callable[[], Any],
    *,
    name: str,
) -> tuple[Thread, list[Any], list[BaseException], Event, Event]:
    values: list[Any] = []
    errors: list[BaseException] = []
    started = Event()
    finished = Event()

    def run() -> None:
        started.set()
        try:
            values.append(target())
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    thread = Thread(target=run, name=name)
    thread.start()
    return thread, values, errors, started, finished


def _join(thread: Thread, errors: list[BaseException], *, label: str) -> None:
    thread.join(timeout=3.0)
    _assert(not thread.is_alive(), f"{label} thread did not finish")
    if errors:
        raise AssertionError(f"{label} thread failed: {errors[0]!r}") from errors[0]


def _assert_stale(
    decision: Any,
    StaleReason: Any,
    AdvanceReason: Any,
    *,
    retired_by: str,
) -> None:
    _assert(not decision.accepted, "completion unexpectedly accepted")
    _assert(
        decision.stale_reason is StaleReason.RETIRED_GENERATION,
        "stale reason drift",
    )
    _assert(
        decision.retired_by is AdvanceReason(retired_by),
        f"retirement reason drift: {retired_by}",
    )


def _completion_wins(
    session: Any,
    Envelope: Any,
    envelope: Any,
    invalidator: Callable[[], Any],
    *,
    label: str,
) -> tuple[Any, list[Any]]:
    entered = Event()
    release = Event()
    delivered: list[Any] = []

    def deliver(value: Any) -> None:
        entered.set()
        _assert(release.wait(timeout=3.0), f"{label} release timed out")
        delivered.append(value)

    completion, decisions, completion_errors, _, _ = _thread_call(
        lambda: session._apply_stage_completion(envelope, deliver=deliver),
        name=f"completion-wins-{label}",
    )
    _assert(entered.wait(timeout=3.0), f"{label} completion did not hold lock")
    invalidator_thread, _, invalidator_errors, _, invalidator_finished = _thread_call(
        invalidator,
        name=f"{label}-after-completion",
    )
    _assert(
        not invalidator_finished.wait(timeout=0.1),
        f"{label} completed while completion delivery held the lock",
    )
    release.set()
    _join(completion, completion_errors, label=f"completion-wins-{label}")
    _join(invalidator_thread, invalidator_errors, label=f"{label}-after-completion")
    _assert(decisions[0].accepted, f"{label} lock-winning completion rejected")
    return decisions[0], delivered


def _advance_wins(
    session: Any,
    envelope: Any,
    advance: Callable[[], Any],
    *,
    label: str,
) -> tuple[Any, list[Any]]:
    gate_held = Event()
    proceed = Event()

    def winner() -> Any:
        with session._serialized_operation():
            gate_held.set()
            _assert(proceed.wait(timeout=3.0), f"{label} proceed timed out")
            return advance()

    advance_thread, _, advance_errors, _, _ = _thread_call(
        winner,
        name=f"{label}-wins",
    )
    _assert(gate_held.wait(timeout=3.0), f"{label} did not hold operation lock")
    delivered: list[Any] = []
    completion, decisions, completion_errors, _, _ = _thread_call(
        lambda: session._apply_stage_completion(envelope, deliver=delivered.append),
        name=f"completion-after-{label}",
    )
    proceed.set()
    _join(advance_thread, advance_errors, label=f"{label}-wins")
    _join(completion, completion_errors, label=f"completion-after-{label}")
    return decisions[0], delivered


def check_interrupt_cancel_races(
    framework: Any,
    Envelope: Any,
    StaleReason: Any,
    AdvanceReason: Any,
) -> None:
    for label, method, reason in (
        ("interrupt", "interrupt", "interrupt"),
        ("cancel", "cancel_current_turn", "cancel"),
    ):
        session = framework.create_realtime_session()
        turn_id, generation_id = _start_generation(session, framework)
        session._set_phase(framework.RealtimePhase.THINKING)
        value = f"stale-{label}-secret-marker"
        envelope = _envelope(
            Envelope,
            turn_id=turn_id,
            generation_id=generation_id,
            stage="voice_output",
            value=value,
        )
        decision, delivered = _advance_wins(
            session,
            envelope,
            lambda: getattr(session, method)(),
            label=label,
        )
        _assert_stale(
            decision,
            StaleReason,
            AdvanceReason,
            retired_by=reason,
        )
        _assert(not delivered, f"{label}-winning race delivered stale completion")
        _assert(
            value not in repr(session.event_history),
            f"{label} stale value leaked into diagnostic",
        )
        session.close()

        session = framework.create_realtime_session()
        turn_id, generation_id = _start_generation(session, framework)
        session._set_phase(framework.RealtimePhase.THINKING)
        envelope = _envelope(
            Envelope,
            turn_id=turn_id,
            generation_id=generation_id,
            stage="text_generation",
            value=f"current-before-{label}",
        )
        decision, delivered = _completion_wins(
            session,
            Envelope,
            envelope,
            lambda: getattr(session, method)(),
            label=label,
        )
        _assert(decision.accepted, f"completion-winning {label} race rejected")
        _assert(
            delivered == [f"current-before-{label}"],
            f"completion-winning {label} delivery drift",
        )
        session.close()

    print("[OK] completion-vs-interrupt/cancel both lock winners conform")


def check_close_races(
    framework: Any,
    Envelope: Any,
    StaleReason: Any,
    AdvanceReason: Any,
) -> None:
    session = framework.create_realtime_session()
    events: list[Any] = []
    session.on_event(events.append)
    turn_id, generation_id = _start_generation(session, framework)
    envelope = _envelope(
        Envelope,
        turn_id=turn_id,
        generation_id=generation_id,
        stage="voice_output",
        value="post-close artifact",
    )
    stale_before = session.generation_diagnostics["stale_completion_count"]
    decision, delivered = _advance_wins(
        session,
        envelope,
        session.close,
        label="close",
    )
    _assert_stale(
        decision,
        StaleReason,
        AdvanceReason,
        retired_by="session_closed",
    )
    _assert(not delivered, "close-winning race delivered completion")
    _assert(
        [event.type for event in events]
        == [framework.RealtimeEventType.SESSION_CLOSED],
        "close-winning race emitted active stale diagnostic",
    )
    _assert(
        session.generation_diagnostics["stale_completion_count"]
        == stale_before + 1,
        "post-close stale drop was not count-observable",
    )

    session = framework.create_realtime_session()
    events = []
    session.on_event(events.append)
    turn_id, generation_id = _start_generation(session, framework)
    envelope = _envelope(
        Envelope,
        turn_id=turn_id,
        generation_id=generation_id,
        stage="text_generation",
        value="current before close",
    )
    decision, delivered = _completion_wins(
        session,
        Envelope,
        envelope,
        session.close,
        label="close",
    )
    _assert(decision.accepted, "completion-winning close race rejected")
    _assert(delivered == ["current before close"], "close delivery drift")
    _assert(
        sum(
            event.type is framework.RealtimeEventType.SESSION_CLOSED
            for event in events
        )
        == 1,
        "SESSION_CLOSED count drift",
    )
    print("[OK] completion-vs-close both lock winners and post-close silence conform")


def check_new_turn_races(
    framework: Any,
    Envelope: Any,
    StaleReason: Any,
    AdvanceReason: Any,
) -> None:
    session = framework.create_realtime_session()
    old_turn, old_generation = _start_generation(session, framework)
    new_turn = framework.TurnId.new()
    envelope = _envelope(
        Envelope,
        turn_id=old_turn,
        generation_id=old_generation,
        stage="text_generation",
        value="old turn delta",
    )
    decision, delivered = _advance_wins(
        session,
        envelope,
        lambda: session._start_turn_generation(new_turn),
        label="new-turn",
    )
    _assert_stale(
        decision,
        StaleReason,
        AdvanceReason,
        retired_by="new_turn",
    )
    _assert(not delivered, "new-turn-winning race delivered old turn delta")
    session.close()

    session = framework.create_realtime_session()
    old_turn, old_generation = _start_generation(session, framework)
    new_turn = framework.TurnId.new()
    envelope = _envelope(
        Envelope,
        turn_id=old_turn,
        generation_id=old_generation,
        stage="motion",
        value="current motion completion",
    )
    def start_new_turn_serialized() -> Any:
        with session._serialized_operation():
            return session._start_turn_generation(new_turn)

    decision, delivered = _completion_wins(
        session,
        Envelope,
        envelope,
        start_new_turn_serialized,
        label="new-turn",
    )
    _assert(decision.accepted, "completion-winning new-turn race rejected")
    _assert(
        delivered == ["current motion completion"],
        "completion-winning new-turn delivery drift",
    )
    session.close()
    print("[OK] completion-vs-new-turn both lock winners conform")


def check_terminal_callback_reentry(
    framework: Any,
    Envelope: Any,
    StaleReason: Any,
    AdvanceReason: Any,
) -> None:
    session = framework.create_realtime_session()
    events: list[Any] = []
    legacy_events: list[Any] = []
    decisions: list[Any] = []
    delivered: list[Any] = []

    def callback(event: Any) -> None:
        events.append(event)
        if event.type is framework.RealtimeEventType.TURN_COMPLETED:
            decisions.append(
                session._apply_stage_completion(
                    _envelope(
                        Envelope,
                        turn_id=event.turn_id,
                        generation_id=event.generation_id,
                        stage="voice_output",
                        value="terminal callback old artifact",
                    ),
                    deliver=delivered.append,
                )
            )

    session.on_event(callback)
    session.on_legacy_event(legacy_events.append)
    result = session.run_turn(input_text="terminal race")
    _assert(len(decisions) == 1, "terminal callback reentry count drift")
    _assert_stale(
        decisions[0],
        StaleReason,
        AdvanceReason,
        retired_by="turn_terminal",
    )
    _assert(not delivered, "terminal callback delivered stale completion")
    event_types = [event.type for event in events]
    _assert(
        event_types.index(framework.RealtimeEventType.TURN_COMPLETED)
        < event_types.index(framework.RealtimeEventType.STALE_RESULT_DROPPED),
        "terminal/stale event ordering drift",
    )
    _assert(
        all(
            event.type is not framework.RealtimeEventType.STALE_RESULT_DROPPED
            for event in legacy_events
        ),
        "stale diagnostic leaked to legacy callback",
    )
    _assert(len(session.terminal_results) == 1, "terminal registry size drift")
    _assert(session.terminal_results[0] is result, "terminal result identity drift")
    session.close()
    print("[OK] terminal callback reentry is stale after turn-terminal retirement")


def check_session_source_linearization() -> None:
    source = (
        PROJECT_ROOT / "framework" / "realtime_session.py"
    ).read_text(encoding="utf-8")
    apply_start = source.index("    def _apply_stage_completion(")
    apply_end = source.index("    def _session_closed_error(", apply_start)
    apply_source = source[apply_start:apply_end]
    _assert(
        "with self._serialized_operation():" in apply_source,
        "completion ingress is not operation-lock owned",
    )
    _assert(
        apply_source.index("admit_completion")
        < apply_source.index("deliver(envelope.value)"),
        "completion delivery precedes admission",
    )
    terminal_start = source.index("    def _commit_terminal_result(")
    terminal_end = source.index("    @contextmanager", terminal_start)
    terminal_source = source[terminal_start:terminal_end]
    _assert(
        terminal_source.index("_advance_generation")
        < terminal_source.index("self._transition("),
        "terminal event precedes generation retirement",
    )
    close_start = source.index("    def close(self) -> None:")
    close_end = source.index("    def _close_now(", close_start)
    close_source = source[close_start:close_end]
    _assert(
        close_source.index("_advance_generation")
        < close_source.index("if self._operation_depth > 0:"),
        "close deferred decision precedes generation retirement",
    )
    print("[OK] session source fixes admission/delivery and retirement ordering")


def check_vts_source_alignment() -> None:
    source = (
        PROJECT_ROOT / "framework" / "vtube_studio_pyvts_transport.py"
    ).read_text(encoding="utf-8")
    _assert("self._lifecycle_generation = 0" in source, "VTS generation missing")
    _assert(
        "generation = self._lifecycle_generation" in source,
        "VTS operation generation capture missing",
    )
    _assert(
        source.count("if self._generation_changed(generation):") >= 4,
        "VTS post-await generation checks incomplete",
    )
    changed_start = source.index("    def _generation_changed(")
    changed_end = source.index("    def _reset_runtime_state(", changed_start)
    changed_source = source[changed_start:changed_end]
    _assert("self._closed" in changed_source, "VTS closed check missing")
    _assert(
        "generation != self._lifecycle_generation" in changed_source,
        "VTS generation mismatch check missing",
    )
    close_start = source.rindex("    async def close(self)")
    close_source = source[close_start:]
    _assert(
        close_source.index("self._closed = True")
        < close_source.index("self._lifecycle_generation += 1")
        < close_source.index("await asyncio.wait_for("),
        "VTS close generation order drift",
    )
    _assert("asyncio.create_task(" not in source, "VTS background task introduced")
    _assert(
        '"automatic_retry_executed": False' in source,
        "VTS automatic retry declaration drift",
    )
    _assert(
        '"automatic_reconnect_executed": False' in source,
        "VTS automatic reconnect declaration drift",
    )
    print("[OK] VTS source lifecycle-generation ordering aligns without runtime change")


async def _run_fake_vts_late_suppression() -> None:
    from framework.motion import MotionIntent
    from framework.motion_adapter_execution import MotionAdapterExecutionConfig
    from framework.vtube_studio_pyvts_transport import (
        VTubeStudioPyvtsTransport,
        VTubeStudioPyvtsTransportConfig,
    )
    from framework.vtube_studio_transport import (
        VTubeStudioHotkeyRequest,
        VTubeStudioTransportOutcome,
    )

    class FakeRequests:
        def authentication(self, token: str) -> dict[str, str]:
            _assert(token == "fake-token", "fake authentication token drift")
            return {"kind": "authentication"}

        def requestHotKeyList(self) -> dict[str, str]:
            return {"kind": "inventory"}

        def requestTriggerHotKey(self, name: str) -> dict[str, str]:
            _assert(name == "Wave", "fake hotkey name drift")
            return {"kind": "trigger"}

    class FakeClient:
        def __init__(self) -> None:
            self.vts_request = FakeRequests()
            self.trigger_started = asyncio.Event()
            self.trigger_release = asyncio.Event()

        async def connect(self) -> None:
            return None

        async def request(self, request: dict[str, str]) -> dict[str, Any]:
            kind = request["kind"]
            if kind == "authentication":
                return {
                    "messageType": "AuthenticationResponse",
                    "data": {"authenticated": True},
                }
            if kind == "inventory":
                return {
                    "messageType": "HotkeyListResponse",
                    "data": {
                        "modelLoaded": True,
                        "availableHotkeys": [{"name": "Wave"}],
                    },
                }
            if kind == "trigger":
                self.trigger_started.set()
                await self.trigger_release.wait()
                return {
                    "messageType": "HotkeyTriggerResponse",
                    "data": {},
                }
            raise AssertionError(f"unexpected fake request: {request}")

        async def close(self) -> None:
            return None

    execution = MotionAdapterExecutionConfig(
        adapter="vts",
        real_adapter_enabled=True,
        allow_provider_execution=True,
        endpoint_configured=True,
        runtime_available=True,
        token_available=True,
        model_selected=True,
        configured_intents=(MotionIntent.GESTURE,),
    )
    config = VTubeStudioPyvtsTransportConfig(
        execution_config=execution,
        endpoint_host="127.0.0.1",
        endpoint_port=8001,
        authentication_token="fake-token",
    )
    client = FakeClient()
    imported_names: list[str] = []
    transport = VTubeStudioPyvtsTransport(
        config=config,
        module_importer=lambda name: imported_names.append(name) or object(),
        client_factory=lambda module, resolved: client,
    )
    preflight = await transport.preflight()
    _assert(
        preflight.outcome is VTubeStudioTransportOutcome.READY,
        "fake VTS preflight did not become ready",
    )
    trigger = asyncio.create_task(
        transport.trigger_hotkey(
            VTubeStudioHotkeyRequest(
                intent=MotionIntent.GESTURE,
                hotkey_name="Wave",
            )
        )
    )
    await asyncio.wait_for(client.trigger_started.wait(), timeout=3.0)
    close_result = await transport.close()
    _assert(
        close_result.outcome is VTubeStudioTransportOutcome.COMPLETED,
        "fake VTS close outcome drift",
    )
    client.trigger_release.set()
    late = await asyncio.wait_for(trigger, timeout=3.0)
    _assert(
        late.outcome is VTubeStudioTransportOutcome.CLOSED,
        "late fake VTS completion was not closed",
    )
    _assert(
        late.public_metadata["late_completion_suppressed"] is True,
        "late fake VTS completion was not marked suppressed",
    )
    _assert(
        late.public_metadata["reason"] == "late_completion_suppressed",
        "late fake VTS suppression reason drift",
    )
    _assert(
        late.public_metadata["real_hotkey_triggered"] is False,
        "fake VTS claimed a real hotkey trigger",
    )
    _assert(imported_names == ["pyvts"], "injected importer call drift")
    _assert("pyvts" not in sys.modules, "real pyvts module was imported")


def check_vts_fake_alignment() -> None:
    asyncio.run(_run_fake_vts_late_suppression())
    print("[OK] injected fake VTS close wins and suppresses late completion")


def check_docs_public_and_safety() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_realtime_generation_gate_contract.md",
    ):
        normalized = " ".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8").split()
        )
        for phrase in (
            "FW-RT6-2d-C-RACE-VTS-ALIGNMENT:BEGIN",
            "6 files / docs-test-only",
            "completion application wins",
            "generation advance wins",
            "VTS lifecycle-generation alignment",
            "Control D: NOT_AUTHORIZED",
        ):
            _assert(
                phrase in normalized,
                f"Control C contract missing {phrase}: {relative}",
            )

    import framework

    _assert(len(framework.__all__) == 121, "root-public name count drift")
    _assert(
        "RealtimeGenerationGate" not in framework.__all__,
        "internal generation gate became root-public",
    )
    forbidden = sorted(
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in PROVIDER_MODULE_PREFIXES
        )
    )
    _assert(not forbidden, f"real provider modules loaded: {forbidden}")
    print("[OK] Control C docs, root-public compatibility, and real-provider safety conform")


def main() -> None:
    check_repository_contract()

    import framework
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )

    check_session_source_linearization()
    check_interrupt_cancel_races(
        framework,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
        GenerationAdvanceReason,
    )
    check_close_races(
        framework,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
        GenerationAdvanceReason,
    )
    check_new_turn_races(
        framework,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
        GenerationAdvanceReason,
    )
    check_terminal_callback_reentry(
        framework,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
        GenerationAdvanceReason,
    )
    check_vts_source_alignment()
    check_vts_fake_alignment()
    check_docs_public_and_safety()

    print("v600_rt6_2d_control_c_status: implemented-awaiting-review")
    print("v600_rt6_2d_control_c_exact_change_surface_count: 6")
    print("v600_rt6_2d_control_c_runtime_source_changed: False")
    print("v600_rt6_2d_control_c_root_public_names: 121 / unchanged")
    print("v600_rt6_2d_control_c_completion_interrupt_both_winners: True")
    print("v600_rt6_2d_control_c_completion_cancel_both_winners: True")
    print("v600_rt6_2d_control_c_completion_close_both_winners: True")
    print("v600_rt6_2d_control_c_completion_new_turn_both_winners: True")
    print("v600_rt6_2d_control_c_terminal_callback_reentry_stale: True")
    print("v600_rt6_2d_control_c_old_turn_delta_delivered: False")
    print("v600_rt6_2d_control_c_old_tts_artifact_delivered: False")
    print("v600_rt6_2d_control_c_old_motion_completion_delivered: False")
    print("v600_rt6_2d_control_c_post_close_active_event: False")
    print("v600_rt6_2d_control_c_vts_source_changed: False")
    print("v600_rt6_2d_control_c_real_pyvts_imported: False")
    print("v600_rt6_2d_control_c_real_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2d_control_d_authorized: False")
    print("[OK] FW-RT6-2d Control C race and VTS generation alignment conform")


if __name__ == "__main__":
    main()
