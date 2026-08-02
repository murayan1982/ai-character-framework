"""Operator-only real VTube Studio acceptance through the root-public API.

Private configuration, authentication material, and evidence remain outside the
repository. Console output contains only bounded public markers and intent
category names. It never prints private paths, token material, hotkey names,
selector values, model identity, provider payloads, or raw exception text.

FW-VTS-0f1c requires expression, emotion, gesture, and reset_expression.
stop_motion is optional and is executed only when an actually supported private
binding is supplied.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from framework import (  # noqa: E402
    MotionIntent,
    MotionOutcome,
    MotionRequest,
    create_motion_session,
)


EXPECTED_PYVTS_VERSION = "0.3.3"
CONFIG_SCHEMA = "ai-character-framework-v550-vts-private-config-v1"
EVIDENCE_SCHEMA = "ai-character-framework-v550-vts-operator-evidence-v1"
REAL_CONFIRMATION = "I_ACCEPT_LOCAL_VTUBE_STUDIO_REAL_MOTION_EXECUTION"
PRIVATE_CONFIRMATION = (
    "I_WILL_KEEP_VTS_TOKEN_CONFIG_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY"
)
REQUIRED_INTENTS = (
    "expression",
    "emotion",
    "gesture",
    "reset_expression",
)
OPTIONAL_INTENT = "stop_motion"
OBSERVATION_PHRASES = {
    "expression": "I_OBSERVED_EXPRESSION_EFFECT",
    "emotion": "I_OBSERVED_EMOTION_EFFECT",
    "gesture": "I_OBSERVED_GESTURE_EFFECT",
    "reset_expression": "I_OBSERVED_RESET_EFFECT",
    "stop_motion": "I_OBSERVED_STOP_EFFECT",
}
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _repo_root() -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(completed.stdout.strip()).resolve()


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


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _absolute_outside_repo(raw: str, *, root: Path, label: str) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{label} must be an absolute path.")
    resolved = candidate.resolve(strict=True)
    if _is_inside(resolved, root):
        raise ValueError(f"{label} must remain outside the repository.")
    return resolved


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _load_private_config(path: Path, *, root: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping) or payload.get("schema") != CONFIG_SCHEMA:
        raise ValueError("Private configuration schema mismatch.")
    if set(payload) != {
        "schema",
        "endpoint",
        "authentication_token_file",
        "hotkey_bindings",
    }:
        raise ValueError("Private configuration contains unexpected fields.")

    endpoint = payload.get("endpoint")
    bindings = payload.get("hotkey_bindings")
    if not isinstance(endpoint, Mapping) or not isinstance(bindings, Mapping):
        raise ValueError("Private configuration shape is invalid.")
    if set(endpoint) != {"host", "port"}:
        raise ValueError(
            "Private endpoint configuration contains unexpected fields."
        )
    host = str(endpoint.get("host", "")).strip().casefold()
    if host not in _LOOPBACK_HOSTS:
        raise ValueError(
            "Only an explicit loopback VTube Studio host is allowed."
        )
    try:
        port = int(endpoint.get("port"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Private endpoint port is invalid.") from exc
    if not 1 <= port <= 65535:
        raise ValueError("Private endpoint port is invalid.")

    token_path = _absolute_outside_repo(
        str(payload.get("authentication_token_file", "")),
        root=root,
        label="Authentication token file",
    )
    if not token_path.is_file() or token_path.stat().st_size <= 0:
        raise ValueError("Private authentication token file is unavailable.")

    normalized: dict[str, str] = {}
    for raw_key, raw_value in bindings.items():
        key = str(raw_key).strip().casefold()
        value = str(raw_value).strip()
        if not key or not value:
            raise ValueError(
                "Private hotkey selectors and names must be non-empty."
            )
        if key in normalized:
            raise ValueError(
                "Private hotkey bindings contain duplicate normalized selectors."
            )
        if len(key) > 128 or len(value) > 128:
            raise ValueError(
                "Private hotkey selectors and names must be at most "
                "128 characters."
            )
        normalized[key] = value

    if len(normalized) not in {4, 5}:
        raise ValueError(
            "Exactly four required private hotkey bindings plus an optional "
            "stop_motion binding are accepted."
        )

    groups: dict[str, list[str]] = {
        "expression": [],
        "emotion": [],
        "gesture": [],
        "reset_expression": [],
        "stop_motion": [],
    }
    for selector in normalized:
        if selector in {"reset_expression", "stop_motion"}:
            groups[selector].append(selector)
            continue
        prefix, separator, selected = selector.partition(":")
        if (
            not separator
            or prefix not in {"expression", "emotion", "gesture"}
            or not selected.strip()
        ):
            raise ValueError(
                "Private hotkey selectors must be expression:<value>, "
                "emotion:<value>, gesture:<value>, reset_expression, "
                "and optionally stop_motion."
            )
        groups[prefix].append(selector)

    for intent_name in REQUIRED_INTENTS:
        if len(groups[intent_name]) != 1:
            raise ValueError(
                "Private hotkey bindings must contain exactly one selector "
                f"for required intent: {intent_name}."
            )
    if len(groups[OPTIONAL_INTENT]) > 1:
        raise ValueError(
            "Private hotkey bindings may contain at most one stop_motion "
            "selector."
        )

    stop_motion_supported = bool(groups[OPTIONAL_INTENT])
    execution_intents = REQUIRED_INTENTS + (
        (OPTIONAL_INTENT,) if stop_motion_supported else ()
    )

    return {
        "host": host,
        "port": port,
        "token_path": token_path,
        "bindings": normalized,
        "selector_by_intent": {
            intent_name: groups[intent_name][0]
            for intent_name in execution_intents
        },
        "execution_intents": execution_intents,
        "stop_motion_supported": stop_motion_supported,
    }


def _request_for(intent_name: str, selector: str) -> MotionRequest:
    if intent_name == "expression":
        return MotionRequest.expression_change(selector.split(":", 1)[1])
    if intent_name == "emotion":
        return MotionRequest.emotion_update(selector.split(":", 1)[1])
    if intent_name == "gesture":
        return MotionRequest(
            intent=MotionIntent.GESTURE,
            gesture=selector.split(":", 1)[1],
        )
    if intent_name == "reset_expression":
        return MotionRequest(intent=MotionIntent.RESET_EXPRESSION)
    if intent_name == "stop_motion":
        return MotionRequest.stop_motion()
    raise ValueError("Unsupported operator intent category.")


def _observe(intent_name: str) -> bool:
    phrase = OBSERVATION_PHRASES[intent_name]
    print(f"v550_vts_operator_observation_required: {intent_name}")
    response = input(f"Type {phrase}: ").strip()
    return response == phrase


def _bridge_threads_alive() -> bool:
    return any(
        thread.is_alive() and thread.name == "framework-vts-motion-bridge"
        for thread in threading.enumerate()
    )


def _capability_matches_private(
    capability: Any,
    private: Mapping[str, Any],
    values: Mapping[str, Any],
) -> bool:
    required_ready = all(
        (
            capability.adapter_status.value == "configured",
            capability.supports_real_adapter,
            capability.supports_expression,
            capability.supports_emotion,
            capability.supports_gesture,
            capability.supports_reset_expression,
            values.get("private_config_outside_repo") is True,
            values.get("private_token_outside_repo") is True,
            values.get("private_evidence_outside_repo") is True,
            values.get("actual_pyvts_imported") is True,
            values.get("actual_websocket_connected") is True,
            values.get("actual_vts_authenticated") is True,
            values.get("actual_model_loaded") is True,
            values.get("actual_hotkey_inventory_loaded") is True,
        )
    )
    stop_matches = (
        bool(capability.supports_stop_motion)
        is bool(private["stop_motion_supported"])
    )
    return bool(required_ready and stop_matches)


def _run_intents(
    session: Any,
    private: Mapping[str, Any],
    *,
    observer: Callable[[str], bool] = _observe,
) -> tuple[dict[str, dict[str, Any]], dict[str, bool]]:
    results: dict[str, dict[str, Any]] = {}
    verified = {
        "expression": False,
        "emotion": False,
        "gesture": False,
        "reset_expression": False,
        "stop_motion": False,
    }
    for intent_name in private["execution_intents"]:
        request = _request_for(
            intent_name,
            private["selector_by_intent"][intent_name],
        )
        result = session.apply_motion(request)
        result_metadata = dict(result.public_metadata)
        protocol_executed = (
            result_metadata.get("provider_protocol_call_executed") is True
        )
        hotkey_resolved = result_metadata.get("hotkey_resolved") is True
        completed = result.outcome is MotionOutcome.COMPLETED
        if not all((completed, protocol_executed, hotkey_resolved)):
            raise RuntimeError(f"{intent_name}_execution_not_verified")
        observed = observer(intent_name)
        if not observed:
            raise RuntimeError(
                f"{intent_name}_visual_confirmation_missing"
            )
        verified[intent_name] = True
        results[intent_name] = {
            "outcome": result.outcome.value,
            "provider_protocol_call_executed": protocol_executed,
            "hotkey_resolved": hotkey_resolved,
            "provider_request_completed": completed,
            "operator_visual_confirmation": observed,
            "real_hotkey_execution_verified": bool(
                completed
                and protocol_executed
                and hotkey_resolved
                and observed
            ),
            "real_motion_verified": bool(
                completed
                and protocol_executed
                and hotkey_resolved
                and observed
            ),
        }
    return results, verified


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run configured local VTube Studio acceptance through the "
            "root-public MotionSession API."
        )
    )
    parser.add_argument("--private-config", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument(
        "--connect-timeout-seconds",
        type=float,
        default=10.0,
    )
    parser.add_argument(
        "--authenticate-timeout-seconds",
        type=float,
        default=10.0,
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=10.0,
    )
    parser.add_argument(
        "--close-timeout-seconds",
        type=float,
        default=5.0,
    )
    parser.add_argument(
        "--confirm-real-vts-execution",
        required=True,
    )
    parser.add_argument(
        "--confirm-private-artifacts-outside-repo",
        required=True,
    )
    return parser


def _print_markers(
    *,
    status: str,
    stage: str,
    values: Mapping[str, Any],
) -> None:
    print(f"v550_vts_operator_run_status: {status}")
    print(f"v550_vts_operator_run_stage: {stage}")
    for key in (
        "actual_pyvts_imported",
        "actual_websocket_connected",
        "actual_vts_authenticated",
        "actual_model_loaded",
        "actual_hotkey_inventory_loaded",
        "expression_verified",
        "emotion_verified",
        "gesture_verified",
        "reset_expression_verified",
        "required_four_intents_verified",
        "stop_motion_supported",
        "stop_motion_verified",
        "optional_stop_motion_contract",
        "real_hotkey_execution_verified",
        "real_motion_execution_verified",
        "operator_visual_confirmation_complete",
        "session_close_verified",
        "bridge_thread_terminated",
        "repo_clean_after",
    ):
        print(f"v550_{key}: {bool(values.get(key, False))}")
    print("v550_token_material_exposed: False")
    print("v550_token_path_exposed: False")
    print("v550_hotkey_name_exposed: False")
    print("v550_hotkey_identifier_exposed: False")
    print("v550_model_identity_exposed: False")
    print("v550_provider_payload_exposed: False")
    print("v550_raw_exception_exposed: False")
    print(
        "v550_private_config_outside_repo: "
        f"{bool(values.get('private_config_outside_repo', False))}"
    )
    print(
        "v550_private_token_outside_repo: "
        f"{bool(values.get('private_token_outside_repo', False))}"
    )
    print(
        "v550_private_evidence_outside_repo: "
        f"{bool(values.get('private_evidence_outside_repo', False))}"
    )
    print("v550_drc_repo_changed: False")


def main() -> int:
    args = _build_parser().parse_args()
    values: dict[str, Any] = {
        "actual_pyvts_imported": False,
        "actual_websocket_connected": False,
        "actual_vts_authenticated": False,
        "actual_model_loaded": False,
        "actual_hotkey_inventory_loaded": False,
        "expression_verified": False,
        "emotion_verified": False,
        "gesture_verified": False,
        "reset_expression_verified": False,
        "required_four_intents_verified": False,
        "stop_motion_supported": False,
        "stop_motion_verified": False,
        "optional_stop_motion_contract": False,
        "real_hotkey_execution_verified": False,
        "real_motion_execution_verified": False,
        "operator_visual_confirmation_complete": False,
        "session_close_verified": False,
        "bridge_thread_terminated": False,
        "repo_clean_after": False,
        "private_config_outside_repo": False,
        "private_token_outside_repo": False,
        "private_evidence_outside_repo": False,
    }
    stage = "validation"
    session = None
    try:
        root = _repo_root()
        if root != REPO_ROOT.resolve() or Path.cwd().resolve() != root:
            raise ValueError("Run this command from the repository root.")
        if args.confirm_real_vts_execution != REAL_CONFIRMATION:
            raise ValueError(
                "Real VTube Studio confirmation did not match."
            )
        if (
            args.confirm_private_artifacts_outside_repo
            != PRIVATE_CONFIRMATION
        ):
            raise ValueError(
                "Private-artifact confirmation did not match."
            )
        if _status_paths(root) - {".vscode/settings.json"}:
            raise ValueError(
                "A clean accepted FW-VTS-0f1c worktree is required."
            )
        for value, label in (
            (args.connect_timeout_seconds, "connect timeout"),
            (
                args.authenticate_timeout_seconds,
                "authenticate timeout",
            ),
            (args.request_timeout_seconds, "request timeout"),
            (args.close_timeout_seconds, "close timeout"),
        ):
            if value <= 0:
                raise ValueError(f"{label} must be positive.")

        config_path = _absolute_outside_repo(
            args.private_config,
            root=root,
            label="Private configuration",
        )
        if (
            not config_path.is_file()
            or config_path.stat().st_size > 64 * 1024
        ):
            raise ValueError(
                "Private configuration is unavailable or too large."
            )
        values["private_config_outside_repo"] = True

        evidence_root = Path(args.evidence_root).expanduser()
        if not evidence_root.is_absolute():
            raise ValueError("Evidence root must be an absolute path.")
        evidence_root = evidence_root.resolve()
        if _is_inside(evidence_root, root):
            raise ValueError(
                "Evidence root must remain outside the repository."
            )
        evidence_root.mkdir(parents=True, exist_ok=True)
        if not evidence_root.is_dir():
            raise ValueError("Evidence root must be a directory.")
        values["private_evidence_outside_repo"] = True

        private = _load_private_config(config_path, root=root)
        values["stop_motion_supported"] = bool(
            private["stop_motion_supported"]
        )
        values["optional_stop_motion_contract"] = True
        values["private_token_outside_repo"] = True
        if private["token_path"].stat().st_size > 4096:
            raise ValueError(
                "Private authentication token file is too large."
            )
        token = (
            private["token_path"]
            .read_text(encoding="utf-8")
            .strip()
        )
        if not token or len(token) > 256:
            raise ValueError(
                "Private authentication token is empty or invalid."
            )

        try:
            pyvts_version = version("pyvts")
        except PackageNotFoundError as exc:
            raise RuntimeError("pyvts_runtime_not_installed") from exc
        if pyvts_version != EXPECTED_PYVTS_VERSION:
            raise RuntimeError("pyvts_version_not_accepted")

        stage = "preflight"
        session = create_motion_session(
            adapter="vts",
            real_adapter_enabled=True,
            allow_provider_execution=True,
            runtime_available=True,
            model_selected=True,
            vts_endpoint_host=private["host"],
            vts_endpoint_port=private["port"],
            vts_authentication_token=token,
            vts_hotkey_bindings=private["bindings"],
            vts_connect_timeout_seconds=float(
                args.connect_timeout_seconds
            ),
            vts_authenticate_timeout_seconds=float(
                args.authenticate_timeout_seconds
            ),
            vts_request_timeout_seconds=float(
                args.request_timeout_seconds
            ),
            vts_close_timeout_seconds=float(
                args.close_timeout_seconds
            ),
        )
        token = ""

        capability = session.preflight()
        metadata = dict(capability.public_metadata)
        values.update(
            {
                "actual_pyvts_imported": (
                    metadata.get("provider_sdk_imported") is True
                ),
                "actual_websocket_connected": (
                    metadata.get("connected") is True
                ),
                "actual_vts_authenticated": (
                    metadata.get("authenticated") is True
                ),
                "actual_model_loaded": (
                    metadata.get("model_loaded") is True
                ),
                "actual_hotkey_inventory_loaded": (
                    metadata.get("hotkey_inventory_loaded") is True
                ),
            }
        )
        if not _capability_matches_private(
            capability,
            private,
            values,
        ):
            raise RuntimeError("root_public_preflight_not_ready")

        stage = "real_motion"
        results, verified = _run_intents(session, private)
        for intent_name, accepted in verified.items():
            values[f"{intent_name}_verified"] = accepted

        values["required_four_intents_verified"] = all(
            values[f"{intent_name}_verified"]
            for intent_name in REQUIRED_INTENTS
        )
        values["stop_motion_verified"] = bool(
            values["stop_motion_supported"]
            and verified["stop_motion"]
        )
        values["real_hotkey_execution_verified"] = all(
            entry["real_hotkey_execution_verified"]
            for entry in results.values()
        )
        values["real_motion_execution_verified"] = all(
            entry["real_motion_verified"]
            for entry in results.values()
        )
        values["operator_visual_confirmation_complete"] = all(
            entry["operator_visual_confirmation"]
            for entry in results.values()
        )

        stage = "cleanup"
        session.close()
        session.close()
        values["session_close_verified"] = session.is_closed
        values["bridge_thread_terminated"] = (
            not _bridge_threads_alive()
        )
        session = None
        values["repo_clean_after"] = not (
            _status_paths(root) - {".vscode/settings.json"}
        )

        run_id = uuid.uuid4().hex
        run_dir = (
            evidence_root / f"v550_vts_acceptance_{run_id}"
        )
        run_dir.mkdir(parents=False, exist_ok=False)
        evidence_path = (
            run_dir / "real_motion_operator_evidence.json"
        )
        evidence = {
            "schema": EVIDENCE_SCHEMA,
            "run_id": run_id,
            "created_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "repo_head": _git(root, "rev-parse", "HEAD"),
            "pyvts_version": pyvts_version,
            "repo_clean_before": True,
            "repo_clean_after": values["repo_clean_after"],
            "private_config_outside_repo": values[
                "private_config_outside_repo"
            ],
            "private_token_outside_repo": values[
                "private_token_outside_repo"
            ],
            "private_evidence_outside_repo": values[
                "private_evidence_outside_repo"
            ],
            "endpoint_loopback_only": True,
            "actual_pyvts_imported": values[
                "actual_pyvts_imported"
            ],
            "actual_websocket_connected": values[
                "actual_websocket_connected"
            ],
            "actual_vts_authenticated": values[
                "actual_vts_authenticated"
            ],
            "actual_model_loaded": values[
                "actual_model_loaded"
            ],
            "actual_hotkey_inventory_loaded": values[
                "actual_hotkey_inventory_loaded"
            ],
            "intent_results": results,
            "required_four_intents_verified": values[
                "required_four_intents_verified"
            ],
            "stop_motion_supported": values[
                "stop_motion_supported"
            ],
            "stop_motion_verified": values[
                "stop_motion_verified"
            ],
            "optional_stop_motion_contract": values[
                "optional_stop_motion_contract"
            ],
            "real_hotkey_execution_verified": values[
                "real_hotkey_execution_verified"
            ],
            "real_motion_execution_verified": values[
                "real_motion_execution_verified"
            ],
            "operator_visual_confirmation_complete": values[
                "operator_visual_confirmation_complete"
            ],
            "session_close_verified": values[
                "session_close_verified"
            ],
            "bridge_thread_terminated": values[
                "bridge_thread_terminated"
            ],
            "automatic_retry_executed": False,
            "automatic_reconnect_executed": False,
            "polling_loop_created": False,
            "token_material_exposed": False,
            "token_path_exposed": False,
            "hotkey_name_exposed": False,
            "hotkey_identifier_exposed": False,
            "model_identity_exposed": False,
            "provider_payload_exposed": False,
            "raw_exception_exposed": False,
            "drc_repo_changed": False,
        }
        _write_json(evidence_path, evidence)

        optional_stop_accepted = (
            values["stop_motion_verified"]
            if values["stop_motion_supported"]
            else not values["stop_motion_verified"]
        )
        success = all(
            (
                values["actual_pyvts_imported"],
                values["actual_websocket_connected"],
                values["actual_vts_authenticated"],
                values["actual_model_loaded"],
                values["actual_hotkey_inventory_loaded"],
                values["required_four_intents_verified"],
                values["optional_stop_motion_contract"],
                optional_stop_accepted,
                values["real_hotkey_execution_verified"],
                values["real_motion_execution_verified"],
                values["operator_visual_confirmation_complete"],
                values["session_close_verified"],
                values["bridge_thread_terminated"],
                values["repo_clean_after"],
                evidence_path.is_file(),
            )
        )
        _print_markers(
            status="completed" if success else "not_accepted",
            stage="completed" if success else stage,
            values=values,
        )
        print(f"v550_vts_private_evidence_run_id: {run_id}")
        print(
            "v550_vts_private_evidence_validation: "
            "run-private-verifier"
        )
        return 0 if success else 1
    except Exception:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
        values["bridge_thread_terminated"] = (
            not _bridge_threads_alive()
        )
        try:
            root = _repo_root()
            values["repo_clean_after"] = not (
                _status_paths(root) - {".vscode/settings.json"}
            )
        except Exception:
            values["repo_clean_after"] = False
        _print_markers(
            status="failed",
            stage=stage,
            values=values,
        )
        print(
            "v550_vts_operator_safe_message: "
            "operator acceptance did not complete"
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
