from abc import ABC, abstractmethod
from typing import Generator, List, Tuple


class BaseLLM(ABC):
    """
    Common interface for LLM providers.

    Provider implementations are responsible for:
    - creating and owning their provider-specific client
    - managing provider-specific conversation state
    - converting streamed provider responses into a common output shape

    The common streaming output is:

        tuple[str, list[str]]

    where:
    - str is the next text chunk to display or speak
    - list[str] is a list of emotion tags detected in that chunk

    Provider implementations should raise provider-specific runtime failures
    as RuntimeError with enough context for fallback/debug logs.
    """

    @abstractmethod
    def ask_stream(self, text: str) -> Generator[Tuple[str, List[str]], None, None]:
        """
        Send user text to the provider and stream response chunks.

        Each yielded item must be a tuple of:

            (text_chunk, emotion_tags)

        Implementations may keep conversation history internally.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Stable provider identifier used for logs, routing, and diagnostics.

        Examples:
        - google
        - xai
        - openai
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Provider model identifier used for logs, routing, and diagnostics.
        """
        raise NotImplementedError

    def reset_session(self) -> None:
        """
        Reset provider-owned conversation state.

        Stateless providers may keep the default no-op implementation.
        """
        return None