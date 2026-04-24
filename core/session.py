import asyncio
import datetime

from core.pipeline import process_ai_response, get_user_input
from core.utils.logging import append_log
from core.events import emit


class ChatSession:
    """Run the top-level conversation loop for one runtime session.

    The session owns the repeated user-input cycle:
    user input -> runtime events -> AI response processing -> logging.
    Lower-level response handling such as streaming display, TTS, emotion
    parsing, and VTS expression triggers stays in core.pipeline and plugins.
    """

    def __init__(self, runtime: dict):
        self.runtime = runtime

    async def run(self):
        """Start the interactive conversation loop until exit or interruption."""
        use_stt = self.runtime["use_stt"]
        use_tts = self.runtime["use_tts"]
        log_file = self.runtime["log_file"]
        llm = self.runtime["llm"]
        vts = self.runtime["vts"]
        stt = self.runtime["stt"]
        tts = self.runtime["tts"]
        config = self.runtime.get("config")
        allow_text_fallback_during_stt = bool(
            getattr(config, "allow_text_fallback_during_stt", False)
        )

        while True:
            try:
                # waiting / listening: collect keyboard or STT input for one turn.
                user_input = await get_user_input(
                    use_stt,
                    stt,
                    allow_text_fallback_during_stt=allow_text_fallback_during_stt,
                )

                if not user_input:
                    continue

                # Runtime event: on_user_input
                await emit(self.runtime, "on_user_input", user_input)

                if user_input.lower() in {"exit", "quit"}:
                    print("[Exiting] System shutting down...")
                    break

                start_ts = datetime.datetime.now().strftime("%H:%M:%S")

                # thinking / speaking: stream the LLM response and optional voice/VTS side effects.
                full_log_text = await process_ai_response(
                    runtime=self.runtime,
                    llm=llm,
                    user_input=user_input,
                    vts=vts,
                    tts=tts,
                    use_tts=use_tts,
                )

                append_log(log_file, start_ts, user_input, full_log_text)

            except KeyboardInterrupt:
                print("\n[Exiting] Keyboard interrupt received.")
                break

            except Exception as e:
                # Runtime event: on_error
                await emit(self.runtime, "on_error", e)
                print(f"\n[Main Error] {e}")
                await asyncio.sleep(1)
