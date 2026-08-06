"""FW-RT6-2d Control A provider-neutral generation gate primitive smoke.

Offline/mock-safe: no provider SDK, network, microphone, playback, VTube Studio,
private configuration, or DRC repository operation occurs.
"""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
from threading import Barrier, Thread

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
        _git("rev-parse", "origin/main") == EXPECTED_BASELINE,
        "origin/main baseline drift",
    )
    _assert(
        _git("rev-parse", f"{EXPECTED_BASELINE}^") == EXPECTED_BASELINE_PARENT,
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
    print("[OK] accepted Control B baseline and exact six-file docs/test-only Control C surface conform")


def check_root_public_compatibility() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES

    _assert(tuple(framework.__all__) == PUBLIC_API_NAMES, "framework.__all__ drift")
    _assert(len(PUBLIC_API_NAMES) == 121, "root-public name count drift")
    for name in (
        "RealtimeGenerationGate",
        "RealtimeStageCompletionEnvelope",
        "GenerationAdvanceReason",
        "StaleCompletionReason",
        "GenerationAdmissionDecision",
    ):
        _assert(name not in framework.__all__, f"internal generation symbol leaked: {name}")
        _assert(name not in framework.__dict__, f"internal generation binding leaked: {name}")
    _assert(
        "framework.realtime_generation_gate" not in sys.modules,
        "root import eagerly loaded the internal generation gate",
    )
    print("[OK] root-public 121-name surface stays unchanged and generation gate stays internal")


def check_source_contract() -> None:
    path = PROJECT_ROOT / "framework" / "realtime_generation_gate.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported_roots.add((node.module or "").split(".", 1)[0])

    allowed_roots = {
        "__future__",
        "dataclasses",
        "enum",
        "threading",
        "types",
        "typing",
        "identity",
    }
    unexpected = sorted(imported_roots - allowed_roots)
    _assert(not unexpected, f"generation gate imports unexpected roots: {unexpected}")

    for phrase in (
        "class GenerationAdvanceReason(str, Enum):",
        "class StaleCompletionReason(str, Enum):",
        "class RealtimeStageCompletionEnvelope",
        "class GenerationAdmissionDecision",
        "class RealtimeGenerationGate:",
        "def start_generation(",
        "def advance(",
        "def admit_completion(",
        "with self._lock:",
        "GenerationId.new()",
        "MappingProxyType(",
    ):
        _assert(phrase in source, f"generation gate source phrase missing: {phrase}")

    _assert(
        "provider" not in " ".join(sorted(imported_roots)).lower(),
        "generation gate imported a provider module",
    )
    print("[OK] generation gate source is provider-neutral and lock-owned")


def check_start_advance_and_stale_reasons() -> None:
    from framework.identity import GenerationId, TurnId
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )

    gate = RealtimeGenerationGate()
    _assert(gate.current_generation_id is None, "gate started active")
    _assert(gate.current_turn_id is None, "gate started with a turn")
    _assert(
        gate.advance(GenerationAdvanceReason.INTERRUPT) is None,
        "no-active advance should be a no-op",
    )

    turn_a = TurnId.new()
    generation_a = gate.start_generation(turn_a)
    _assert(isinstance(generation_a, GenerationId), "fresh generation type drift")
    _assert(gate.current_generation_id == generation_a, "current generation drift")
    _assert(gate.current_turn_id == turn_a, "current turn drift")

    accepted = gate.admit_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_a,
            generation_id=generation_a,
            stage="text_generation",
            value={"delta": "accepted"},
        )
    )
    _assert(accepted.accepted, "current completion was rejected")
    _assert(accepted.stale_reason is None, "accepted completion has stale reason")
    _assert(accepted.current_generation_id == generation_a, "accepted current ID drift")

    turn_b = TurnId.new()
    generation_b = gate.start_generation(turn_b)
    _assert(generation_b != generation_a, "new turn reused a generation")

    stale_value = {"credential": "must-not-appear-in-repr"}
    retired = gate.admit_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_a,
            generation_id=generation_a,
            stage="text_generation",
            value=stale_value,
        )
    )
    _assert(not retired.accepted, "retired generation was accepted")
    _assert(
        retired.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
        "retired generation reason drift",
    )
    _assert(
        retired.retired_by is GenerationAdvanceReason.NEW_TURN,
        "new-turn retirement reason drift",
    )
    _assert("must-not-appear-in-repr" not in repr(retired), "completion value leaked in repr")

    wrong_turn = gate.admit_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_a,
            generation_id=generation_b,
            stage="voice_output",
            value="artifact",
        )
    )
    _assert(
        wrong_turn.stale_reason is StaleCompletionReason.TURN_MISMATCH,
        "turn mismatch reason drift",
    )

    unknown = gate.admit_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_b,
            generation_id=GenerationId.new(),
            stage="motion",
            value="done",
        )
    )
    _assert(
        unknown.stale_reason is StaleCompletionReason.UNKNOWN_GENERATION,
        "unknown generation reason drift",
    )

    retired_id = gate.advance(GenerationAdvanceReason.INTERRUPT)
    _assert(retired_id == generation_b, "interrupt retired the wrong generation")
    interrupted = gate.admit_completion(
        RealtimeStageCompletionEnvelope(
            turn_id=turn_b,
            generation_id=generation_b,
            stage="voice_output",
            value="late",
        )
    )
    _assert(
        interrupted.retired_by is GenerationAdvanceReason.INTERRUPT,
        "interrupt retirement reason was not retained",
    )

    diagnostics = gate.diagnostics
    _assert(
        set(diagnostics)
        == {
            "generation_start_count",
            "generation_advance_count",
            "accepted_completion_count",
            "stale_completion_count",
            "active_generation_count",
            "registry_size",
        },
        "generation diagnostics keys drift",
    )
    _assert(diagnostics["generation_start_count"] == 2, "start count drift")
    _assert(diagnostics["generation_advance_count"] == 2, "advance count drift")
    _assert(diagnostics["accepted_completion_count"] == 1, "accepted count drift")
    _assert(diagnostics["stale_completion_count"] == 4, "stale count drift")
    _assert(diagnostics["active_generation_count"] == 0, "active count drift")
    _assert(diagnostics["registry_size"] == 2, "registry size drift")
    try:
        diagnostics["stale_completion_count"] = 0
    except TypeError:
        pass
    else:
        raise AssertionError("generation diagnostics are mutable")
    print("[OK] fresh, retired, unknown, and turn-mismatch admission semantics conform")


