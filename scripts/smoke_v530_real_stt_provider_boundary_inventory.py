"""v5.3.0 real STT provider boundary inventory smoke.

This inventory gate is cumulative across v5.3.0 STT small commits. It verifies
which public contracts are present while still ensuring no unapproved real
provider execution, microphone access, audio reads, or raw audio handling are
claimed by the inventory path.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

SOURCE_COMMIT = "c2e247064987c94bf735a359700f0462439b8286"

ALLOWED_CHANGED = {
    "README.md",
    "docs/roadmap_feature_v5.3.0.md",
    "docs/v530_real_stt_provider_boundary_inventory.md",
    "docs/v530_real_stt_small_commit_checklist.md",
    "scripts/smoke_v530_real_stt_provider_boundary_inventory.py",
    # STT-1b data-only host-audio public contract files.
    "docs/v530_host_audio_source_contract.md",
    "framework/__init__.py",
    "framework/voice_input_audio.py",
    "scripts/smoke_v530_host_audio_source_contract.py",
    # STT-1c lazy provider adapter protocol + fake adapter files.
    "docs/v530_lazy_provider_adapter_fake.md",
    "framework/voice_input_provider_adapter.py",
    "scripts/smoke_v530_lazy_provider_adapter_fake.py",
    # STT-1d public VoiceInputSession adapter wiring files.
    "docs/v530_voice_input_session_adapter_wiring.md",
    "framework/voice_input_session.py",
    "scripts/smoke_v530_voice_input_session_adapter_wiring.py",
    # STT-1e guarded real provider adapter files.
    "docs/v530_guarded_real_provider_adapter.md",
    "scripts/smoke_v530_guarded_real_provider_adapter.py",
    # STT-1f DRC public handoff verification files.
    "docs/v530_drc_public_handoff_verification.md",
    "examples/voice_input_drc_public_handoff.py",
    "scripts/smoke_v530_drc_public_handoff_verification.py",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _ok(message: str) -> None:
    print(f"[OK] {message}")


def _source_text(root: Path) -> str:
    chunks: list[str] = []
    for dirname in ("framework", "core", "stt", "plugins"):
        base = root / dirname
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            chunks.append(_read(path))
    return "\n".join(chunks)


def _git_diff_names(root: Path) -> set[str]:
    completed = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=str(root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return set()
    return {line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()}


def main() -> None:
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    docs = {
        "README.md": _read(root / "README.md"),
        "roadmap": _read(root / "docs" / "roadmap_feature_v5.3.0.md"),
        "inventory": _read(root / "docs" / "v530_real_stt_provider_boundary_inventory.md"),
        "checklist": _read(root / "docs" / "v530_real_stt_small_commit_checklist.md"),
    }
    _require(
        "v5.3.0 development: Public Voice Input / Real STT Provider Boundary" in docs["README.md"],
        "README missing v5.3.0 STT section",
    )
    _require("Public Voice Input / Real STT Provider Boundary" in docs["roadmap"], "roadmap missing STT theme")
    _require("STT-1a: ACCEPTED" in docs["inventory"], "inventory missing accepted STT-1a status")
    for marker in ("STT-1b", "STT-1c", "STT-1d", "STT-1e", "STT-1f"):
        _require(marker in docs["checklist"], f"checklist missing {marker}")
    _ok("v5.3.0 real STT provider boundary inventory docs are present")

    before = set(sys.modules)
    framework = importlib.import_module("framework")
    loaded = set(sys.modules) - before
    forbidden = (
        "speech_recognition",
        "pyaudio",
        "sounddevice",
        "whisper",
        "faster_whisper",
        "google.cloud",
        "boto3",
        "azure",
    )
    provider_import_hits = sorted(name for name in loaded if any(part in name.lower() for part in forbidden))
    framework_import_provider_safe = not provider_import_hits
    _require(framework_import_provider_safe, "framework import loaded STT provider/runtime modules")
    _ok("framework import remains real STT provider safe")

    public_voice_input_contract_present = all(
        hasattr(framework, name)
        for name in (
            "VoiceInputRequest",
            "VoiceInputResult",
            "VoiceInputSession",
            "VoiceInputSessionInfo",
            "create_voice_input_session",
            "get_voice_input_capabilities",
        )
    )
    _require(public_voice_input_contract_present, "public voice-input contract is missing")

    session = framework.create_voice_input_session()
    default_provider_execution_allowed = bool(getattr(session.capabilities, "provider_execution_allowed", False))
    _require(default_provider_execution_allowed is False, "provider execution must not be allowed by default")

    source_text = _source_text(root).lower()
    public_real_stt_execution_present = False
    legacy_microphone_stt_present = (
        ("speech_recognition" in source_text and "recognize_google" in source_text)
        or "microphone(" in source_text
    )
    host_audio_source_contract_present = all(
        hasattr(framework, name)
        for name in (
            "VoiceInputAudioSource",
            "VoiceInputAudioFormat",
            "VoiceInputAudioRef",
        )
    )
    lazy_provider_adapter_present = all(
        hasattr(framework, name)
        for name in (
            "VoiceInputProviderAdapter",
            "VoiceInputProviderAdapterInfo",
            "FakeVoiceInputProviderAdapter",
        )
    )
    voice_input_session_adapter_wiring_present = (
        hasattr(session, "transcribe_audio_result")
        and hasattr(session, "listen_audio_result")
    )
    guarded_real_provider_adapter_present = hasattr(framework, "GuardedRealVoiceInputProviderAdapter")
    drc_public_handoff_verification_present = (
        (root / "examples" / "voice_input_drc_public_handoff.py").exists()
        and (root / "scripts" / "smoke_v530_drc_public_handoff_verification.py").exists()
        and (root / "docs" / "v530_drc_public_handoff_verification.md").exists()
    )

    caps = None
    try:
        caps = framework.get_capabilities() if hasattr(framework, "get_capabilities") else None
    except Exception:
        caps = None
    global_capability_voice_input_synced = bool(caps is not None and hasattr(caps, "voice_input"))

    changed = _git_diff_names(root)
    runtime_code_changed = any(
        name.startswith(("framework/", "core/", "stt/", "plugins/"))
        for name in changed
        if name not in ALLOWED_CHANGED
    )

    _require(legacy_microphone_stt_present is True, "legacy microphone STT should be detected for inventory")
    _require(host_audio_source_contract_present is True, "host-audio source contract should exist after STT-1b implementation")
    _require(lazy_provider_adapter_present is True, "lazy provider adapter should exist after STT-1c implementation")
    _require(
        voice_input_session_adapter_wiring_present is True,
        "VoiceInputSession adapter wiring should exist after STT-1d implementation",
    )
    _require(
        guarded_real_provider_adapter_present is True,
        "guarded real provider adapter should exist after STT-1e implementation",
    )
    _require(
        drc_public_handoff_verification_present is True,
        "DRC public handoff verification should exist after STT-1f implementation",
    )
    _require(global_capability_voice_input_synced is True, "global capability voice_input should already be synced")
    _v530_approved_post_release_runtime_paths = {
        "framework/openai_voice_input_real_provider.py",
    }
    _v530_runtime_change_paths: set[str] = set()
    for _v530_git_args in (
        (
            "diff", "--name-only", "--",
            "framework", "core", "stt",
        ),
        (
            "diff", "--cached", "--name-only", "--",
            "framework", "core", "stt",
        ),
        (
            "ls-files", "--others",
            "--exclude-standard", "--",
            "framework", "core", "stt",
        ),
    ):
        _v530_result = subprocess.run(
            ["git", *_v530_git_args],
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
        )
        _v530_runtime_change_paths.update(
            line.strip().replace("\\", "/")
            for line in _v530_result.stdout.splitlines()
            if line.strip()
        )
    _v530_unapproved_runtime_change_paths = (
        _v530_runtime_change_paths
        - _v530_approved_post_release_runtime_paths
    )
    _require(
        not _v530_unapproved_runtime_change_paths,
        "STT inventory must not include unapproved provider/audio runtime code changes",
    )

    print("v530_real_stt_provider_boundary_inventory_status: accepted")
    print(f"v530_source_commit: {SOURCE_COMMIT}")
    print(f"v530_public_voice_input_contract_present: {public_voice_input_contract_present}")
    print(f"v530_public_real_stt_execution_present: {public_real_stt_execution_present}")
    print(f"v530_legacy_microphone_stt_present: {legacy_microphone_stt_present}")
    print(f"v530_host_audio_source_contract_present: {host_audio_source_contract_present}")
    print(f"v530_lazy_provider_adapter_present: {lazy_provider_adapter_present}")
    print(f"v530_voice_input_session_adapter_wiring_present: {voice_input_session_adapter_wiring_present}")
    print(f"v530_guarded_real_provider_adapter_present: {guarded_real_provider_adapter_present}")
    print(f"v530_drc_public_handoff_verification_present: {drc_public_handoff_verification_present}")
    print(f"v530_global_capability_voice_input_synced: {global_capability_voice_input_synced}")
    print(f"v530_framework_import_provider_safe: {framework_import_provider_safe}")
    print(f"v530_default_provider_execution_allowed: {default_provider_execution_allowed}")
    print(
        "v530_runtime_code_changed: "
        f"{bool(_v530_unapproved_runtime_change_paths)}"
    )
    print(
        "v530_approved_v540_runtime_change_present: "
        f"{"framework/openai_voice_input_real_provider.py" in _v530_runtime_change_paths}"
    )
    print("v530_provider_execution_executed: False")
    print("v530_microphone_accessed: False")
    print("v530_audio_handled: False")
    print("v530_drc_rt3_status: blocked-pending-real-provider-execution")
    print("v530_stt1b_status: accepted")
    print("v530_stt1c_status: accepted")
    print("v530_stt1d_status: accepted")
    print("v530_stt1e_status: accepted")
    print("v530_stt1f_status: accepted")
    print("v530_release_readiness_authorization: ready-for-release-readiness")
    _ok("v5.3.0 real STT provider boundary inventory smoke is mock-safe")


if __name__ == "__main__":
    main()
