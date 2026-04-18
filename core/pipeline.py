import asyncio
import re
from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from core.events import emit
from core.emotion import parse_emotion_response
import traceback

ANSI_CLEANER = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)

async def get_user_input(use_stt: bool, stt: STTEngine | None) -> str:
    if not use_stt or stt is None:
        return (await ainput("\nUser: ")).strip()

    print("[STT Waiting...]")
    result = await stt.listen()
    return str(result).strip() if result else ""

async def wait_for_tts_playback(tts_engine: VoiceEngine, timeout: float = 15.0) -> None:
    try:
        tts_engine.flush()

        async def _wait_loop():
            while tts_engine.is_speaking_active:
                await asyncio.sleep(0.1)

        await asyncio.wait_for(_wait_loop(), timeout=timeout)

    except asyncio.TimeoutError:
        print("[TTS Wait Warning] playback wait timed out")
    except Exception as e:
        print(f"[TTS Wait Error] {e}")

async def process_ai_response(
    *,
    runtime: dict,
    llm,
    user_input: str,
    vts,
    tts,
    use_tts: bool,
) -> str:
    try:
        print("\n  AI: ", end="", flush=True)

        full_log_text = ""
        pending_prefix = ""
        emotion_parsed = False
        emotion_triggered = False

        for clean_chunk, emotions in llm.ask_stream(user_input):

            if emotions:
                full_log_text += "".join(f"[{emotion}]" for emotion in emotions)

            if not clean_chunk and not emotions:
                continue

            if emotions and not emotion_triggered:
                try:
                    emotion = str(emotions[0]).strip().lower()
                    await emit(runtime, "on_emotion_detected", emotion)
                except Exception as e:
                    print(f"[Emotion Plugin Error] {e}")
                emotion_triggered = True

            chunk_text = ANSI_CLEANER.sub("", clean_chunk or "")

            if not emotion_parsed:
                pending_prefix += chunk_text
                parsed = parse_emotion_response(pending_prefix)

                if parsed.clean_text == "" and "[emotion:" in pending_prefix:
                    continue

                display_text = parsed.clean_text
                emotion_parsed = True
                pending_prefix = ""

                if not emotion_triggered:
                    try:
                        await emit(runtime, "on_emotion_detected", parsed.emotion)
                    except Exception as e:
                        print(f"[Emotion Plugin Error] {e}")
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

    except Exception:
        print("\n[PROCESS_AI_RESPONSE ERROR]")
        traceback.print_exc()
        raise