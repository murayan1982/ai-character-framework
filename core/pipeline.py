import asyncio
from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from core.events import emit
from core.streaming import StreamingState, consume_stream_chunk
import traceback


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
        print("[TTS Warning] playback wait timed out. Continuing session.")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"[TTS Warning] playback wait failed. Continuing session. ({e})")


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
        thinking_label = "  AI: ..."
        answer_prefix = "  AI: "

        print()
        print(thinking_label, flush=True)

        full_log_text = ""
        stream_state = StreamingState()
        emotion_triggered = False
        first_visible_chunk_received = False
        first_speech_sent = False

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

            chunk_result = consume_stream_chunk(stream_state, clean_chunk)

            if chunk_result.parsed_emotion is not None and not emotion_triggered:
                try:
                    await emit(runtime, "on_emotion_detected", chunk_result.parsed_emotion)
                except Exception as e:
                    print(f"[Emotion Plugin Error] {e}")
                emotion_triggered = True

            display_text = chunk_result.display_text
            speech_text = chunk_result.speech_text

            if display_text:
                if not first_visible_chunk_received:
                    print(answer_prefix, end="", flush=True)
                    first_visible_chunk_received = True

                print(display_text, end="", flush=True)
                full_log_text += display_text
                await emit(runtime, "on_llm_chunk", display_text)

            if speech_text and use_tts and tts is not None:
                if not first_speech_sent:
                    first_speech_sent = True
                tts.speak(speech_text)

        if not first_visible_chunk_received:
            print(answer_prefix, end="", flush=True)

        print()

        if use_tts and tts is not None:
            if first_speech_sent and tts.is_speaking_active:
                print("[TTS Playing...]")
            await wait_for_tts_playback(tts)

        await emit(runtime, "on_llm_complete", full_log_text)
        return full_log_text

    except Exception:
        print("\n[PROCESS_AI_RESPONSE ERROR]")
        traceback.print_exc()
        raise