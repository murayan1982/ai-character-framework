"""Operator-only local VTube Studio token bootstrap for FW-VTS-0f.

This command may import the actual optional pyvts package, open a loopback
WebSocket connection to a locally running VTube Studio instance, request an
operator-approved authentication token, authenticate that token, and persist it
to an explicitly selected private path outside the repository.

It is intentionally separate from the root-public MotionSession runtime. It
never prints token material, private paths, provider payloads, or raw exception
text.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PYVTS_VERSION = "0.3.3"
PLUGIN_NAME = "AI Character Framework"
PLUGIN_DEVELOPER = "murayan"
BOOTSTRAP_SCHEMA = "ai-character-framework-v550-vts-bootstrap-evidence-v1"
REAL_CONFIRMATION = "I_ACCEPT_LOCAL_VTUBE_STUDIO_TOKEN_BOOTSTRAP"
PRIVATE_CONFIRMATION = (
    "I_WILL_KEEP_VTS_TOKEN_AND_EVIDENCE_OUTSIDE_THE_REPOSITORY"
)
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
    resolved = candidate.resolve()
    if _is_inside(resolved, root):
        raise ValueError(f"{label} must remain outside the repository.")
    return resolved


def _write_private_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".vts-token-",
        dir=str(path.parent),
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _response_data(response: Any) -> Mapping[str, Any] | None:
    root = _mapping(response)
    if root is None:
        return None
    if str(root.get("messageType", "")).strip() == "APIError":
        return None
    data = root.get("data")
    if isinstance(data, Mapping):
        if "errorID" in data:
            return None
        return data
    return root


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Request and privately persist a local VTube Studio token. "
            "This operator command performs real local provider execution."
        )
    )
    parser.add_argument("--token-output", required=True)
    parser.add_argument("--evidence-root", required=True)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--connect-timeout-seconds", type=float, default=10.0)
    parser.add_argument("--request-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--close-timeout-seconds", type=float, default=5.0)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--confirm-real-vts-execution", required=True)
    parser.add_argument("--confirm-private-artifacts-outside-repo", required=True)
    return parser


async def _bootstrap(
    pyvts_module: Any,
    *,
    host: str,
    port: int,
    connect_timeout: float,
    request_timeout: float,
    close_timeout: float,
) -> tuple[str, dict[str, bool]]:
    constructor = getattr(pyvts_module, "vts")
    client = constructor(
        plugin_info={
            "plugin_name": PLUGIN_NAME,
            "developer": PLUGIN_DEVELOPER,
            "plugin_icon": None,
            "authentication_token_path": "",
        },
        vts_api_info={
            "name": "VTubeStudioPublicAPI",
            "version": "1.0",
            "host": host,
            "port": port,
        },
    )
    markers = {
        "provider_client_created": True,
        "websocket_connected": False,
        "token_request_executed": False,
        "new_token_authenticated": False,
        "provider_close_completed": False,
    }
    try:
        await asyncio.wait_for(client.connect(), timeout=connect_timeout)
        markers["websocket_connected"] = True

        token_request = client.vts_request.authentication_token()
        response = await asyncio.wait_for(
            client.request(token_request),
            timeout=request_timeout,
        )
        markers["token_request_executed"] = True
        data = _response_data(response)
        token = (
            str(data.get("authenticationToken", "")).strip()
            if data is not None
            else ""
        )
        if not token or len(token) > 256 or not token.isascii():
            raise RuntimeError("token_request_rejected")

        client.authentic_token = token
        auth_request = client.vts_request.authentication(token)
        auth_response = await asyncio.wait_for(
            client.request(auth_request),
            timeout=request_timeout,
        )
        auth_data = _response_data(auth_response)
        if auth_data is None or auth_data.get("authenticated") is not True:
            raise RuntimeError("new_token_authentication_rejected")
        markers["new_token_authenticated"] = True
        return token, markers
    finally:
        try:
            await asyncio.wait_for(client.close(), timeout=close_timeout)
            markers["provider_close_completed"] = True
        except Exception:
            markers["provider_close_completed"] = False


def _print_markers(*, status: str, stage: str, values: Mapping[str, bool]) -> None:
    print(f"v550_vts_token_bootstrap_status: {status}")
    print(f"v550_vts_token_bootstrap_stage: {stage}")
    print(
        "v550_actual_pyvts_imported: "
        f"{values.get('actual_pyvts_imported', False)}"
    )
    print(
        "v550_actual_provider_client_created: "
        f"{values.get('provider_client_created', False)}"
    )
    print(
        "v550_actual_websocket_connected: "
        f"{values.get('websocket_connected', False)}"
    )
    print(
        "v550_actual_token_request_executed: "
        f"{values.get('token_request_executed', False)}"
    )
    print(
        "v550_new_token_authenticated: "
        f"{values.get('new_token_authenticated', False)}"
    )
    print(
        "v550_provider_close_completed: "
        f"{values.get('provider_close_completed', False)}"
    )
    print(f"v550_private_token_written: {values.get('token_written', False)}")
    print("v550_token_material_exposed: False")
    print("v550_token_path_exposed: False")
    print("v550_endpoint_value_exposed: False")
    print("v550_provider_payload_exposed: False")
    print("v550_raw_exception_exposed: False")
    print(
        "v550_private_evidence_outside_repo: "
        f"{values.get('private_evidence_outside_repo', False)}"
    )
    print(
        "v550_private_token_outside_repo: "
        f"{values.get('private_token_outside_repo', False)}"
    )
    print(
        "v550_repo_clean_after_operator_run: "
        f"{values.get('repo_clean_after', False)}"
    )


def main() -> int:
    args = _build_parser().parse_args()
    values: dict[str, bool] = {
        "actual_pyvts_imported": False,
        "provider_client_created": False,
        "websocket_connected": False,
        "token_request_executed": False,
        "new_token_authenticated": False,
        "provider_close_completed": False,
        "token_written": False,
        "repo_clean_after": False,
        "private_evidence_outside_repo": False,
        "private_token_outside_repo": False,
    }
    stage = "validation"
    try:
        root = _repo_root()
        if root != REPO_ROOT.resolve() or Path.cwd().resolve() != root:
            raise ValueError("Run this command from the repository root.")
        if args.confirm_real_vts_execution != REAL_CONFIRMATION:
            raise ValueError("Real VTube Studio confirmation did not match.")
        if args.confirm_private_artifacts_outside_repo != PRIVATE_CONFIRMATION:
            raise ValueError("Private-artifact confirmation did not match.")
        if _status_paths(root) - {".vscode/settings.json"}:
            raise ValueError("A clean accepted FW-VTS-0f1 worktree is required.")

        host = str(args.host).strip().casefold()
        if host not in _LOOPBACK_HOSTS:
            raise ValueError("Only an explicit loopback VTube Studio host is allowed.")
        if not 1 <= int(args.port) <= 65535:
            raise ValueError("port must be between 1 and 65535.")
        for value, label in (
            (args.connect_timeout_seconds, "connect timeout"),
            (args.request_timeout_seconds, "request timeout"),
            (args.close_timeout_seconds, "close timeout"),
        ):
            if value <= 0:
                raise ValueError(f"{label} must be positive.")

        token_output = _absolute_outside_repo(
            args.token_output,
            root=root,
            label="Token output",
        )
        evidence_root = _absolute_outside_repo(
            args.evidence_root,
            root=root,
            label="Evidence root",
        )
        if token_output.exists() and not args.overwrite:
            raise ValueError("Token output already exists; explicit overwrite is required.")
        if token_output.exists() and not token_output.is_file():
            raise ValueError("Token output must identify a regular file.")
        token_output.parent.mkdir(parents=True, exist_ok=True)
        values["private_token_outside_repo"] = True
        evidence_root.mkdir(parents=True, exist_ok=True)
        if not evidence_root.is_dir():
            raise ValueError("Evidence root must be a directory.")
        values["private_evidence_outside_repo"] = True

        stage = "provider_import"
        try:
            pyvts_version = version("pyvts")
        except PackageNotFoundError as exc:
            raise RuntimeError("pyvts_runtime_not_installed") from exc
        if pyvts_version != EXPECTED_PYVTS_VERSION:
            raise RuntimeError("pyvts_version_not_accepted")
        pyvts_module = importlib.import_module("pyvts")
        values["actual_pyvts_imported"] = True

        stage = "local_vts_bootstrap"
        token, provider_values = asyncio.run(
            _bootstrap(
                pyvts_module,
                host=host,
                port=int(args.port),
                connect_timeout=float(args.connect_timeout_seconds),
                request_timeout=float(args.request_timeout_seconds),
                close_timeout=float(args.close_timeout_seconds),
            )
        )
        values.update(provider_values)
        if not values["provider_close_completed"]:
            raise RuntimeError("provider_close_not_completed")

        stage = "private_write"
        _write_private_text_atomic(token_output, token)
        token = ""
        values["token_written"] = token_output.is_file() and token_output.stat().st_size > 0
        if not values["token_written"]:
            raise RuntimeError("private_token_write_failed")

        run_id = uuid.uuid4().hex
        run_dir = evidence_root / f"v550_vts_bootstrap_{run_id}"
        run_dir.mkdir(parents=False, exist_ok=False)
        evidence_path = run_dir / "bootstrap_evidence.json"
        values["repo_clean_after"] = not (
            _status_paths(root) - {".vscode/settings.json"}
        )
        evidence = {
            "schema": BOOTSTRAP_SCHEMA,
            "run_id": run_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "repo_head": _git(root, "rev-parse", "HEAD"),
            "pyvts_version": pyvts_version,
            "repo_clean_before": True,
            "repo_clean_after": values["repo_clean_after"],
            "endpoint_loopback_only": True,
            "actual_pyvts_imported": values["actual_pyvts_imported"],
            "provider_client_created": values["provider_client_created"],
            "actual_websocket_connected": values["websocket_connected"],
            "token_request_executed": values["token_request_executed"],
            "new_token_authenticated": values["new_token_authenticated"],
            "provider_close_completed": values["provider_close_completed"],
            "private_token_written": values["token_written"],
            "private_token_outside_repo": values["private_token_outside_repo"],
            "private_evidence_outside_repo": values["private_evidence_outside_repo"],
            "token_material_exposed": False,
            "token_path_exposed": False,
            "endpoint_value_exposed": False,
            "provider_payload_exposed": False,
            "raw_exception_exposed": False,
            "drc_repo_changed": False,
        }
        _write_json(evidence_path, evidence)

        success = all(
            (
                values["actual_pyvts_imported"],
                values["provider_client_created"],
                values["websocket_connected"],
                values["token_request_executed"],
                values["new_token_authenticated"],
                values["provider_close_completed"],
                values["token_written"],
                values["repo_clean_after"],
                evidence_path.is_file(),
            )
        )
        _print_markers(
            status="completed" if success else "not_accepted",
            stage="completed" if success else stage,
            values=values,
        )
        print(f"v550_vts_bootstrap_private_run_id: {run_id}")
        print("v550_vts_bootstrap_evidence_validation: run-private-verifier")
        return 0 if success else 1
    except Exception:
        _print_markers(status="failed", stage=stage, values=values)
        print("v550_vts_bootstrap_safe_message: operator bootstrap did not complete")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
