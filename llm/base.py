from abc import ABC, abstractmethod
from typing import Generator, Tuple, List

class BaseLLM(ABC):
    @abstractmethod
    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        """テキストを入力してストリームで応答を返す"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    def reset_session(self):
        """必要ならoverride"""
        pass