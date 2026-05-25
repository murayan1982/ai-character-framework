from __future__ import annotations

from typing import Any


EMOTION_TAG_INSTRUCTION = """At the beginning of every assistant response, output exactly one emotion tag:
[emotion:neutral], [emotion:happy], [emotion:sad], [emotion:angry], [emotion:surprised], or [emotion:confused].
After the tag, write the normal response text.
Do not output multiple emotion tags."""

VOICE_OUTPUT_POLICY = """\
Voice output is enabled.
Write responses in natural spoken language that is easy for text-to-speech engines to read aloud.
Prefer short, clear sentences with natural punctuation.
Avoid dense Markdown, tables, excessive symbols, emoji, and decorative formatting unless the user explicitly asks for them.
Keep code, commands, file paths, URLs, environment variable names, and proper nouns unchanged.
Do not change the required output language.
Do not override the character's personality or role.
"""

LANGUAGE_NAMES = {
    "ja": "Japanese",
    "en": "English",
}


def should_apply_voice_output_policy(config: Any) -> bool:
    """Return whether voice-friendly output policy should be added."""
    output_voice_enabled = bool(getattr(config, "output_voice_enabled", False))
    tts_provider = str(getattr(config, "tts_provider", "none") or "none").lower()
    return output_voice_enabled and tts_provider != "none"


def build_final_system_instruction(config: Any) -> str:
    """Build the final system instruction from runtime prompt layers.

    Prompt layers stay separate by responsibility:
    - output language instruction
    - optional voice-friendly output policy
    - optional emotion tag instruction
    - character system prompt
    """
    parts: list[str] = []

    output_language_code = str(
        getattr(config, "output_language_code", "") or ""
    ).strip()
    if output_language_code:
        parts.append(build_language_instruction(output_language_code))

    if should_apply_voice_output_policy(config):
        parts.append(VOICE_OUTPUT_POLICY.strip())

    if bool(getattr(config, "emotion_enabled", False)):
        parts.append(EMOTION_TAG_INSTRUCTION.strip())

    character_system_prompt = str(
        getattr(config, "system_prompt", "") or ""
    ).strip()
    if character_system_prompt:
        parts.append(character_system_prompt)

    return "\n\n".join(parts).strip()


def build_language_instruction(output_language_code: str) -> str:
    """Build language-control instruction for the configured output language."""
    normalized = str(output_language_code).strip().lower()
    output_language_name = LANGUAGE_NAMES.get(normalized)

    if output_language_name is None:
        return (
            "You MUST write your entire response in the configured output language: "
            f"{normalized}. Keep only code, commands, file paths, URLs, "
            "and proper nouns unchanged."
        )

    return (
        f"You MUST write your entire response in {output_language_name}. "
        f"All explanations, headings, bullet points, and sentences must be in "
        f"{output_language_name}. "
        f"You are NOT allowed to output any other language. "
        f"If you generate content in another language, you must immediately rewrite it in "
        f"{output_language_name}. "
        f"Keep only code, commands, file paths, URLs, and proper nouns unchanged."
    )
