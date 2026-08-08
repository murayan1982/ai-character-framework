"""FW-RT6-7c Control C aggregate voice-input result acceptance gate."""

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

EXPECTED_HEAD = "dfcdc137ba8d04bde09f62fe0ced04086886dbfe"
EXPECTED_SURFACE = {
    "docs/public_facade.md",
    "docs/v600_tasklist.md",
    "scripts/check_v600_voice_input_result_acceptance.py",
}
LEGACY_RESULT_FIELDS = (
    "outcome",
    "text",
    "language",
    "confidence",
    "duration_ms",
    "public_error_code",
    "safe_message",
    "retryable",
    "public_metadata",
)
CORRELATION_FIELDS = ("session_id", "turn_id", "generation_id")


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
    print("[OK] baseline and exact three-file FW-RT6-7c Control C surface conform")


def check_accepted_control_a_b() -> None:
    control_a = _load(
        "_fw_rt6_7c_control_a_for_aggregate",
        "scripts/smoke_v600_voice_input_result_control_a.py",
    )
    control_b = _load(
        "_fw_rt6_7c_control_b_for_aggregate",
        "scripts/smoke_v600_voice_input_result_control_b.py",
    )
    control_a.check_accepted_7b_regression()
    control_a.check_additive_result_contract()
    control_a.check_session_result_event_correlation()
    control_a.check_v5_compatibility_gates()
    control_a.check_focused_tests()
    control_b.check_result_and_callback_bridge()
    control_b.check_host_audio_and_public_surface()
    control_b.check_focused_tests()
    print("[OK] accepted Control A+B result/callback regressions conform")


def check_aggregate_contract() -> None:
    import framework
    from framework.version import VOICE_INPUT_API_VERSION

    result_fields = tuple(item.name for item in fields(framework.VoiceInputResult))
    _require(
        result_fields == LEGACY_RESULT_FIELDS + CORRELATION_FIELDS,
        "aggregate VoiceInputResult field contract drift",
    )
    legacy_result = framework.VoiceInputResult.completed("legacy")
    _require(
        legacy_result.session_id is None
        and legacy_result.turn_id is None
        and legacy_result.generation_id is None,
        "legacy factory call correlation drift",
    )

    session = framework.create_voice_input_session(language="ja-JP")
    canonical = []
    legacy = []
    session.on_realtime_event(canonical.append)
    session.on_event(legacy.append)
    listen = session.listen_result()
    fallback = session.text_fallback_result("aggregate fallback")

    for result in (listen, fallback):
        _require(result.session_id == session.session_id, "result session drift")
        _require(result.turn_id is not None, "result turn correlation missing")
        _require(result.generation_id is not None, "result generation missing")
    _require(listen.turn_id != fallback.turn_id, "operation turn identity reused")
    _require(
        [event["type"] for event in legacy]
        == [
            "voice_input.started",
            "voice_input.unavailable",
            "voice_input.text_fallback",
        ],
        "legacy mapping bridge drift",
    )
    _require(
        all(set(event) == {"type", "session_type", "payload"} for event in legacy),
        "legacy mapping shape drift",
    )

    session.close()
    canonical_after_close = len(canonical)
    legacy_after_close = len(legacy)
    source = framework.VoiceInputAudioSource.from_opaque_id(
        "aggregate_closed_audio",
        audio_format=framework.VoiceInputAudioFormat.wav(duration_ms=100),
    )
    closed_results = (
        session.listen_result(),
        session.text_fallback_result("ignored"),
        session.transcribe_audio_result(source),
    )
    _require(
        closed_results[0] == closed_results[1] == closed_results[2],
        "unified post-close rejection drift",
    )
    _require(
        all(
            result.outcome is framework.VoiceInputOutcome.CLOSED
            and result.session_id == session.session_id
            and result.turn_id is None
            and result.generation_id is None
            for result in closed_results
        ),
        "post-close session-only rejection drift",
    )
    _require(len(canonical) == canonical_after_close, "duplicate canonical close event")
    _require(len(legacy) == legacy_after_close, "duplicate legacy close event")
    _require(
        canonical[-1].type is framework.RealtimeEventType.SESSION_CLOSED,
        "canonical session close missing",
    )
    _require(legacy[-1]["type"] == "voice_input.closed", "legacy close mapping missing")
    _require(len(framework.__all__) == 127, "framework root-public count drift")
    _require(VOICE_INPUT_API_VERSION == "5.2.0", "voice-input API version drift")
    _require(
        session.info.api_version == VOICE_INPUT_API_VERSION,
        "session info version connection drift",
    )
    print("[OK] aggregate result, callback, close, version, and public surface conform")


def check_docs_and_task_closure() -> None:
    tasklist = (PROJECT_ROOT / "docs/v600_tasklist.md").read_text(encoding="utf-8")
    facade = (PROJECT_ROOT / "docs/public_facade.md").read_text(encoding="utf-8")
    start = tasklist.index("## FW-RT6-7c — Voice input result compatibility")
    end = tasklist.index("\n---\n", start)
    section = tasklist[start:end]
    _require(
        section.count("- [x]") == 5 and section.count("- [ ]") == 0,
        "FW-RT6-7c must be 5 / 5 accepted-candidate",
    )
    for text in (tasklist, facade):
        _require(
            "FW-RT6-7c-C-AGGREGATE-ACCEPTANCE:BEGIN" in text,
            "Control C aggregate marker missing",
        )
    for marker in (
        "FW-RT6-7c tasks: 5 / 5 ACCEPTED-CANDIDATE",
        "runtime source changed by Control C: False",
        "FW-RT6-7c final acceptance sync: NOT_AUTHORIZED",
        "FW-RT6-8a motion correlation: NOT_AUTHORIZED",
        "partial transcript/audio streaming: DEFERRED_TO_P1",
        "commit / push: NOT_AUTHORIZED",
    ):
        _require(marker in tasklist, f"tasklist aggregate marker missing: {marker}")
    _require(
        "Control C changes no runtime source" in facade,
        "facade runtime boundary missing",
    )
    _require(
        "Host-audio transcription remains" in facade,
        "facade host-audio compatibility boundary missing",
    )
    print("[OK] five FW-RT6-7c tasks close as aggregate acceptance-candidates")


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
    print("[OK] Control C introduces no runtime source or FW-RT6-8/P1 change")


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
    print("v600_rt6_7c_control_a_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7c_control_b_status: COMPLETED / VERIFIED / ACCEPTED / CLOSED")
    print("v600_rt6_7c_control_c_status: implemented-awaiting-review")
    print("v600_rt6_7c_control_c_exact_surface: 3 files")
    print("v600_rt6_7c_runtime_changed_by_control_c: False")
    print("v600_rt6_7c_task_count: 5 / 5 ACCEPTED-CANDIDATE")
    print("v600_rt6_7c_final_acceptance_sync: NOT_AUTHORIZED")
    print("v600_rt6_8a_status: NOT_AUTHORIZED")
    print("v600_rt6_7c_partial_streaming: DEFERRED_TO_P1")
    print("v600_rt6_7c_commit_push: NOT_AUTHORIZED")


if __name__ == "__main__":
    main()
