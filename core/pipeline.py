import asyncio
import re
from contextlib import suppress
from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from core.events import emit
from core.emotion import parse_emotion_response, resolve_emotion_hotkey

ANSI_CLEANER = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)

async def get_user_input(use_stt: bool, stt: STTEngine | None) -> str:

    if not use_stt or stt is None:
        return (await ainput("\nUser: ")).strip()

    stt_task = asyncio.create_task(stt.listen())
    kb_task = asyncio.create_task(ainput("\n[Keyboard or Speak]: "))

    try:
        while True:
            done, _ = await asyncio.wait(
                [stt_task, kb_task],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if kb_task in done:
                result = kb_task.result()
                return str(result).strip() if result else ""

            if stt_task in done:
                result = stt_task.result()
                user_input = str(result).strip() if result else ""

                if user_input:
                    return user_input

                # v1.4 fallback:
                # If STT returns empty first, do not return empty input.
                # Keep waiting for keyboard input.
                if not kb_task.done():
                    result = await kb_task
                    return str(result).strip() if result else ""

                result = kb_task.result()
                return str(result).strip() if result else ""

    finally:
        if not stt_task.done():
            stt_task.cancel()

        if not kb_task.done():
            kb_task.cancel()

async def wait_for_tts_playback(tts: VoiceEngine) -> None:
    tts.flush()
    while tts.is_speaking_active:
        await asyncio.sleep(0.1)

async def process_ai_response(
    *,
    runtime: dict,
    llm,
    user_input: str,
    vts,
    tts,
    use_tts: bool,
) -> str:
    print("\n  AI: ", end="", flush=True)

    full_log_text = ""
    pending_prefix = ""
    emotion_parsed = False
    emotion_triggered = False

    for clean_chunk, emotions in llm.ask_stream(user_input):
        if emotions:
            full_log_text += "".join(f"[{emotion}]" for emotion in emotions)
            # v1.4: automatic VTS expression control is not supported.
            # v1.5 will handle emotion tags via plugin-based expression control.

        if not clean_chunk:
            continue

        chunk_text = ANSI_CLEANER.sub("", clean_chunk)

        if not emotion_parsed:
            pending_prefix += chunk_text
            parsed = parse_emotion_response(pending_prefix)

            # まだタグだけで本文が来ていない可能性があるので、
            # 本文が見えるまで少し待つ
            if parsed.clean_text == "" and "[emotion:" in pending_prefix:
                continue

            display_text = parsed.clean_text
            emotion_parsed = True
            if (
                not emotion_triggered
                and runtime.get("config") is not None
                and runtime["config"].emotion_enabled
                and runtime["config"].vts_emotion_enabled
                and vts is not None
            ):
                hotkey_name = resolve_emotion_hotkey(
                    parsed.emotion,
                    runtime["config"].vts_hotkeys,
                )
                if hotkey_name:
                    await vts.trigger_hotkey(hotkey_name)

                emotion_triggered = True
        else:
            display_text = chunk_text

        if display_text:
            print(display_text, end="", flush=True)
            full_log_text += display_text
            await emit(runtime, "on_llm_chunk", display_text)

            if use_tts and tts is not None:
                tts.speak(display_text)

    print()

    if use_tts and tts is not None:
        await wait_for_tts_playback(tts)

    await emit(runtime, "on_llm_complete", full_log_text)
    return full_log_text