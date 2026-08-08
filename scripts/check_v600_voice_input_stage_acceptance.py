"""FW-RT6-7b Control C aggregate voice-input stage acceptance gate."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from dataclasses import fields
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_HEAD = "bfe15c03bd9759131d7ef1d39378ce949c3f0970"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_voice_input_stage_acceptance.py",
}


def _require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def _run(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    _require(
        result.returncode == 0,
        "command failed: "
        + " ".join(command)
        + "\n"
        + result.stdout
        + result.stderr,
    )
    return result.stdout


def _git(*args: str) -> str:
    return _run(["git", *args]).strip()


def _changed_paths() -> set[str]:
    paths = _git("diff", "--name-only", "HEAD").splitlines()
    paths += _git("ls-files", "--others", "--exclude-standard").splitlines()
    return {
        path.strip().replace("\\", "/")
        for path in paths
        if path.strip()
    }


def _load(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    _require(spec is not None and spec.loader is not None, f"cannot load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_exact_surface() -> None:
    _require(_git("rev-parse", "HEAD") == EXPECTED_HEAD, "baseline HEAD drift")
    _require(
        _git("rev-parse", "origin/main") == EXPECTED_HEAD,
        "origin/main drift",
    )
    actual = _changed_paths()
    _require(
        actual == EXPECTED_SURFACE,
        "Control C exact surface drift; "
        f"expected={sorted(EXPECTED_SURFACE)!r}; actual={sorted(actual)!r}",
    )
    print("[OK] baseline and exact three-file FW-RT6-7b Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_b = _load(
        "_fw_rt6_7b_control_b_for_aggregate",
        "scripts/smoke_v600_voice_input_stage_control_b.py",
    )
    control_b.check_accepted_foundation_regression()
    control_b.check_abort_and_generation_contract()
    control_b.check_privacy_and_deferred_scope()
    control_b.check_focused_tests()
    print("[OK] accepted Control A+B lifecycle/privacy/abort regressions conform")


def check_aggregate_contract() -> None:
    import framework
    from framework.realtime_event_payloads import DiagnosticEventPayload
    from framework.version import VOICE_INPUT_API_VERSION

    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(VOICE_INPUT_API_VERSION == "5.2.0", "voice-input API version drift")
    session = framework.create_voice_input_session()
    _require(
        session.info.api_version == VOICE_INPUT_API_VERSION,
        "VoiceInputSessionInfo central version connection drift",
    )
    _require(callable(session.abort_input), "public input-abort boundary missing")
    _require(session.abort_input() is False, "idle abort must remain false")
    _require(
        framework.RealtimeEventType.STALE_RESULT_DROPPED.value
        == "realtime.stale_result.dropped",
        "canonical stale-result event drift",
    )
    _require(
        DiagnosticEventPayload(code="aggregate_voice_input").code
        == "aggregate_voice_input",
        "typed stale diagnostic payload unavailable",
    )
    result_fields = {item.name for item in fields(framework.VoiceInputResult)}
    _require(
        not {"session_id", "turn_id", "generation_id"} & result_fields,
        "Control C prematurely adopted FW-RT6-7c result correlation",
    )
    print("[OK] aggregate public/version/result-shape contract conforms")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7b — Voice input stage composition")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 7 and section.count("- [ ]") == 0,
        "FW-RT6-7b must be 7 / 7 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-7b-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
    for marker in (
        "FW-RT6-7b tasks: 7 / 7 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "FW-RT6-7b final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-7c result correlation/close compatibility: NOT_AUTHORIZED",
        "partial transcript/audio streaming: DEFERRED_TO_P1",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    _require(
        "Control C changes no runtime source" in facade,
        "facade runtime boundary missing",
    )
    _require(
        "does not claim provider hard cancellation" in facade,
        "facade provider hard-cancel non-claim missing",
    )
    print("[OK] seven FW-RT6-7b tasks close as aggregate acceptance-candidates")


def check_runtime_and_deferred_scope() -> None:
    runtime_prefixes = (
        "framework/",
        "core/",
        "llm/",
        "providers/",
        "stt/",
        "tts/",
        "vts/",
    )
    runtime = {
        path for path in _changed_paths() if path.startswith(runtime_prefixes)
    }
    _require(not runtime, f"Control C changed runtime sources: {sorted(runtime)!r}")
    print("[OK] Control C introduces no runtime source or FW-RT6-7c/P1 change")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args()
    if not args.source_only:
        check_exact_surface()
    check_accepted_control_a_b()
    check_aggregate_contract()
    check_docs_and_task_closure()
    if not args.source_only:
        check_runtime_and_deferred_scope()
    print("v600_rt6_7b_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7b_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7b_control_c_status: implemented-awaiting-review")
    print("v600_rt6_7b_control_c_exact_surface: 3 files")
    print("v600_rt6_7b_runtime_changed_by_control_c: False")
    print("v600_rt6_7b_task_count: 7 / 7 ACCEPTED-CANDIDATE")
    print("v600_rt6_7b_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_7c_status: NOT_AUTHORIZED")
    print("v600_rt6_7b_partial_streaming: DEFERRED_TO_P1")
    print("v600_rt6_7b_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
