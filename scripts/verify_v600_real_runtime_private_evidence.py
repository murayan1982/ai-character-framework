"""Validate private FW-RT6-13c evidence without exposing its contents."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


EVIDENCE_SCHEMA = "ai-character-framework-v600-rt6-13c-private-evidence-v1"
EXPECTED_DEPENDENCIES = {
    "openai": "2.31.0",
    "elevenlabs": "2.41.0",
    "pyvts": "0.3.3",
}
_RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_HEAD_PATTERN = re.compile(r"^[0-9a-f]{40}$")

TRUE_FIELDS = frozenset(
    {
        "repo_clean_before",
        "repo_clean_after",
        "private_config_outside_repo",
        "private_audio_outside_repo",
        "private_artifacts_outside_repo",
        "private_evidence_outside_repo",
        "configured_real_voice_input",
        "configured_real_llm_streaming",
        "cooperative_interrupt",
        "future_llm_delivery_suppressed",
        "real_tts_generation",
        "pending_clear",
        "late_artifact_rejection",
        "host_playback_owned",
        "host_playback_stop_requested",
        "host_playback_stop_acknowledged",
        "configured_real_motion",
        "operator_visual_confirmation",
        "interrupt_recovery_next_turn",
        "close_cleanup",
        "actual_openai_sdk_imported",
        "actual_openai_client_created",
        "actual_openai_network_execution",
        "actual_elevenlabs_sdk_imported",
        "actual_elevenlabs_client_created",
        "actual_elevenlabs_provider_execution",
        "actual_pyvts_imported",
        "actual_vts_websocket_connected",
        "actual_vts_authenticated",
        "actual_vts_protocol_execution",
    }
)
FALSE_FIELDS = frozenset(
    {
        "provider_hard_cancel_claimed",
        "framework_physical_playback_stop_claimed",
        "credential_value_exposed",
        "private_path_exposed",
        "raw_audio_exposed",
        "raw_provider_payload_exposed",
        "raw_exception_exposed",
        "transcript_text_exposed",
        "llm_text_exposed",
        "private_model_exposed",
        "private_hotkey_exposed",
        "private_selector_exposed",
        "microphone_accessed",
        "framework_realtime_session_real_orchestration_used",
        "drc_repo_changed",
    }
)
POSITIVE_COUNT_FIELDS = frozenset(
    {
        "stt_transcript_char_count",
        "llm_delta_count",
        "recovery_delta_count",
        "tts_artifact_count",
        "pending_cleared_count",
        "late_artifact_invalidated_count",
        "motion_intent_count",
    }
)
BASE_FIELDS = frozenset(
    {
        "schema",
        "run_id",
        "created_at_utc",
        "framework_head",
        "dependency_versions",
    }
)
EXPECTED_FIELDS = BASE_FIELDS | TRUE_FIELDS | FALSE_FIELDS | POSITIVE_COUNT_FIELDS


def _repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()).resolve()


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def validate_payload(payload: object) -> Mapping[str, Any]:
    """Validate only the exact public-safe evidence shape."""

    _require(isinstance(payload, Mapping), "Evidence must be a JSON object.")
    _require(
        set(payload) == EXPECTED_FIELDS,
        "Evidence contains missing or unexpected fields.",
    )
    _require(payload.get("schema") == EVIDENCE_SCHEMA, "Evidence schema mismatch.")
    run_id = payload.get("run_id")
    _require(
        isinstance(run_id, str) and bool(_RUN_ID_PATTERN.fullmatch(run_id)),
        "Evidence run identifier is invalid.",
    )
    framework_head = payload.get("framework_head")
    _require(
        isinstance(framework_head, str)
        and bool(_HEAD_PATTERN.fullmatch(framework_head)),
        "Evidence Framework head is invalid.",
    )
    created = payload.get("created_at_utc")
    _require(isinstance(created, str), "Evidence timestamp is invalid.")
    try:
        parsed = datetime.fromisoformat(created)
    except ValueError as error:
        raise AssertionError("Evidence timestamp is invalid.") from error
    _require(parsed.tzinfo is not None, "Evidence timestamp must include a timezone.")

    dependencies = payload.get("dependency_versions")
    _require(
        isinstance(dependencies, Mapping)
        and dict(dependencies) == EXPECTED_DEPENDENCIES,
        "Evidence dependency versions do not match the accepted set.",
    )
    for field in TRUE_FIELDS:
        _require(payload.get(field) is True, f"Required true marker missing: {field}")
    for field in FALSE_FIELDS:
        _require(payload.get(field) is False, f"Required false marker missing: {field}")
    for field in POSITIVE_COUNT_FIELDS:
        value = payload.get(field)
        _require(
            isinstance(value, int) and not isinstance(value, bool) and value > 0,
            f"Required positive count missing: {field}",
        )
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate FW-RT6-13c private evidence using only fixed public-safe "
            "markers. Evidence contents and paths are never printed."
        )
    )
    parser.add_argument("--evidence-json", required=True)
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        root = _repo_root()
        raw_path = Path(args.evidence_json).expanduser()
        if not raw_path.is_absolute():
            raise AssertionError("Private evidence path must be absolute.")
        evidence_path = raw_path.resolve(strict=True)
        _require(
            not _is_inside(evidence_path, root),
            "Private evidence must remain outside the repository.",
        )
        _require(
            evidence_path.is_file() and 0 < evidence_path.stat().st_size <= 64 * 1024,
            "Private evidence is unavailable or too large.",
        )
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
        validate_payload(payload)
    except Exception:
        print("v600_13c_private_evidence_status: rejected")
        print("v600_13c_private_evidence_safe_message: evidence validation failed")
        return 1

    print("v600_13c_private_evidence_status: accepted-by-validator")
    print("v600_13c_acceptance_scenarios: 9 / 9 VERIFIED")
    print("v600_13c_real_voice_input: True")
    print("v600_13c_real_llm_streaming: True")
    print("v600_13c_cooperative_interrupt: True")
    print("v600_13c_real_tts_generation: True")
    print("v600_13c_pending_clear_late_rejection: True")
    print("v600_13c_host_playback_stop_boundary: True")
    print("v600_13c_real_motion: True")
    print("v600_13c_interrupt_recovery_next_turn: True")
    print("v600_13c_close_cleanup: True")
    print("v600_13c_provider_hard_cancel_claimed: False")
    print("v600_13c_framework_physical_playback_stop_claimed: False")
    print("v600_13c_private_values_or_paths_exposed: False")
    print("v600_13c_raw_audio_payload_exception_exposed: False")
    print("v600_13c_private_model_hotkey_selector_exposed: False")
    print("v600_13c_framework_realtime_session_real_orchestration_used: False")
    print("v600_13c_acceptance_sync_authorization: ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
