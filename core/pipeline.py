import asyncio
import re
from contextlib import suppress

from live2d.vts_client import VTSClient
from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from core.events import emit

ANSI_CLEANER = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)

def handle_background_task_result(task: asyncio.Task) -> None:
    with suppress(asyncio.CancelledError):
        exc = task.exception()
        if exc is not None:
            print(f"[Async Error] {exc}")


def schedule_expression_change(vts: VTSClient, emotion: str) -> None:
    task = asyncio.create_task(vts.change_expression(emotion))
    task.add_done_callback(handle_background_task_result)


async def get_user_input(use_stt: bool, stt: STTEngine | None) -> str:
    if not use_stt or stt is None:
        return (await ainput("\nUser: ")).strip()

    stt_task = asyncio.create_task(stt.listen())
    kb_task = asyncio.create_task(ainput("\n[Keyboard or Speak]: "))

    done, pending = await asyncio.wait(
        [stt_task, kb_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    user_input = ""
    for task in done:
        result = task.result()
        if result:
            user_input = str(result).strip()
            break

    for task in pending:
        task.cancel()

    for task in pending:
        with suppress(asyncio.CancelledError):
            await task

    return user_input


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

    for clean_chunk, emotions in llm.ask_stream(user_input):
        if emotions:
            full_log_text += "".join(f"[{emotion}]" for emotion in emotions)
            for emotion in emotions:
                schedule_expression_change(vts, emotion)

        if clean_chunk:
            display_text = ANSI_CLEANER.sub("", clean_chunk)
            display_text = re.sub(r"\[[a-zA-Z0-9_]+\]", "", display_text)
            if display_text:
                print(display_text, end="", flush=True)
                full_log_text += display_text
                await emit(runtime, "on_llm_chunk", display_text)

                if use_tts and tts is not None:
                    tts.speak(display_text)

    print()
    await emit(runtime, "on_llm_complete", full_log_text)
    return full_log_text