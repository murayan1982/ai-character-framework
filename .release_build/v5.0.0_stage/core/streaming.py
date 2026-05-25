from __future__ import annotations

import re
from dataclasses import dataclass

from core.emotion import parse_emotion_response


ANSI_CLEANER = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


@dataclass
class StreamingState:
    pending_prefix: str = ""
    emotion_parsed: bool = False


@dataclass
class StreamingChunkResult:
    display_text: str
    speech_text: str
    parsed_emotion: str | None
    should_wait_for_more: bool = False


def consume_stream_chunk(
    state: StreamingState,
    raw_chunk: str | None,
) -> StreamingChunkResult:
    """
    Normalize one streamed LLM chunk for downstream UX handling.

    Responsibilities:
    - remove ANSI escape sequences
    - hold incomplete leading emotion tag until it becomes parseable
    - return display/speech text separately for future UX expansion
    """
    chunk_text = ANSI_CLEANER.sub("", raw_chunk or "")

    if state.emotion_parsed:
        return StreamingChunkResult(
            display_text=chunk_text,
            speech_text=chunk_text,
            parsed_emotion=None,
            should_wait_for_more=False,
        )

    state.pending_prefix += chunk_text
    parsed = parse_emotion_response(state.pending_prefix)

    if parsed.clean_text == "" and "[emotion:" in state.pending_prefix:
        return StreamingChunkResult(
            display_text="",
            speech_text="",
            parsed_emotion=None,
            should_wait_for_more=True,
        )

    state.emotion_parsed = True
    state.pending_prefix = ""

    return StreamingChunkResult(
        display_text=parsed.clean_text,
        speech_text=parsed.clean_text,
        parsed_emotion=parsed.emotion,
        should_wait_for_more=False,
    )