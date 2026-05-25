from typing import Generator, Tuple, List
from llm.base import BaseLLM
from config import settings

class RouterLLM(BaseLLM):
    def __init__(self, chat_llm: BaseLLM, code_llm: BaseLLM):
        self.chat_llm = chat_llm
        self.code_llm = code_llm

    @property
    def provider_name(self) -> str:
        return "router"

    @property
    def model_name(self) -> str:
        return "chat/code"

    def reset_session(self) -> None:
        self.chat_llm.reset_session()
        self.code_llm.reset_session()

    def _select_llm(self, text: str) -> BaseLLM:
        lowered = text.lower()

        strong_hits = sum(
            1 for keyword in settings.STRONG_CODE_KEYWORDS if keyword in lowered
        )
        weak_hits = sum(
            1 for keyword in settings.WEAK_CODE_KEYWORDS if keyword in lowered
        )

        if strong_hits >= 1:
            return self.code_llm

        if weak_hits >= 2:
            return self.code_llm

        return self.chat_llm

    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        selected_llm = self._select_llm(text)

        if settings.DEBUG_ROUTER:
            route = "code" if selected_llm is self.code_llm else "chat"
            print(
                f"[Router] route={route} -> "
                f"{selected_llm.provider_name} / {selected_llm.model_name}"
            )

        yield from selected_llm.ask_stream(text)