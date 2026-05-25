import asyncio
import traceback

from stt.stt_engine import STTEngine
from tts.voice_engine import VoiceEngine
from core.events import emit
from core.streaming import StreamingState, consume_stream_chunk
from core.state import (
    ConversationState,
    is_interruption_requested,
    set_runtime_state,
)


async def ainput(prompt: str = "") -> str:
    return await asyncio.to_thread(input, prompt)


async def get_user_input(
    use_stt: bool,
    stt: STTEngine | None,
    *,
    allow_text_fallback_during_stt: bool = False,
) -> str:
    """
    Collect one user input turn from the active input path.

    Responsibility:
    - Use keyboard input when STT is disabled or unavailable.
    - Use voice input when STT is enabled and available.
    - Optionally fall back to keyboard input after STT timeout/failure.
    - Return the collected text to the session loop.

    This helper does not own conversation state transitions.
    Future state handling should be layered above or around this boundary.
    """
    # Keyboard input path.
    if not use_stt or stt is None:
        return (await ainput("\n[Waiting] User: ")).strip()

    # Voice input path.
    print("[Listening] Waiting for voice input...")
    result = await stt.listen()

    # Optional text fallback after STT failure or timeout.
    voice_text = str(result).strip() if result else ""
    if voice_text:
        return voice_text

    if allow_text_fallback_during_stt:
        fallback = await ainput(
            "[Waiting] Text fallback (Enter=retry / 'exit'=quit): "
        )
        return fallback.strip()

    return ""


async def wait_for_tts_playback(
    tts_engine: VoiceEngine,
    timeout: float = 15.0,
    *,
    runtime: dict | None = None,
) -> None:
    """Wait for queued TTS playback without blocking the session forever."""
    try:
        tts_engine.flush()

        async def _wait_loop():
            while tts_engine.is_speaking_active:
                if runtime is not None and is_interruption_requested(runtime):
                    _stop_tts_playback(tts_engine)
                    break
                await asyncio.sleep(0.1)

        await asyncio.wait_for(_wait_loop(), timeout=timeout)

    except asyncio.TimeoutError:
        print("[TTS Warning] playback wait timed out. Continuing session.")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"[TTS Warning] playback wait failed. Continuing session. ({e})")


async def _emit_emotion_once(
    runtime: dict,
    emotion: str | None,
    *,
    emotion_triggered: bool,
) -> bool:
    """Emit the first detected emotion once per assistant turn."""
    if emotion_triggered or emotion is None:
        return emotion_triggered

    normalized_emotion = str(emotion).strip().lower()
    if not normalized_emotion:
        return emotion_triggered

    try:
        await emit(runtime, "on_emotion_detected", normalized_emotion)
    except Exception as e:
        print(f"[Emotion Plugin Error] {e}")

    return True


async def _print_and_emit_display_chunk(
    runtime: dict,
    display_text: str,
    *,
    answer_prefix: str,
    first_visible_chunk_received: bool,
) -> bool:
    """Print one clean display chunk and emit the LLM chunk event."""
    if not display_text:
        return first_visible_chunk_received

    if not first_visible_chunk_received:
        print(answer_prefix, end="", flush=True)
        first_visible_chunk_received = True

    print(display_text, end="", flush=True)
    await emit(runtime, "on_llm_chunk", display_text)
    return first_visible_chunk_received


def _queue_tts_chunk(
    speech_text: str,
    *,
    use_tts: bool,
    tts: VoiceEngine | None,
) -> bool:
    """Queue one clean speech chunk for TTS playback when enabled."""
    if not speech_text or not use_tts or tts is None:
        return False

    tts.speak(speech_text)
    return True


def _stop_tts_playback(tts: VoiceEngine | None) -> None:
    """Best-effort stop for active or queued TTS playback during interruption."""
    if tts is None:
        return

    stop_fn = getattr(tts, "stop", None)
    if stop_fn is None:
        return

    try:
        stop_fn()
    except Exception as e:
        print(f"[TTS Warning] stop request failed. Continuing session. ({e})")


async def process_ai_response(
    *,
    runtime: dict,
    llm,
    user_input: str,
    vts,
    tts,
    use_tts: bool,
) -> str:
    """Process one assistant turn from LLM stream to display, TTS, and events.

    Responsibility:
    - Consume the LLM stream one chunk at a time.
    - Parse streaming chunks into display text, speech text, and emotion tags.
    - Print clean visible text for the user.
    - Queue clean speech text for optional TTS playback.
    - Check interruption boundaries during LLM streaming and TTS playback waits.
    - Emit runtime events for plugins.

    This helper does not own provider selection or final idle transitions.
    Those responsibilities are handled by surrounding runtime/session layers.
    """
    try:
        answer_prefix = "  AI: "
        await set_runtime_state(runtime, ConversationState.THINKING)
        print("[Thinking] Generating response...")

        full_log_text = ""
        stream_state = StreamingState()
        emotion_triggered = False
        first_visible_chunk_received = False
        response_started = False
        tts_output_queued = False
        interrupted = False

        # Thinking: consume the LLM stream one chunk at a time.
        for clean_chunk, emotions in llm.ask_stream(user_input):
            if is_interruption_requested(runtime):
                interrupted = True
                _stop_tts_playback(tts)
                await set_runtime_state(runtime, ConversationState.INTERRUPTED)
                break

            if emotions:
                full_log_text += "".join(f"[{emotion}]" for emotion in emotions)

            if not clean_chunk and not emotions:
                continue

            if emotions:
                emotion_triggered = await _emit_emotion_once(
                    runtime,
                    emotions[0],
                    emotion_triggered=emotion_triggered,
                )

            chunk_result = consume_stream_chunk(stream_state, clean_chunk)

            if chunk_result.should_wait_for_more:
                continue

            emotion_triggered = await _emit_emotion_once(
                runtime,
                chunk_result.parsed_emotion,
                emotion_triggered=emotion_triggered,
            )

            display_text = chunk_result.display_text
            speech_text = chunk_result.speech_text

            if display_text and not response_started:
                await set_runtime_state(runtime, ConversationState.RESPONDING)
                response_started = True

            # Display: show only clean text, not leading emotion tags.
            first_visible_chunk_received = await _print_and_emit_display_chunk(
                runtime,
                display_text,
                answer_prefix=answer_prefix,
                first_visible_chunk_received=first_visible_chunk_received,
            )

            if display_text:
                full_log_text += display_text

            if speech_text and is_interruption_requested(runtime):
                interrupted = True
                _stop_tts_playback(tts)
                await set_runtime_state(runtime, ConversationState.INTERRUPTED)
                break

            # Speaking: send the same clean text to TTS when enabled.
            if _queue_tts_chunk(speech_text, use_tts=use_tts, tts=tts):
                tts_output_queued = True

        if not interrupted and not first_visible_chunk_received:
            await set_runtime_state(runtime, ConversationState.RESPONDING)
            print(answer_prefix, end="", flush=True)

        print()

        if use_tts and tts is not None and not interrupted:
            if is_interruption_requested(runtime):
                interrupted = True
                _stop_tts_playback(tts)
                await set_runtime_state(runtime, ConversationState.INTERRUPTED)
            else:
                if tts_output_queued and tts.is_speaking_active:
                    await set_runtime_state(runtime, ConversationState.SPEAKING)
                    print("[Speaking] Playing TTS output...")
                await wait_for_tts_playback(tts, runtime=runtime)

        await emit(runtime, "on_llm_complete", full_log_text)
        return full_log_text

    except Exception:
        print("\n[PROCESS_AI_RESPONSE ERROR]")
        traceback.print_exc()
        raise
