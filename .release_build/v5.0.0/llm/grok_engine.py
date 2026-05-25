from openai import OpenAI
import re
from typing import Generator, Tuple, List
from llm.base import BaseLLM
from config.calibration import MAX_TOKENS_NORMAL, LLM_TEMPERATURE
from config.secrets import XAI_API_KEY

class GrokEngine(BaseLLM):
    def __init__(self, system_instruction: str, model: str):
        if not XAI_API_KEY:
            raise EnvironmentError("XAI_API_KEY is not defined.")

        self.client = OpenAI(
            api_key=XAI_API_KEY,
            base_url="https://api.x.ai/v1",
        )
        self.model_id = model
        self.base_instruction = system_instruction
        self.history = [
            {"role": "system", "content": self.base_instruction}
        ]
    
    @property
    def provider_name(self) -> str:
        return "xai"

    @property
    def model_name(self) -> str:
        return self.model_id

    def reset_session(self) -> None:
        self.history = [
            {"role": "system", "content": self.base_instruction}
        ]

    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        self.history.append({"role": "user", "content": text})

        try:
            stream = self.client.chat.completions.create(
                model=self.model_id,
                messages=self.history,
                temperature=LLM_TEMPERATURE,
                max_tokens=MAX_TOKENS_NORMAL,
                stream=True,
            )

            tag_pattern = re.compile(r"\[([a-zA-Z0-9_]+)\]")
            full_response = ""
            buffer = ""

            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if not delta:
                    continue

                full_response += delta
                buffer += delta

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

            self.history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            raise RuntimeError(f"{self.provider_name} failed: {e}") from e