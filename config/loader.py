from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class RuntimeConfig:
    app_preset: str
    input_language_code: str
    output_language_code: str


def load_runtime_config() -> RuntimeConfig:
    load_dotenv()

    return RuntimeConfig(
        app_preset=os.getenv("APP_PRESET", "text_chat"),
        input_language_code=os.getenv("INPUT_LANGUAGE_CODE", "ja"),
        output_language_code=os.getenv("OUTPUT_LANGUAGE_CODE", "ja"),
    )