def check_all_advance_reasons_and_noop_rules() -> None:
    from framework.identity import TurnId
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )

    gate = RealtimeGenerationGate()
    for reason in GenerationAdvanceReason:
        turn_id = TurnId.new()
        generation_id = gate.start_generation(turn_id)
        retired = gate.advance(reason)
        _assert(retired == generation_id, f"{reason.value} retired wrong generation")
        decision = gate.admit_completion(
            RealtimeStageCompletionEnvelope(
                turn_id=turn_id,
                generation_id=generation_id,
                stage="stage",
                value=reason.value,
            )
        )
        _assert(
            decision.stale_reason is StaleCompletionReason.RETIRED_GENERATION,
            f"{reason.value} did not classify as retired",
        )
        _assert(
            decision.retired_by is reason,
            f"{reason.value} retirement reason was not retained",
        )
        before = dict(gate.diagnostics)
        _assert(gate.advance(reason) is None, f"{reason.value} no-active advance changed")
        _assert(dict(gate.diagnostics) == before, "no-active advance changed diagnostics")

    diagnostics = gate.diagnostics
    _assert(
        diagnostics["generation_start_count"] == len(GenerationAdvanceReason),
        "advance-reason start count drift",
    )
    _assert(
        diagnostics["generation_advance_count"] == len(GenerationAdvanceReason),
        "advance-reason count drift",
    )
    print("[OK] all generation advance reasons retire once and no-active repeats are no-ops")


