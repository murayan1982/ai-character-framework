# Voice Output Policy

This document describes the planned voice-friendly output policy for TTS-enabled sessions.

The voice output policy is not character personality.

It is a runtime output-quality layer that helps LLM responses work better with text-to-speech playback.

## Responsibility

The framework currently builds the final system instruction from multiple concerns:

1. Output language instruction
2. Character instruction
3. Optional runtime output policy

These concerns should stay separate.

## Output Language Instruction

The output language instruction controls which language the assistant must use.

Example:

```text
You MUST write your entire response in Japanese.
```

This instruction should remain the strongest language rule.

The voice output policy must not override `output_language_code`.

## Character Instruction

Character files define who the character is.

Examples:

- personality
- tone
- role
- background
- conversation style
- character-specific behavior

Character prompts should not need to know whether TTS is enabled.

## Voice Output Policy

The voice output policy defines how responses should be shaped when voice output is enabled.

It should help TTS engines read responses more naturally.

Recommended behavior:

- Prefer natural spoken sentences.
- Prefer short and clear sentence boundaries.
- Avoid dense Markdown.
- Avoid tables unless explicitly requested.
- Avoid excessive symbols, emoji, and decorative formatting.
- Avoid uncommon abbreviations when a spoken form is clearer.
- Keep code, commands, file paths, URLs, environment variable names, and proper nouns unchanged.
- Do not change the requested output language.
- Do not override character personality.

## When It Should Apply

The policy should apply only when voice/TTS output is active.

Recommended initial condition:

```text
output_voice_enabled == True
tts_provider != "none"
```

Text-only sessions should not use the voice output policy by default.

## Initial Policy Text

A future implementation may append a policy like this to the final system instruction when TTS output is enabled:

```text
Voice output is enabled.
Write responses in natural spoken language that is easy for text-to-speech engines to read aloud.
Prefer short, clear sentences with natural punctuation.
Avoid dense Markdown, tables, excessive symbols, emoji, and decorative formatting unless the user explicitly asks for them.
Keep code, commands, file paths, URLs, environment variable names, and proper nouns unchanged.
Do not change the required output language.
Do not override the character's personality or role.
```

## Japanese TTS Notes

For Japanese voice output, the policy should encourage readable Japanese without over-constraining the character.

Useful guidance:

- Prefer natural Japanese punctuation.
- Avoid symbol-heavy expressions.
- Avoid excessive English abbreviations when Japanese wording is clearer.
- Keep proper nouns and technical identifiers unchanged.
- Keep code and commands unchanged.

## Out of Scope

This policy does not implement:

- TTS provider-specific pronunciation dictionaries
- forced furigana
- SSML
- per-provider phoneme controls
- automatic text normalization
- audio playback behavior
- character personality changes

Those may be future provider or voice pipeline features.

## Design Direction

The policy should eventually be implemented as a small prompt-building layer.

Preferred direction:

```text
final_system_instruction =
  language_instruction
  + optional_voice_output_policy
  + character_system_prompt
```

The exact ordering should be reviewed during implementation.

Language rules should remain strongest.
Character behavior should remain character-owned.
Voice readability should remain runtime-owned.