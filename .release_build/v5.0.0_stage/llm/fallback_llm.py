from typing import Generator, Tuple, List
from llm.base import BaseLLM
from config.defaults import DEBUG, DEBUG_FALLBACK

class FallbackLLM(BaseLLM):
    def __init__(self, primary: BaseLLM, fallback: BaseLLM):
        self.primary = primary
        self.fallback = fallback

    @property
    def provider_name(self) -> str:
        return f"{self.primary.provider_name}->{self.fallback.provider_name}"

    @property
    def model_name(self) -> str:
        return f"{self.primary.model_name}->{self.fallback.model_name}"

    def reset_session(self) -> None:
        self.primary.reset_session()
        self.fallback.reset_session()

    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        try:
            yield from self.primary.ask_stream(text)
        except Exception as e:
            if DEBUG and DEBUG_FALLBACK:
                print(f"\n[Fallback triggered] {self.primary.provider_name} -> {self.fallback.provider_name}")
                print(f"[Fallback reason] {e}")
            yield from self.fallback.ask_stream(text)