"""FW-VTS-0f2 public real-motion acceptance-sync source-only smoke."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_HEAD = "b7b9639dfa1f675ba04a33cd8ce297429f98fd15"
BOOTSTRAP_HEAD = "1f737128554d701150427da4ce1c146759881255"

DOC_PATHS = (
    "README.md",
    "docs/public_facade.md",
    "docs/v550_real_motion_adapter_readiness.md",
    "docs/v550_motion_session_real_adapter_composition.md",
    "docs/v550_vtube_studio_pyvts_transport.md",
    "docs/v550_vtube_studio_operator_acceptance.md",
)

BEGIN_MARKER = "<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:BEGIN -->"
END_MARKER = "<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:END -->"

REQUIRED_BLOCK_MARKERS = (
    "checkpoint: FW-VTS-0f2",
    "status: IMPLEMENTED / AWAITING_REVIEW",
    f"accepted framework head: {ACCEPTANCE_HEAD}",
    f"accepted bootstrap head: {BOOTSTRAP_HEAD}",
    "pyvts version: 0.3.3",
    "actual pyvts import: VERIFIED",
    "actual WebSocket connection: VERIFIED",
    "actual VTube Studio authentication: VERIFIED",
    "model loaded: VERIFIED",
    "hotkey inventory loaded: VERIFIED",
    "expression: VERIFIED",
    "emotion: VERIFIED",
    "gesture: VERIFIED",
    "reset_expression: VERIFIED",
    "required four intents: VERIFIED",
    "stop_motion_supported: False",
    "stop_motion_verified: False",
    "optional stop_motion contract: VERIFIED",
    "real hotkey execution: VERIFIED",
    "real motion execution: VERIFIED",
    "operator visual confirmation: COMPLETE",
    "session close: VERIFIED",
    "bridge thread termination: VERIFIED",
    "bootstrap evidence reused: VERIFIED",
    "bootstrap operator unchanged: VERIFIED",
    "private evidence: ACCEPTED_BY_VALIDATOR",
    "DRC repository changed: False",
    "private values recorded in repository: False",
    "real VTS execution repeated by this sync: False",
    "private evidence read by this sync: False",
    "commit / push: NOT_AUTHORIZED",
)

FORBIDDEN_BLOCK_KEYS = (
    "run_id",
    "token_path",
    "token_hash",
    "authentication_token",
    "evidence_path",
    "private_config_path",
    "endpoint_host",
    "endpoint_port",
    "hotkey_name",
    "hotkey_identifier",
    "selector_value",
    "model_identity",
    "provider_payload",
    "raw_exception",
    "websocket_url",
)


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _read(relative: str) -> str:
    path = ROOT / relative
    _require(path.is_file(), f"missing acceptance-sync document: {relative}")
    return path.read_text(encoding="utf-8", errors="strict")


def _extract_block(source: str, *, relative: str) -> str:
    _require(
        source.count(BEGIN_MARKER) == 1,
        f"{relative} must contain exactly one acceptance-sync begin marker",
    )
    _require(
        source.count(END_MARKER) == 1,
        f"{relative} must contain exactly one acceptance-sync end marker",
    )
    before, remainder = source.split(BEGIN_MARKER, 1)
    block, after = remainder.split(END_MARKER, 1)
    _require(
        BEGIN_MARKER not in before + after
        and END_MARKER not in before + after,
        f"{relative} contains nested or duplicate acceptance-sync markers",
    )
    return "\n".join(line.rstrip() for line in block.strip().splitlines())


def main() -> None:
    blocks = {
        relative: _extract_block(_read(relative), relative=relative)
        for relative in DOC_PATHS
    }

    reference = blocks[DOC_PATHS[0]]
    for relative, block in blocks.items():
        _require(
            block == reference,
            f"acceptance-sync block differs in {relative}",
        )

    for marker in REQUIRED_BLOCK_MARKERS:
        _require(
            marker in reference,
            f"acceptance-sync block missing marker: {marker}",
        )

    lower_block = reference.casefold()
    for forbidden in FORBIDDEN_BLOCK_KEYS:
        _require(
            forbidden.casefold() not in lower_block,
            f"acceptance-sync block contains private key: {forbidden}",
        )

    _require(
        re.search(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", lower_block)
        is None,
        "acceptance-sync block contains a private-style 32-hex run ID",
    )

    _require(
        set(re.findall(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", lower_block))
        == {ACCEPTANCE_HEAD, BOOTSTRAP_HEAD},
        "acceptance-sync block contains unexpected commit identifiers",
    )

    print("v550_vtube_studio_real_motion_acceptance_sync_smoke: PASS")
    print("v550_acceptance_sync_document_count: 6")
    print("v550_acceptance_sync_blocks_identical: True")
    print("v550_acceptance_head_recorded: True")
    print("v550_bootstrap_head_recorded: True")
    print("v550_required_four_intents_recorded: True")
    print("v550_optional_stop_motion_contract_recorded: True")
    print("v550_stop_motion_supported: False")
    print("v550_stop_motion_verified: False")
    print("v550_private_evidence_accepted_marker_recorded: True")
    print("v550_private_values_recorded: False")
    print("v550_actual_pyvts_imported_in_smoke: False")
    print("v550_network_execution_in_smoke: False")
    print("v550_real_motion_execution_in_smoke: False")
    print("v550_private_evidence_read_in_smoke: False")
    print("[OK] FW-VTS-0f2 public acceptance-sync smoke passed")


if __name__ == "__main__":
    main()
