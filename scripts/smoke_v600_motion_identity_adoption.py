"""FW-RT6-1a Control C motion identity adoption gate.

Mock-safe: no provider, network, microphone, playback, VTS, or host-app
execution is performed. The accepted Control B semantic checks are reused
without its repository-state assertion.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "f740b374a35ed1a448beb6dc17a25427acb547fc"
EXPECTED_SURFACE = {
    "framework/motion.py",
    "framework/motion_session.py",
    "scripts/smoke_v600_motion_identity_adoption.py",
    "scripts/smoke_v520_motion_public_contract_conformance_gate.py",
    "scripts/smoke_v550_motion_session_real_adapter_composition.py",
    "docs/v600_public_identity_contract.md",
    "docs/public_facade.md",
    "docs/app_integration_contract.md",
}
FORBIDDEN_IMPORT_FRAGMENTS = (
    "openai", "elevenlabs", "pyvts", "websocket", "pyaudio",
    "sounddevice", "speech_recognition",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    import subprocess
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, check=True,
        capture_output=True, text=True,
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


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control C baseline")
    _assert(_changed_paths() == EXPECTED_SURFACE, f"unexpected Control C surface: {sorted(_changed_paths())}")
    print("[OK] Control C baseline and exact eight-file surface match")


def check_control_b_semantics() -> None:
    path = PROJECT_ROOT / "scripts" / "smoke_v600_realtime_identity_adoption.py"
    spec = importlib.util.spec_from_file_location("_v600_realtime_identity_adoption", path)
    _assert(spec is not None and spec.loader is not None, "unable to load Control B smoke")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    framework = module.check_import_safety()
    module.check_identity_adoption(framework)
    module.check_docs()
    print("[OK] accepted realtime identity semantics remain intact")


def check_motion_identity_adoption():
    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    hits = sorted(
        name for name in loaded
        if any(fragment in name.lower() for fragment in FORBIDDEN_IMPORT_FRAGMENTS)
    )
    _assert(not hits, f"motion identity adoption imported forbidden modules: {hits}")
    _assert(len(framework.__all__) == 99, "root-public count changed")

    info = framework.MotionSessionInfo()
    _assert(isinstance(info.session_id, framework.SessionId), "default MotionSessionInfo ID is not SessionId")

    legacy = framework.MotionResult.completed(session_id="motion-session")
    _assert(type(legacy.session_id) is str and legacy.session_id == "motion-session", "legacy motion session ID changed")

    sid_text = str(framework.SessionId.new())
    typed = framework.MotionResult.completed(session_id=sid_text)
    _assert(isinstance(typed.session_id, framework.SessionId), "serialized SessionId did not normalize")

    for factory in (
        lambda: framework.MotionResult.completed(session_id=str(framework.TurnId.new())),
        lambda: framework.MotionSessionInfo(session_id="fw_session_invalid"),
    ):
        try:
            factory()
        except ValueError:
            pass
        else:
            raise AssertionError("wrong-kind or malformed motion identity was accepted")

    events = []
    session = framework.create_motion_session()
    session.on_event(events.append)
    session_id = session.info.session_id
    _assert(isinstance(session_id, framework.SessionId), "MotionSession ID is not SessionId")
    session.emit_created()
    result = session.apply_motion(framework.MotionRequest.expression_change("smile"))
    _assert(result.session_id == session_id, "mock result identity drift")
    _assert(isinstance(result.session_id, framework.SessionId), "mock result ID type drift")
    guarded = framework.create_motion_session(
        adapter="vts", real_adapter_enabled=True, allow_provider_execution=False,
    )
    guard_result = guarded.apply_motion(framework.MotionRequest.expression_change("smile"))
    _assert(guard_result.session_id == guarded.info.session_id, "guard result identity drift")
    guarded.close()
    session.close()
    closed = session.apply_motion(framework.MotionRequest.expression_change("smile"))
    _assert(closed.session_id == session_id, "closed result identity drift")
    _assert(events, "motion callback events missing")
    _assert(all(type(event["session_id"]) is str for event in events), "callback ID is not plain string")
    _assert(all(event["session_id"] == str(session_id) for event in events), "callback identity drift")
    json.dumps([event["session_id"] for event in events])

    request = framework.MotionRequest.expression_change("smile")
    _assert(type(request.request_id) is str, "MotionRequest request_id type changed")
    _assert(not request.request_id.startswith("fw_generation_"), "MotionRequest request_id became GenerationId")
    _assert("turn_id" not in framework.MotionResult.__dataclass_fields__, "MotionResult turn_id wired prematurely")
    _assert("generation_id" not in framework.MotionResult.__dataclass_fields__, "MotionResult generation_id wired prematurely")
    print("[OK] Framework-generated motion identities are typed and stable")
    print("[OK] motion callbacks serialize one stable JSON-safe session identity")
    print("[OK] legacy IDs remain compatible and reserved wrong-kind IDs are rejected")


def check_docs() -> None:
    for relative in (
        "docs/v600_public_identity_contract.md",
        "docs/public_facade.md",
        "docs/app_integration_contract.md",
    ):
        text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        _assert("FW-RT6-1a-C-MOTION-IDENTITY-ADOPTION" in text, f"missing Control C marker: {relative}")
        _assert("MotionRequest request_id changed: False" in text, f"missing request identity policy: {relative}")
        _assert("MotionResult turn_id/generation_id fields added: False" in text, f"premature correlation claim: {relative}")
    print("[OK] motion identity adoption documentation records scope and deferrals")


def main() -> None:
    check_repository_contract()
    check_control_b_semantics()
    check_motion_identity_adoption()
    check_docs()
    print("v600_motion_identity_adoption_status: implemented-awaiting-review")
    print("v600_exact_change_surface_count: 8")
    print("v600_root_public_name_count: 99")
    print("v600_framework_generated_motion_session_id_typed: True")
    print("v600_motion_result_session_id_typed: True")
    print("v600_motion_callback_session_id_json_string: True")
    print("v600_legacy_motion_session_ids_preserved: True")
    print("v600_wrong_kind_identity_rejected: True")
    print("v600_motion_request_id_changed: False")
    print("v600_generation_id_promoted_from_request_id: False")
    print("v600_turn_generation_result_fields_added: False")
    print("v600_provider_identifier_exposed: False")
    print("v600_provider_execution: False")
    print("v600_network_execution: False")
    print("v600_next_control: FW-RT6-1a Control D")
    print("v600_next_control_authorized: False")
    print("[OK] FW-RT6-1a Control C motion identity adoption smoke passed")


if __name__ == "__main__":
    main()