def check_concurrent_admission_is_atomic() -> None:
    from framework.identity import TurnId
    from framework.realtime_generation_gate import (
        GenerationAdvanceReason,
        RealtimeGenerationGate,
        RealtimeStageCompletionEnvelope,
        StaleCompletionReason,
    )

    gate = RealtimeGenerationGate()
    turn_id = TurnId.new()
    generation_id = gate.start_generation(turn_id)

    current_thread_count = 8
    current_barrier = Barrier(current_thread_count)
    current_decisions = []
    failures = []

    def admit_current(index: int) -> None:
        try:
            current_barrier.wait(timeout=5)
            current_decisions.append(
                gate.admit_completion(
                    RealtimeStageCompletionEnvelope(
                        turn_id=turn_id,
                        generation_id=generation_id,
                        stage="response_delta",
                        value=index,
                    )
                )
            )
        except Exception as exc:
            failures.append(exc)

    threads = [
        Thread(target=admit_current, args=(index,))
        for index in range(current_thread_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    _assert(not any(thread.is_alive() for thread in threads), "current admission hung")
    _assert(not failures, f"current admission failure: {failures!r}")
    _assert(
        len(current_decisions) == current_thread_count
        and all(decision.accepted for decision in current_decisions),
        "current generation completion was not atomically accepted",
    )

    gate.advance(GenerationAdvanceReason.CANCEL)
    stale_thread_count = 8
    stale_barrier = Barrier(stale_thread_count)
    stale_decisions = []

    def admit_stale(index: int) -> None:
        try:
            stale_barrier.wait(timeout=5)
            stale_decisions.append(
                gate.admit_completion(
                    RealtimeStageCompletionEnvelope(
                        turn_id=turn_id,
                        generation_id=generation_id,
                        stage="audio_artifact",
                        value=index,
                    )
                )
            )
        except Exception as exc:
            failures.append(exc)

    threads = [
        Thread(target=admit_stale, args=(index,))
        for index in range(stale_thread_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    _assert(not any(thread.is_alive() for thread in threads), "stale admission hung")
    _assert(not failures, f"stale admission failure: {failures!r}")
    _assert(
        len(stale_decisions) == stale_thread_count
        and all(
            not decision.accepted
            and decision.stale_reason is StaleCompletionReason.RETIRED_GENERATION
            and decision.retired_by is GenerationAdvanceReason.CANCEL
            for decision in stale_decisions
        ),
        "retired generation completion was not atomically rejected",
    )

    diagnostics = gate.diagnostics
    _assert(
        diagnostics["accepted_completion_count"] == current_thread_count,
        "concurrent accepted count drift",
    )
    _assert(
        diagnostics["stale_completion_count"] == stale_thread_count,
        "concurrent stale count drift",
    )
    print("[OK] concurrent current completions accept and retired completions reject atomically")


def check_docs_and_scope() -> None:
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_realtime_generation_gate_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        normalized_text = " ".join(text.split())
        for phrase in (
            "FW-RT6-2d-A-GENERATION-GATE-PRIMITIVES:BEGIN",
            "fresh opaque GenerationId",
            "GenerationAdvanceReason",
            "retired_generation",
            "unknown_generation",
            "turn_mismatch",
            "Control B",
            "NOT_AUTHORIZED",
        ):
            _assert(
                phrase in normalized_text,
                f"generation contract missing {phrase}: {relative}",
            )

    session_source = (
        PROJECT_ROOT / "framework" / "realtime_session.py"
    ).read_text(encoding="utf-8")
    _assert(
        "_generation_gate" in session_source,
        "Control B session generation ownership is missing",
    )
    _assert(
        "_apply_stage_completion" in session_source,
        "Control B central completion ingress is missing",
    )
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_realtime_generation_gate_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-2d-B-REALTIME-SESSION-GENERATION-ADOPTION:BEGIN" in text,
            f"Control B adoption marker missing: {relative}",
        )
    for relative in (
        "docs/app_integration_contract.md",
        "docs/public_facade.md",
        "docs/v600_realtime_generation_gate_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert(
            "FW-RT6-2d-C-RACE-VTS-ALIGNMENT:BEGIN" in text,
            f"Control C race/VTS marker missing: {relative}",
        )
    print("[OK] Control A primitives remain documented through Control C race alignment")


def check_import_safety() -> None:
    forbidden = sorted(
        name
        for name in sys.modules
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not forbidden, f"forbidden provider/runtime imports loaded: {forbidden}")
    print("[OK] Control A validation stayed provider/runtime safe")


def main() -> None:
    check_repository_contract()
    check_root_public_compatibility()
    check_source_contract()
    check_import_safety()
    check_start_advance_and_stale_reasons()
    check_all_advance_reasons_and_noop_rules()
    check_concurrent_admission_is_atomic()
    check_docs_and_scope()
    check_import_safety()

    print("v600_rt6_2d_control_a_status: accepted-control-c-regression")
    print("v600_rt6_2d_control_a_exact_change_surface_count: 6")
    print("v600_rt6_2d_control_a_generation_gate_internal: True")
    print("v600_rt6_2d_control_a_root_public_names: 121 / unchanged")
    print("v600_rt6_2d_control_a_generation_start_fresh: True")
    print("v600_rt6_2d_control_a_retirement_reason_retained: True")
    print("v600_rt6_2d_control_a_current_completion_accepted: True")
    print("v600_rt6_2d_control_a_retired_completion_rejected: True")
    print("v600_rt6_2d_control_a_unknown_completion_rejected: True")
    print("v600_rt6_2d_control_a_turn_mismatch_rejected: True")
    print("v600_rt6_2d_control_a_generation_diagnostics_immutable: True")
    print("v600_rt6_2d_control_a_session_adoption: implemented-Control-B")
    print("v600_rt6_2d_control_a_stale_diagnostic_event: implemented-Control-B")
    print("v600_rt6_2d_control_a_vts_alignment: verified-Control-C")
    print("v600_rt6_2d_control_a_provider_network_microphone_playback_vts_execution: False")
    print("v600_rt6_2d_control_c_authorized: True")
    print("[OK] FW-RT6-2d Control A primitives conform under Control C alignment")


if __name__ == "__main__":
    main()
