from google import genai
import re
from typing import Generator, Tuple, List
from llm.base import BaseLLM
from config.calibration import MAX_TOKENS_NORMAL, LLM_TEMPERATURE
from config.secrets import GOOGLE_API_KEY

class GeminiEngine(BaseLLM):
    def __init__(self, system_instruction: str, model: str):
        if not GOOGLE_API_KEY:
            raise EnvironmentError("GOOGLE_API_KEY is not defined.")

        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model_id = model
        self.turn_count = 0
        self.current_mood = "Normal"
        self.base_instruction = system_instruction

        self._start_new_session()
    
    @property
    def provider_name(self) -> str:
        return "google"

    @property
    def model_name(self) -> str:
        return self.model_id

    def reset_session(self) -> None:
        self.turn_count = 0
        self.current_mood = "Normal"
        self._start_new_session()

    def _start_new_session(self) -> None:
        self.chat = self.client.chats.create(
            model=self.model_id,
            config={
                "system_instruction": self.base_instruction,
                "temperature": LLM_TEMPERATURE,
                "max_output_tokens": MAX_TOKENS_NORMAL,
            },
        )

    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        self.turn_count += 1

        if self.turn_count > 10:
            self._refresh_session_with_mood()
            self.turn_count = 1

        final_input = text
        if self.turn_count == 1 and self.current_mood != "Normal":
            final_input = (
                f"(Context: Current relationship/mood is '{self.current_mood}')\n{text}"
            )

        try:
            response = self.chat.send_message_stream(final_input)
            tag_pattern = re.compile(r"\[([a-zA-Z0-9_]+)\]")
            buffer = ""

            for chunk in response:
                if not chunk.text:
                    continue

                buffer += chunk.text

                if "[" in buffer:
                    if "]" in buffer:
                        emotions = tag_pattern.findall(buffer)
                        clean_text = tag_pattern.sub("", buffer)
                        yield clean_text, emotions
                        buffer = ""
                    elif len(buffer) > 100:
                        yield buffer, []
                        buffer = ""
                else:
                    yield buffer, []
                    buffer = ""

            if buffer:
                emotions = tag_pattern.findall(buffer)
                clean_text = tag_pattern.sub("", buffer)
                yield clean_text, emotions

        except Exception as e:
            raise RuntimeError(f"{self.provider_name} failed: {e}") from e

    def _refresh_session_with_mood(self) -> None:
        try:
            mood_prompt = (
                "Summarize the current relationship atmosphere with the user "
                "in one short English sentence. "
                "Example: 'Casual and friendly' or 'Technical and focused'."
            )
            mood_res = self.chat.send_message(mood_prompt)
            self.current_mood = mood_res.text.strip()
        except Exception:
            self.current_mood = "Normal"

        self._start_new_session()