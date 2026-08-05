"""FW-RT6-0a current-source gap inventory smoke.

This smoke is source-tree-only and provider-safe. It records the current v5.5.0
public/runtime gaps required for the v6.0.0 planning baseline. It must not open a
network connection, execute a provider, use a microphone, play audio, inspect
private configuration/evidence, modify another repository, commit, or push.
"""

from __future__ import annotations

import ast
import socket
import sys
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BASELINE_HEAD = "f56697b6de066b062794ac7bb01330d2d9e91759"

REQUIRED_FILES = (
    "README.md",
    "docs/roadmap_feature_v6.0.0.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/smoke_v600_current_source_gap_inventory.py",
    "scripts/check_v600_tasklist_contract.py",
)

DOC_MARKERS = (
    "FW-RT6-0a",
    "Unified Realtime Character Runtime",
    BASELINE_HEAD,
    "G-01",
    "G-17",
    "exact six-file docs/test-only checkpoint",
    "runtime Python changed: False",
    "FW-RT6-0b",
    "NOT_AUTHORIZED",
    "DRC repository accessed or changed: False",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing required file: {relative}")
    return path.read_text(encoding="utf-8", errors="replace")


def _class_method_counts(relative: str, class_name: str) -> dict[str, int]:
    tree = ast.parse(_read(relative), filename=relative)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            counts: dict[str, int] = {}
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    counts[item.name] = counts.get(item.name, 0) + 1
            return counts
    raise AssertionError(f"class not found: {class_name} in {relative}")


def _realtime_event_fields() -> set[str]:
    tree = ast.parse(_read("framework/realtime.py"), filename="framework/realtime.py")
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "RealtimeEvent":
            return {
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
            }
    raise AssertionError("RealtimeEvent class not found")


def _assert_documents() -> None:
    for relative in REQUIRED_FILES:
        _require((ROOT / relative).is_file(), f"required FW-RT6-0a file missing: {relative}")

    combined = "\n".join(_read(relative) for relative in REQUIRED_FILES[:4])
    for marker in DOC_MARKERS:
        _require(marker in combined, f"planning docs missing marker: {marker}")

    for forbidden in (
        "FW-RT6-0b implementation: AUTHORIZED",
        "runtime Python changed: True",
        "provider execution: True",
        "DRC repository accessed or changed: True",
    ):
        _require(forbidden not in combined, f"forbidden authorization/status found: {forbidden}")

    print("[OK] FW-RT6-0a planning documents and scope markers are present")


def _assert_current_source_gaps() -> None:
    realtime_session = _read("framework/realtime_session.py")
    _require("Mock-safe public realtime session skeleton" in realtime_session, "RealtimeSession skeleton marker changed")
    _require("does not execute real STT, LLM, TTS, or" in realtime_session, "mock-only run_turn marker changed")
    _require("InterruptResult.not_implemented" in realtime_session, "interrupt not-implemented marker missing")
    _require("OutputFlushResult.not_implemented" in realtime_session, "output-flush not-implemented marker missing")

    event_fields = _realtime_event_fields()
    for missing in ("sequence", "generation", "payload", "terminal"):
        _require(missing not in event_fields, f"FW-RT6-0a baseline unexpectedly contains RealtimeEvent.{missing}")

    capabilities = _read("framework/capabilities.py")
    _require('schema_version="v5.1.capabilities"' in capabilities, "capability schema baseline changed")
    for marker in (
        '_missing_capability("voice_input"',
        '_missing_capability("realtime"',
        '_missing_capability("motion"',
    ):
        _require(marker in capabilities, f"stale global capability marker missing: {marker}")

    voice_input = _read("framework/voice_input_session.py")
    _require("Real STT is intentionally not executed in this skeleton" in voice_input, "VoiceInputSession skeleton marker changed")
    _require((ROOT / "framework/openai_voice_input_real_provider.py").is_file(), "real OpenAI STT executor source missing")

    output_control = _read("framework/output_control.py")
    _require("provider_cancel_supported: bool = False" in output_control, "interrupt summary capability marker changed")
    _require("queue_flush_supported: bool = False" in output_control, "queue summary capability marker changed")

    voice_output_methods = _class_method_counts("framework/audio/voice_output.py", "VoiceOutputSession")
    for name in ("close", "is_closed", "create_output", "speak"):
        _require(voice_output_methods.get(name, 0) > 1, f"expected repeated VoiceOutputSession.{name} baseline definition")

    provider_adapter = _read("framework/audio/_provider_adapter.py")
    _require("audio_artifact_ref=str(artifact_path)" in provider_adapter, "voice artifact path mismatch marker changed")

    llm_base = _read("llm/base.py")
    _require("def ask_stream" in llm_base, "BaseLLM.ask_stream missing")
    _require("cancel" not in llm_base.lower(), "FW-RT6-0a baseline unexpectedly contains BaseLLM cancel protocol")

    pipeline = _read("core/pipeline.py")
    _require("llm.ask_stream" in pipeline, "legacy pipeline streaming marker missing")
    _require("is_interruption_requested" in pipeline, "legacy pipeline interrupt marker missing")
    _require("from tts.voice_engine import VoiceEngine" in pipeline, "legacy VoiceEngine ownership marker missing")

    _require(not (ROOT / "pyproject.toml").exists(), "FW-RT6-0a baseline unexpectedly contains pyproject.toml")
    _require(not any((ROOT / "tests").rglob("*.py")), "FW-RT6-0a baseline unexpectedly contains normal Python tests")

    print("[OK] current v5.5.0 source gaps remain truthfully recorded")


def _assert_public_facade_drift() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    smoke_source = _read("scripts/smoke_public_facade.py")
    tree = ast.parse(smoke_source, filename="scripts/smoke_public_facade.py")
    expected: list[str] | None = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "EXPECTED_PUBLIC_API" for target in node.targets)
        ):
            expected = ast.literal_eval(node.value)
            break
    _require(expected is not None, "legacy EXPECTED_PUBLIC_API list not found")

    def _blocked_connect(*args, **kwargs):
        raise AssertionError("network execution is forbidden in FW-RT6-0a")

    with patch.object(socket, "create_connection", side_effect=_blocked_connect), patch.object(socket.socket, "connect", side_effect=_blocked_connect):
        import framework

    _require(list(framework.__all__) != expected, "legacy smoke_public_facade drift is no longer present")
    _require("RealtimeSession" in framework.__all__, "current root-public realtime export missing")
    _require("MotionSession" in framework.__all__, "current root-public motion export missing")
    print("[OK] legacy public-facade expected list drift is recorded without provider execution")


def main() -> None:
    _assert_documents()
    _assert_current_source_gaps()
    _assert_public_facade_drift()

    print("v600_source_inventory_status: implemented-awaiting-review")
    print("v600_baseline_head: " + BASELINE_HEAD)
    print("v600_exact_change_surface_count: 6")
    print("v600_realtime_session_is_mock_skeleton: True")
    print("v600_unified_real_turn_orchestration_exists: False")
    print("v600_event_sequence_exists: False")
    print("v600_event_generation_exists: False")
    print("v600_exactly_once_terminal_registry_exists: False")
    print("v600_stale_result_gate_exists: False")
    print("v600_detailed_truthful_capability_snapshot_exists: False")
    print("v600_real_interrupt_composition_exists: False")
    print("v600_real_tts_work_control_exists: False")
    print("v600_installable_sdk_metadata_exists: False")
    print("v600_normal_unit_test_layer_exists: False")
    print("v600_network_execution: False")
    print("v600_provider_execution: False")
    print("v600_microphone_used: False")
    print("v600_audio_playback: False")
    print("v600_drc_repository_accessed: False")
    print("v600_next_checkpoint: FW-RT6-0b")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-0a current-source gap inventory smoke passed")


if __name__ == "__main__":
    main()
