from typing import Generator, Tuple, List
from llm.base import BaseLLM


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

        code_keywords = [
            "code", "python", "javascript", "typescript", "bug", "debug",
            "error", "traceback", "exception", "function", "class",
            "コード", "実装", "バグ", "デバッグ", "例外", "関数", "クラス",
        ]

        if any(keyword in lowered for keyword in code_keywords):
            return self.code_llm

        return self.chat_llm

    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        selected_llm = self._select_llm(text)
        print(f"\n[Router] selected: {selected_llm.provider_name} / {selected_llm.model_name}")
        yield from selected_llm.ask_stream(text)