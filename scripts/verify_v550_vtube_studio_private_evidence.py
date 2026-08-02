"""Validate private FW-VTS bootstrap and real-motion evidence safely.

FW-VTS-0f1c accepts four required VTube Studio intents and an optional
stop_motion intent. The accepted bootstrap evidence may come from the earlier
accepted bootstrap commit when that commit is an ancestor of the corrective
acceptance commit and the bootstrap operator source is unchanged.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Mapping


BOOTSTRAP_SCHEMA = (
    "ai-character-framework-v550-vts-bootstrap-evidence-v1"
)
ACCEPTANCE_SCHEMA = (
    "ai-character-framework-v550-vts-operator-evidence-v1"
)
EXPECTED_PYVTS_VERSION = "0.3.3"
REQUIRED_INTENTS = frozenset(
    {"expression", "emotion", "gesture", "reset_expression"}
)
OPTIONAL_INTENT = "stop_motion"
BOOTSTRAP_OPERATOR_PATH = (
    "scripts/operator_v550_vtube_studio_token_bootstrap.py"
)
BOOTSTRAP_ALLOWED_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "created_at_utc",
        "repo_head",
        "pyvts_version",
        "repo_clean_before",
        "repo_clean_after",
        "endpoint_loopback_only",
        "actual_pyvts_imported",
        "provider_client_created",
        "actual_websocket_connected",
        "token_request_executed",
        "new_token_authenticated",
        "provider_close_completed",
        "private_token_written",
        "private_token_outside_repo",
        "private_evidence_outside_repo",
        "token_material_exposed",
        "token_path_exposed",
        "endpoint_value_exposed",
        "provider_payload_exposed",
        "raw_exception_exposed",
        "drc_repo_changed",
    }
)
ACCEPTANCE_ALLOWED_KEYS = frozenset(
    {
        "schema",
        "run_id",
        "created_at_utc",
        "repo_head",
        "pyvts_version",
        "repo_clean_before",
        "repo_clean_after",
        "private_config_outside_repo",
        "private_token_outside_repo",
        "private_evidence_outside_repo",
        "endpoint_loopback_only",
        "actual_pyvts_imported",
        "actual_websocket_connected",
        "actual_vts_authenticated",
        "actual_model_loaded",
        "actual_hotkey_inventory_loaded",
        "intent_results",
        "required_four_intents_verified",
        "stop_motion_supported",
        "stop_motion_verified",
        "optional_stop_motion_contract",
        "real_hotkey_execution_verified",
        "real_motion_execution_verified",
        "operator_visual_confirmation_complete",
        "session_close_verified",
        "bridge_thread_terminated",
        "automatic_retry_executed",
        "automatic_reconnect_executed",
        "polling_loop_created",
        "token_material_exposed",
        "token_path_exposed",
        "hotkey_name_exposed",
        "hotkey_identifier_exposed",
        "model_identity_exposed",
        "provider_payload_exposed",
        "raw_exception_exposed",
        "drc_repo_changed",
    }
)
INTENT_ALLOWED_KEYS = frozenset(
    {
        "outcome",
        "provider_protocol_call_executed",
        "hotkey_resolved",
        "provider_request_completed",
        "operator_visual_confirmation",
        "real_hotkey_execution_verified",
        "real_motion_verified",
    }
)


def _git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _status_paths(root: Path) -> set[str]:
    output = _git(root, "status", "--porcelain=v1", "-z")
    paths: set[str] = set()
    for record in output.split("\0"):
        if not record:
            continue
        value = record[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.add(value.replace("\\", "/"))
    return paths


def _is_hex(value: Any, length: int) -> bool:
    if not isinstance(value, str) or len(value) != length:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


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


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _load(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _require(
        isinstance(payload, Mapping),
        "Evidence must be a JSON object.",
    )
    return payload


def _validate_exact_keys(
    payload: Mapping[str, Any],
    allowed: frozenset[str],
    *,
    label: str,
) -> None:
    unexpected = sorted(set(payload) - allowed)
    _require(
        not unexpected,
        f"{label} evidence contains unexpected keys: {unexpected}",
    )


def _validate_bootstrap(payload: Mapping[str, Any]) -> None:
    _validate_exact_keys(
        payload,
        BOOTSTRAP_ALLOWED_KEYS,
        label="Bootstrap",
    )
    _require(
        payload.get("schema") == BOOTSTRAP_SCHEMA,
        "Bootstrap schema mismatch.",
    )
    _require(
        _is_hex(payload.get("run_id"), 32),
        "Bootstrap run ID is invalid.",
    )
    _require(
        isinstance(payload.get("created_at_utc"), str)
        and bool(payload["created_at_utc"]),
        "Bootstrap timestamp is invalid.",
    )
    _require(
        payload.get("pyvts_version") == EXPECTED_PYVTS_VERSION,
        "pyvts version mismatch.",
    )
    for key in (
        "repo_clean_before",
        "repo_clean_after",
        "endpoint_loopback_only",
        "actual_pyvts_imported",
        "provider_client_created",
        "actual_websocket_connected",
        "token_request_executed",
        "new_token_authenticated",
        "provider_close_completed",
        "private_token_written",
        "private_token_outside_repo",
        "private_evidence_outside_repo",
    ):
        _require(
            payload.get(key) is True,
            f"Bootstrap marker not accepted: {key}",
        )
    for key in (
        "token_material_exposed",
        "token_path_exposed",
        "endpoint_value_exposed",
        "provider_payload_exposed",
        "raw_exception_exposed",
        "drc_repo_changed",
    ):
        _require(
            payload.get(key) is False,
            f"Bootstrap privacy marker mismatch: {key}",
        )


def _validate_intent(intent: str, value: Any) -> None:
    _require(
        isinstance(value, Mapping),
        f"Intent evidence must be an object: {intent}",
    )
    _validate_exact_keys(
        value,
        INTENT_ALLOWED_KEYS,
        label=f"Intent {intent}",
    )
    _require(
        value.get("outcome") == "completed",
        f"Intent did not complete: {intent}",
    )
    for key in (
        "provider_protocol_call_executed",
        "hotkey_resolved",
        "provider_request_completed",
        "real_hotkey_execution_verified",
        "real_motion_verified",
        "operator_visual_confirmation",
    ):
        _require(
            value.get(key) is True,
            f"Intent marker missing: {intent}/{key}",
        )


def _validate_acceptance(payload: Mapping[str, Any]) -> None:
    _validate_exact_keys(
        payload,
        ACCEPTANCE_ALLOWED_KEYS,
        label="Acceptance",
    )
    _require(
        payload.get("schema") == ACCEPTANCE_SCHEMA,
        "Acceptance schema mismatch.",
    )
    _require(
        _is_hex(payload.get("run_id"), 32),
        "Acceptance run ID is invalid.",
    )
    _require(
        isinstance(payload.get("created_at_utc"), str)
        and bool(payload["created_at_utc"]),
        "Acceptance timestamp is invalid.",
    )
    _require(
        payload.get("pyvts_version") == EXPECTED_PYVTS_VERSION,
        "pyvts version mismatch.",
    )
    for key in (
        "repo_clean_before",
        "repo_clean_after",
        "private_config_outside_repo",
        "private_token_outside_repo",
        "private_evidence_outside_repo",
        "endpoint_loopback_only",
        "actual_pyvts_imported",
        "actual_websocket_connected",
        "actual_vts_authenticated",
        "actual_model_loaded",
        "actual_hotkey_inventory_loaded",
        "required_four_intents_verified",
        "optional_stop_motion_contract",
        "real_hotkey_execution_verified",
        "real_motion_execution_verified",
        "operator_visual_confirmation_complete",
        "session_close_verified",
        "bridge_thread_terminated",
    ):
        _require(
            payload.get(key) is True,
            f"Acceptance marker not accepted: {key}",
        )
    for key in (
        "automatic_retry_executed",
        "automatic_reconnect_executed",
        "polling_loop_created",
        "token_material_exposed",
        "token_path_exposed",
        "hotkey_name_exposed",
        "hotkey_identifier_exposed",
        "model_identity_exposed",
        "provider_payload_exposed",
        "raw_exception_exposed",
        "drc_repo_changed",
    ):
        _require(
            payload.get(key) is False,
            f"Acceptance privacy marker mismatch: {key}",
        )

    stop_supported = payload.get("stop_motion_supported")
    stop_verified = payload.get("stop_motion_verified")
    _require(
        isinstance(stop_supported, bool),
        "stop_motion_supported must be boolean.",
    )
    _require(
        isinstance(stop_verified, bool),
        "stop_motion_verified must be boolean.",
    )
    _require(
        stop_verified is stop_supported,
        "stop_motion_verified must match supported optional execution.",
    )

    results = payload.get("intent_results")
    _require(
        isinstance(results, Mapping),
        "Intent results must be an object.",
    )
    expected_intents = set(REQUIRED_INTENTS)
    if stop_supported:
        expected_intents.add(OPTIONAL_INTENT)
    _require(
        set(results) == expected_intents,
        "Evidence must contain the four required intents and stop_motion "
        "only when supported.",
    )
    for intent, value in results.items():
        _validate_intent(intent, value)


def _is_ancestor(
    root: Path,
    ancestor: str,
    descendant: str,
) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def _bootstrap_source_unchanged(
    root: Path,
    bootstrap_head: str,
    acceptance_head: str,
) -> bool:
    completed = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
            bootstrap_head,
            acceptance_head,
            "--",
            BOOTSTRAP_OPERATOR_PATH,
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bootstrap-evidence-json",
        required=True,
    )
    parser.add_argument(
        "--acceptance-evidence-json",
        required=True,
    )
    parser.add_argument(
        "--expected-bootstrap-head",
        required=True,
    )
    parser.add_argument(
        "--expected-acceptance-head",
        required=True,
    )
    args = parser.parse_args()

    root = _repo_root()
    _require(
        _is_hex(args.expected_bootstrap_head, 40),
        "Expected bootstrap head must be a 40-character SHA.",
    )
    _require(
        _is_hex(args.expected_acceptance_head, 40),
        "Expected acceptance head must be a 40-character SHA.",
    )
    _require(
        _git(root, "rev-parse", "HEAD")
        == args.expected_acceptance_head,
        "Current repository head does not match expected acceptance head.",
    )
    _require(
        not (_status_paths(root) - {".vscode/settings.json"}),
        "Evidence validation requires a clean repository.",
    )

    bootstrap_path = (
        Path(args.bootstrap_evidence_json)
        .expanduser()
        .resolve(strict=True)
    )
    acceptance_path = (
        Path(args.acceptance_evidence_json)
        .expanduser()
        .resolve(strict=True)
    )
    for path in (bootstrap_path, acceptance_path):
        _require(
            path.is_file(),
            "Private evidence path must be a regular file.",
        )
        _require(
            not _is_inside(path, root),
            "Private evidence must remain outside the repository.",
        )

    bootstrap = _load(bootstrap_path)
    acceptance = _load(acceptance_path)
    _validate_bootstrap(bootstrap)
    _validate_acceptance(acceptance)

    bootstrap_head = bootstrap.get("repo_head")
    acceptance_head = acceptance.get("repo_head")
    _require(
        _is_hex(bootstrap_head, 40),
        "Bootstrap repository head is invalid.",
    )
    _require(
        _is_hex(acceptance_head, 40),
        "Acceptance repository head is invalid.",
    )
    _require(
        bootstrap_head == args.expected_bootstrap_head,
        "Bootstrap evidence does not match expected bootstrap head.",
    )
    _require(
        acceptance_head == args.expected_acceptance_head,
        "Acceptance evidence does not match expected acceptance head.",
    )
    _require(
        _is_ancestor(root, bootstrap_head, acceptance_head),
        "Accepted bootstrap head is not an ancestor of acceptance head.",
    )
    _require(
        _bootstrap_source_unchanged(
            root,
            bootstrap_head,
            acceptance_head,
        ),
        "Token bootstrap operator changed after accepted bootstrap.",
    )
    _require(
        bootstrap.get("pyvts_version")
        == acceptance.get("pyvts_version"),
        "Bootstrap and acceptance pyvts versions do not match.",
    )

    stop_supported = bool(
        acceptance.get("stop_motion_supported")
    )
    stop_verified = bool(
        acceptance.get("stop_motion_verified")
    )

    print(
        "v550_vts_private_evidence_status: accepted-by-validator"
    )
    print("v550_actual_pyvts_imported: True")
    print("v550_actual_websocket_connected: True")
    print("v550_actual_vts_authenticated: True")
    print("v550_actual_model_loaded: True")
    print("v550_actual_hotkey_inventory_loaded: True")
    print("v550_expression_verified: True")
    print("v550_emotion_verified: True")
    print("v550_gesture_verified: True")
    print("v550_reset_expression_verified: True")
    print("v550_required_four_intents_verified: True")
    print(
        f"v550_stop_motion_supported: {stop_supported}"
    )
    print(
        f"v550_stop_motion_verified: {stop_verified}"
    )
    print("v550_optional_stop_motion_contract: True")
    print("v550_real_hotkey_execution_verified: True")
    print("v550_real_motion_execution_verified: True")
    print("v550_operator_visual_confirmation_complete: True")
    print("v550_session_close_verified: True")
    print("v550_bridge_thread_terminated: True")
    print("v550_token_material_exposed: False")
    print("v550_token_path_exposed: False")
    print("v550_hotkey_name_exposed: False")
    print("v550_hotkey_identifier_exposed: False")
    print("v550_model_identity_exposed: False")
    print("v550_provider_payload_exposed: False")
    print("v550_raw_exception_exposed: False")
    print("v550_private_evidence_outside_repo: True")
    print("v550_repo_clean_before_operator_run: True")
    print("v550_repo_clean_after_operator_run: True")
    print("v550_bootstrap_head_reused: True")
    print("v550_bootstrap_source_unchanged: True")
    print("v550_drc_repo_changed: False")
    print("v550_vts_acceptance_sync_authorization: ready")
    print(
        "[OK] FW-VTS-0f private VTube Studio evidence passed"
    )


if __name__ == "__main__":
    main()
