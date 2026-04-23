import asyncio
import datetime

from core.pipeline import process_ai_response, get_user_input
from core.utils.logging import append_log
from core.events import emit


class ChatSession:
    def __init__(self, runtime: dict):
        self.runtime = runtime

    async def run(self):
        use_stt = self.runtime["use_stt"]
        use_tts = self.runtime["use_tts"]
        log_file = self.runtime["log_file"]
        llm = self.runtime["llm"]
        vts = self.runtime["vts"]
        stt = self.runtime["stt"]
        tts = self.runtime["tts"]

        while True:
            try:
                user_input = await get_user_input(use_stt, stt)

                if not user_input:
                    continue

                # Runtime event: on_user_input
                await emit(self.runtime, "on_user_input", user_input)

                if user_input.lower() in {"exit", "quit"}:
                    print("System shutting down...")
                    break

                start_ts = datetime.datetime.now().strftime("%H:%M:%S")

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
                #print("\nSystem shutting down...")
                break

            except Exception as e:
                # Runtime event: on_error
                await emit(self.runtime, "on_error", e)
                print(f"\n[Main Error] {e}")
                await asyncio.sleep(1)