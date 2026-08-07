"""FW-RT6-7a Control C aggregate voice-input acceptance gate."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "49558876e9301cddb85830b062a9ef56eeb6cb1e"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_voice_input_acceptance.py",
}


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, check=False)
    _assert(result.returncode == 0, "command failed: " + " ".join(command) + "\n" + result.stdout + result.stderr)
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git("diff", "--name-only", "HEAD").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {path.strip().replace("\\", "/") for path in paths if path.strip()}


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    _assert(spec is not None and spec.loader is not None, f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_git_surface() -> None:
    _assert(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _assert(_git("rev-parse", "origin/main") == EXPECTED_HEAD, "origin/main drift")
    actual = _changed_paths()
    _assert(actual == EXPECTED_SURFACE, f"Control C exact surface drift; expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}")
    print("[OK] baseline and exact three-file FW-RT6-7a Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_a = _load("_fw_rt6_7a_control_a", "scripts/smoke_v600_voice_input_control_a.py")
    control_b = _load("_fw_rt6_7a_control_b", "scripts/smoke_v600_voice_input_control_b.py")
    control_a.check_capability_correction()
    control_a.check_session_identity_and_event_scaffold()
    control_a.check_default_fake_path_preserved()
    control_a.check_docs_and_boundaries()
    control_b.check_default_fake_and_explicit_adapter_precedence()
    control_b.check_real_request_never_silently_falls_back_to_fake()
    control_b.check_session_owned_real_composition_without_provider_specific_host_objects()
    control_b.check_internal_real_chain_and_public_surface()
    control_b.check_docs_and_control_boundaries()
    print("[OK] accepted Control A+B capability, identity and composition regressions conform")


def check_aggregate_contract() -> None:
    import framework
    from framework.version import VOICE_INPUT_API_VERSION
    from framework.voice_input_capability import VoiceInputProviderStatus, get_voice_input_capabilities

    _assert(len(framework.__all__) == 127, "framework root-public count drift")
    _assert(VOICE_INPUT_API_VERSION == "5.2.0", "voice-input compatibility version drift")
    session = framework.create_voice_input_session()
    _assert(session.info.api_version == VOICE_INPUT_API_VERSION, "session info central version connection drift")
    openai = get_voice_input_capabilities(provider="openai", real_stt_enabled=True, allow_provider_execution=True, credential_env={"OPENAI_API_KEY": "presence-only"})
    _assert(openai.provider_status is VoiceInputProviderStatus.REAL_STT_EXECUTOR_AVAILABLE, "OpenAI capability remains stale")
    _assert(openai.supports_real_stt is True, "OpenAI real STT implementation support missing")
    _assert(openai.runtime_probe_performed is False, "capability inspection probed runtime")
    print("[OK] aggregate capability/version/public-surface truthfulness conforms")


def check_docs_and_scope() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7a — VoiceInputSession capability correction")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _assert(section.count("- [x]") == 6 and section.count("- [ ]") == 0, "FW-RT6-7a must be 6 / 6 accepted-candidate")
    for text in (tasklist, facade):
        _assert("FW-RT6-7a-C-AGGREGATE-ACCEPTANCE:BEGIN" in text, "Control C aggregate marker missing")
    for marker in ("FW-RT6-7a tasks: 6 / 6 ACCEPTED-CANDIDATE", "FW-RT6-7b: NOT_AUTHORIZED", "FW-RT6-7c: NOT_AUTHORIZED", "runtime source changed by Control C: False", "commit / push: NOT_AUTHORIZED"):
        _assert(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    _assert("Control C changes no runtime source" in facade, "facade runtime boundary missing")
    print("[OK] six FW-RT6-7a tasks close as acceptance-candidates while 7b/7c remain unauthorized")


def check_runtime_unchanged() -> None:
    runtime = {path for path in _changed_paths() if path.startswith(("framework/", "core/", "providers/", "tts/", "vts/"))}
    _assert(not runtime, f"Control C changed runtime sources: {sorted(runtime)!r}")
    print("[OK] Control C introduces no runtime source change")


def main() -> None:
    check_git_surface()
    check_accepted_control_a_b()
    check_aggregate_contract()
    check_docs_and_scope()
    check_runtime_unchanged()
    print("v600_rt6_7a_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7a_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7a_control_c_status: implemented-awaiting-review")
    print("v600_rt6_7a_control_c_exact_surface: 3 files")
    print("v600_rt6_7a_runtime_changed: False")
    print("v600_rt6_7a_task_count: 6 / 6 ACCEPTED-CANDIDATE")
    print("v600_rt6_7b_status: NOT_AUTHORIZED")
    print("v600_rt6_7c_status: NOT_AUTHORIZED")
    print("v600_rt6_7a_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
