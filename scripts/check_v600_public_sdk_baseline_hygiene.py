"""Aggregate FW-RT6-0b Control D public SDK hygiene checker.

Offline-safe: no provider, network, microphone, playback, or VTS execution.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_BASELINE_HEAD = "136be27c9f6fe62b7753c64f4fed02ae94f98da9"
EXPECTED_SURFACE = {
    "README.md",
    "docs/v600_current_source_gap_inventory.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_public_sdk_baseline_hygiene.py",
}
FORBIDDEN_RUNTIME_PREFIXES = (
    "framework/",
    "core/",
    "llm/",
    "stt/",
    "tts/",
    "live2d/",
    "plugins/",
)
FORBIDDEN_IMPORTED_MODULES = (
    "openai",
    "elevenlabs",
    "pyvts",
    "websockets",
    "tts.voice_engine",
    "live2d.vts_client",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _changed_paths() -> set[str]:
    paths: set[str] = set()
    for args in (
        ("-c", "core.safecrlf=false", "diff", "--name-only"),
        ("-c", "core.safecrlf=false", "diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        output = _git(*args)
        paths.update(line.replace("\\", "/") for line in output.splitlines() if line.strip())
    return paths


def check_repository_contract() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_BASELINE_HEAD, "unexpected Control D baseline")
    changed = _changed_paths()
    _assert(changed == EXPECTED_SURFACE, f"unexpected Control D surface: {sorted(changed)}")
    runtime = [
        path
        for path in changed
        if path.endswith(".py")
        and path != "scripts/check_v600_public_sdk_baseline_hygiene.py"
        and path.startswith(FORBIDDEN_RUNTIME_PREFIXES)
    ]
    _assert(not runtime, f"runtime Python changed by Control D: {runtime}")
    print("[OK] Control D baseline and exact four-file docs/test surface match")


def check_public_manifest() -> None:
    import framework
    from framework.public_api import PUBLIC_API_NAMES, PROVIDER_COMPAT_LAZY_EXPORT_MODULES

    _assert(len(PUBLIC_API_NAMES) == 95, "canonical public API count changed")
    _assert(len(set(PUBLIC_API_NAMES)) == 95, "canonical public API contains duplicates")
    _assert(list(framework.__all__) == list(PUBLIC_API_NAMES), "framework.__all__ drifted")
    _assert(set(PROVIDER_COMPAT_LAZY_EXPORT_MODULES).issubset(PUBLIC_API_NAMES), "lazy compatibility exports missing")
    _assert(framework.__version__ == "6.0.0.dev0", "source version changed")
    _assert("__version__" not in framework.__all__, "__version__ must not alter wildcard surface")
    imported = [name for name in FORBIDDEN_IMPORTED_MODULES if name in sys.modules]
    _assert(not imported, f"root import loaded forbidden modules: {imported}")
    print("[OK] canonical 95-name root-public manifest remains provider-safe")


def check_voice_output_hygiene() -> None:
    source = (PROJECT_ROOT / "framework/audio/voice_output.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "VoiceOutputSession"]
    _assert(len(classes) == 1, "VoiceOutputSession class count changed")
    names = [node.name for node in classes[0].body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    _assert(not duplicates, f"duplicate VoiceOutputSession methods: {duplicates}")

    from framework import VoiceOutputRequest, create_voice_output_session
    session = create_voice_output_session()
    _assert(callable(session.info), "VoiceOutputSession.info must remain a method")
    session.close()
    session.close()
    request = VoiceOutputRequest(text="closed", requested_audio_format="mp3")
    for result in (session.create_output(request), session.speak(request)):
        _assert(result.request_state == "failed", "closed result state changed")
        _assert(result.public_metadata.get("public_error_code") == "session_closed", "closed error code changed")
        _assert(not result.audio_ready, "closed result exposed audio")
    print("[OK] VoiceOutputSession lifecycle remains single-path and compatible")


def check_version_contract() -> None:
    from framework.audio.voice_output import VoiceOutputSessionInfo
    from framework.capabilities import get_capabilities
    from framework.facade import TextChatSessionInfo
    from framework.motion_session import MotionSessionInfo
    from framework.realtime_session import RealtimeSessionInfo
    from framework.version import (
        CAPABILITIES_SCHEMA_VERSION,
        FRAMEWORK_SOURCE_VERSION,
        LATEST_PUBLISHED_RELEASE,
        MOTION_API_VERSION,
        REALTIME_API_VERSION,
        TEXT_CHAT_API_VERSION,
        VOICE_INPUT_API_VERSION,
        VOICE_OUTPUT_BOUNDARY_VERSION,
    )
    from framework.voice_input_session import VoiceInputSessionInfo

    _assert(FRAMEWORK_SOURCE_VERSION == "6.0.0.dev0", "source version drift")
    _assert(LATEST_PUBLISHED_RELEASE == "5.5.0", "published release drift")
    _assert(TextChatSessionInfo.__dataclass_fields__["api_version"].default == TEXT_CHAT_API_VERSION == "4.0", "text API drift")
    _assert(VoiceOutputSessionInfo.__dataclass_fields__["boundary_version"].default == VOICE_OUTPUT_BOUNDARY_VERSION == "v5.lazy_provider_adapter", "voice-output boundary drift")
    _assert(VoiceInputSessionInfo().api_version == VOICE_INPUT_API_VERSION == "5.2.0", "voice-input API drift")
    _assert(RealtimeSessionInfo().api_version == REALTIME_API_VERSION == "5.2.0", "realtime API drift")
    _assert(MotionSessionInfo().api_version == MOTION_API_VERSION == "5.5.0", "motion API drift")
    _assert(get_capabilities(real_tts_enabled=False).schema_version == CAPABILITIES_SCHEMA_VERSION == "v5.1.capabilities", "capability schema drift")
    print("[OK] central source/API/schema metadata preserves frozen compatibility values")


def check_docs_sync() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    gap = (PROJECT_ROOT / "docs/v600_current_source_gap_inventory.md").read_text(encoding="utf-8")
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    _assert("FW-RT6-0b-D-PUBLIC-SDK-HYGIENE-ACCEPTANCE:BEGIN" in readme, "README Control D marker missing")
    _assert("FW-RT6-0b-D-GAP-RESOLUTION-SYNC:BEGIN" in gap, "gap resolution marker missing")
    _assert("FW-RT6-0b-D-ACCEPTANCE-SYNC:BEGIN" in tasklist, "tasklist Control D marker missing")
    _assert("G-14 installable SDK/resource-root contract: UNRESOLVED / FW-RT6-0c" in gap, "G-14 must remain unresolved")
    _assert("capability truthfulness across modules: UNRESOLVED / FW-RT6-1d" in gap, "capability truthfulness must remain unresolved")
    _assert(tasklist.count("- [x] ") >= 8, "FW-RT6-0b tasks were not checked")
    print("[OK] README, gap inventory, and tasklist are synchronized without overclaiming later work")


def main() -> None:
    check_repository_contract()
    check_public_manifest()
    check_voice_output_hygiene()
    check_version_contract()
    check_docs_sync()
    print("v600_public_sdk_baseline_hygiene_status: implemented-awaiting-review")
    print("v600_control_a_accepted: True")
    print("v600_control_b_accepted: True")
    print("v600_control_c_accepted: True")
    print("v600_exact_change_surface_count: 4")
    print("v600_runtime_changed_by_control_d: False")
    print("v600_root_public_name_count: 95")
    print("v600_framework_source_version: 6.0.0.dev0")
    print("v600_latest_published_release: 5.5.0")
    print("v600_capability_truthfulness_changed: False")
    print("v600_network_execution: False")
    print("v600_provider_execution: False")
    print("v600_microphone_used: False")
    print("v600_audio_playback: False")
    print("v600_vts_execution: False")
    print("v600_drc_repository_accessed: False")
    print("v600_next_checkpoint: FW-RT6-0c")
    print("v600_next_checkpoint_authorized: False")
    print("[OK] FW-RT6-0b Control D public SDK baseline hygiene checker passed")


if __name__ == "__main__":
    main()
