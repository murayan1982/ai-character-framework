import asyncio
import datetime
import re
from contextlib import suppress
from pathlib import Path

from config.settings import INPUT_VOICE_ENABLED, OUTPUT_VOICE_ENABLED
from live2d.vts_client import VTSClient
from llm.factory import create_llm
from llm.fallback_llm import FallbackLLM
from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from utils.security import SecurityManager

from llm.router_llm import RouterLLM
from config.settings import (
    CHAT_PRIMARY_LLM,
    CHAT_FALLBACK_LLM,
    CODE_PRIMARY_LLM,
    CODE_FALLBACK_LLM,
)

ANSI_CLEANER = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)


def create_log_file() -> Path:
    log_dir = Path("output")
    log_dir.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M")
    return log_dir / f"log_{timestamp}.txt"


def load_system_prompt() -> str:
    prompt_path = Path("prompts/system_base.txt")
    if not prompt_path.exists():
        raise FileNotFoundError("prompts/system_base.txt not found.")
    return prompt_path.read_text(encoding="utf-8")


def print_system_status(use_stt: bool, use_tts: bool, llm) -> None:
    input_mode = "Voice (STT)" if use_stt else "Keyboard (Text)"
    output_mode = "Voice (TTS)" if use_tts else "Text Only"

    print("\n--- System Active ---")
    print(f"Input Mode:  {input_mode}")
    print(f"Output Mode: {output_mode}")
    print(f"LLM:         {llm.provider_name} / {llm.model_name}")

def append_log(log_file: Path, timestamp: str, user_input: str, ai_text: str) -> None:
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] User: {user_input}\n")
        f.write(f"[{timestamp}] AI: {ai_text}\n\n")


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
    llm,
    user_input: str,
    vts: VTSClient,
    tts: VoiceEngine | None,
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
            if display_text:
                print(display_text, end="", flush=True)
                full_log_text += display_text
                if use_tts and tts is not None:
                    tts.speak(display_text)

    print()
    return full_log_text


async def initialize_components():
    SecurityManager.ensure_safe_environment()

    use_stt = INPUT_VOICE_ENABLED
    use_tts = OUTPUT_VOICE_ENABLED

    system_instruction = load_system_prompt()
    log_file = create_log_file()

    chat_primary = create_llm(
        provider=CHAT_PRIMARY_LLM["provider"],
        model=CHAT_PRIMARY_LLM["model"],
        system_instruction=system_instruction,
    )

    chat_fallback = create_llm(
        provider=CHAT_FALLBACK_LLM["provider"],
        model=CHAT_FALLBACK_LLM["model"],
        system_instruction=system_instruction,
    )

    code_primary = create_llm(
        provider=CODE_PRIMARY_LLM["provider"],
        model=CODE_PRIMARY_LLM["model"],
        system_instruction=system_instruction,
    )

    code_fallback = create_llm(
        provider=CODE_FALLBACK_LLM["provider"],
        model=CODE_FALLBACK_LLM["model"],
        system_instruction=system_instruction,
    )

    chat_llm = FallbackLLM(chat_primary, chat_fallback)
    code_llm = FallbackLLM(code_primary, code_fallback)

    llm = RouterLLM(chat_llm, code_llm)

    vts = VTSClient()
    stt = STTEngine() if use_stt else None
    tts = VoiceEngine() if use_tts else None

    await vts.connect()
    print_system_status(use_stt, use_tts, llm)

    return {
        "use_stt": use_stt,
        "use_tts": use_tts,
        "log_file": log_file,
        "llm": llm,
        "vts": vts,
        "stt": stt,
        "tts": tts,
    }


async def shutdown_components(vts: VTSClient) -> None:
    await vts.close()


async def main():
    runtime = None

    try:
        runtime = await initialize_components()

        use_stt = runtime["use_stt"]
        use_tts = runtime["use_tts"]
        log_file = runtime["log_file"]
        llm = runtime["llm"]
        vts = runtime["vts"]
        stt = runtime["stt"]
        tts = runtime["tts"]

        while True:
            try:
                user_input = await get_user_input(use_stt, stt)

                if not user_input:
                    continue

                if user_input.lower() in {"exit", "quit"}:
                    print("System shutting down...")
                    break

                start_ts = datetime.datetime.now().strftime("%H:%M:%S")

                full_log_text = await process_ai_response(
                    llm=llm,
                    user_input=user_input,
                    vts=vts,
                    tts=tts,
                    use_tts=use_tts,
                )

                if use_tts and tts is not None:
                    await wait_for_tts_playback(tts)

                append_log(log_file, start_ts, user_input, full_log_text)

            except KeyboardInterrupt:
                print("\nSystem shutting down...")
                break
            except Exception as e:
                print(f"\n[Main Error] {e}")
                await asyncio.sleep(1)

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"[Startup Error] {e}")
    finally:
        if runtime is not None:
            await shutdown_components(runtime["vts"])


if __name__ == "__main__":
    asyncio.run(main())