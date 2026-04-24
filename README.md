# AI Character Conversation Framework

A developer-oriented framework for building real-time AI character experiences with text, voice, and Live2D support.

---

## What is this?

This project is an open-source framework for building AI character interaction systems.

It provides a modular foundation combining:

- Multi-LLM conversation (routing + fallback)
- Voice input/output (STT / TTS)
- Live2D (VTube Studio) integration
- Emotion-aware response handling
- Character-level expression mapping

The goal is to let developers focus on features, not infrastructure.

---

## First Run

For the first run, start with:

```env
APP_PRESET=text_chat
```

`text_chat` is the safest starting point because it has the fewest dependencies and is the easiest way to confirm that the framework is working correctly.

Recommended order:

1. `text_chat` — confirm the basic text conversation flow
2. `text_vts` — confirm Live2D / VTS integration without voice
3. `voice_vts` — try the full voice + Live2D experience

---

## Presets

### `text_chat`

Safe default preset for first run.

- Keyboard input
- Text output
- No Live2D
- No voice input/output

Use this preset to confirm that the base framework is working.

---

### `text_vts`

Preset for checking Live2D / VTS behavior without voice features.

- Keyboard input
- Text output
- Live2D enabled
- No voice input/output

Use this preset when you want to test character expression control before enabling voice.

---

### `voice_vts`

Full voice + Live2D preset.

- Voice input (STT)
- Voice output (TTS)
- Live2D enabled

This preset provides the richest experience, but it also has the most runtime dependencies.
After confirming that `text_chat` or `text_vts` works correctly, move on to `voice_vts`.

---

### `bilingual_ja_en`

Example preset for bilingual-style testing.

- Japanese input
- English output
- No Live2D
- No voice input/output

Use this preset when you want to test language separation, such as Japanese input with English-only responses.

---

## Voice Mode Notes

`voice_vts` is intended as an upper-level preset after basic confirmation.

In `voice_vts`:

- STT is used for voice input
- TTS is used for voice output
- if voice input is not detected, text fallback can be used
- type `exit` or `quit` in text fallback to end the session normally
- use `Ctrl+C` for forced termination

This keeps voice mode easier to exit and more practical during testing.

---

## Current Features

- Multi-LLM support (Gemini / Grok)
- Automatic routing (chat vs code)
- Fallback handling
- Voice input (STT) / output (TTS)
- Live2D (VTube Studio) optional integration
- Emotion tag generation and parsing
- Character-level VTS hotkey mapping
- Plugin-based VTS emotion handling
- Clean modular architecture

---

## Architecture

```text
main.py
  ↓
runtime (init)
  ↓
session (loop)
  ↓
pipeline
  ├── LLM (router + fallback)
  ├── TTS
  ├── Hooks
  └── Emotion parsing
         ↓
plugins
  └── EmotionVTSPlugin
         ↓
VTS hotkey trigger
```

Main emotion flow:

```text
User input
-> LLM raw response
-> parse_emotion_response()
-> emotion + clean_text
-> display clean_text
-> TTS clean_text
-> resolve_emotion_hotkey()
-> VTS trigger_hotkey()
```

---

## Extensibility

This framework includes lightweight extension points for runtime customization.

- **Hooks** are event-style extension points used inside the runtime flow
- **Plugins** are lifecycle-oriented extensions used for setup, startup, shutdown, and integration behavior

This keeps the core runtime small while making it easier to add logging, integrations, or custom runtime behavior.

---

## Project Structure

```text
core/
  runtime.py
  session.py
  pipeline.py
  emotion.py
  events.py

llm/
  base.py
  builder.py
  router_llm.py
  fallback_llm.py

live2d/
  vts_client.py

plugins/
  base.py
  manager.py
  builtin/
    console_logger.py
    emotion_vts.py
    response_length_logger.py
  samples/
    simple_greeting.py

config/
  loader.py
  secrets.py
  defaults.py
  legacy.py

registry/
  llm.py
  tts.py

characters/
  default/
    profile.json
    system.txt
    vts_hotkeys.json

presets/
  text_chat.json
  text_vts.json
  voice_vts.json
  bilingual_ja_en.json

stt/
tts/

main.py
```

---

## Character Customization

Character-related files define who the character is.
Preset and runtime settings define how the application runs.

A character is managed as one directory under `characters/`.

```text
characters/
  default/
    profile.json
    system.txt
    vts_hotkeys.json
```

Each character directory can contain the same three files.

---

### Character files

- `profile.json`
  - Basic character metadata such as name and description
  - Useful for identifying the character
  - This is not the main behavior prompt

- `system.txt`
  - The main system prompt that defines how the character speaks and behaves
  - Edit this first when you want to change personality, tone, or response style

- `vts_hotkeys.json`
  - Emotion / Live2D hotkey mappings used for VTS expression control
  - Only needed when using VTube Studio expression control

---

### Editing guide

- If you want to change the character's identity:
  - edit `characters/<character_name>/profile.json`

- If you want to change the character's tone, style, or behavior:
  - edit `characters/<character_name>/system.txt`

- If you want to change facial-expression or emotion mappings:
  - edit `characters/<character_name>/vts_hotkeys.json`

- If you want to switch which character is used:
  - edit `character_name` in `presets/*.json`

- If you want to change input/output mode or runtime behavior:
  - edit `APP_PRESET` in `.env`
  - edit `presets/*.json`

---

### Adding a new character

The simplest way to add a new character is to copy the default character directory.

1. Copy `characters/default/`
2. Rename the copied directory, for example `characters/my_character/`
3. Edit `profile.json`
4. Edit `system.txt`
5. Edit `vts_hotkeys.json` if you use VTube Studio expression control
6. Set `character_name` in `presets/*.json` to the new directory name

Example:

```text
characters/
  default/
    profile.json
    system.txt
    vts_hotkeys.json
  my_character/
    profile.json
    system.txt
    vts_hotkeys.json
```

Then update a preset:

```json
{
  "character_name": "my_character"
}
```

The directory name under `characters/` and the `character_name` value in the preset should match.

---

### Preset vs Character

A simple rule:

- Character = who the assistant is
- Preset / Runtime = how the system runs

Examples:

- Change speaking style -> character (`system.txt`)
- Change displayed name / description -> character (`profile.json`)
- Change emotion-to-VTS mapping -> character (`vts_hotkeys.json`)
- Change selected character -> preset (`character_name`)
- Change text/voice mode -> preset (`presets/*.json`)

---

## Setup

### 1. Clone

```bash
git clone https://github.com/murayan1982/ai-character-framework.git
cd ai-character-framework
```

---

### 2. Install

```bash
pip install -r requirements.txt
```

---

### 3. Environment Variables

Create `.env` from `.env.example`.

Windows:

```bash
copy .env.example .env
```

Mac / Linux:

```bash
cp .env.example .env
```

Then open `.env` and add your API keys.

Required:

```env
GEMINI_API_KEY=your_api_key_here
```

Optional:

```env
XAI_API_KEY=your_xai_api_key_here
ELEVENLABS_API_KEY=your_key_here
```

Optional voice configuration:

```env
VOICE_MASTER=[{"id":"your_voice_id_here","name":"MyVoice"}]
```

---

## Developer Flow

For regular development, start from the smallest working setup and then add features step by step.

Recommended flow:

1. Start with `APP_PRESET=text_chat`
2. Confirm the basic text conversation flow
3. Customize the character under `characters/*`
4. Switch presets when you want to test Live2D or voice features
5. Edit registry files only when you want to change LLM or TTS definitions

Use these files as the main entry points:

- `.env`
  - Selects the startup preset with `APP_PRESET`

- `presets/*.json`
  - Defines runtime mode such as text, voice, Live2D, language, and selected character

- `characters/*`
  - Defines character-specific identity, behavior, and VTS expression mapping

- `registry/llm.py`
  - Defines available LLM providers and routes

- `registry/tts.py`
  - Defines available TTS providers and models

A simple rule:

- Change who the assistant is -> edit `characters/*`
- Change how the framework runs -> edit `.env` or `presets/*.json`
- Change provider definitions -> edit `registry/*`

---

## Runtime Configuration

Runtime behavior is controlled mainly by:

- `APP_PRESET`
- `presets/*.json`
- character files under `characters/*`

Character files and runtime settings have different responsibilities.

- `characters/*` defines who the character is
- `APP_PRESET` and `presets/*.json` define how the framework runs
- `RuntimeConfig` is assembled from both and becomes the runtime source of truth

Example:

```env
APP_PRESET=text_chat
```

The framework loads the selected preset and builds a `RuntimeConfig` object at startup.

---

### RuntimeConfig controls things like

- input language
- output language
- STT on/off
- TTS on/off
- VTS on/off
- emotion on/off
- VTS emotion on/off
- selected character
- selected character hotkey mapping

---

### Configuration Flow

Runtime behavior is configured in the following order:

1. `.env` selects the startup preset through `APP_PRESET`
2. `presets/*.json` defines the runtime mode
3. `characters/*` provides character-specific differences
4. `config/loader.py` assembles `RuntimeConfig`
5. Runtime behavior should read from `RuntimeConfig` as the source of truth

---

### What to edit for common changes

- Change startup mode:
  - `APP_PRESET` in `.env`
  - `presets/*.json`

- Change character-specific behavior:
  - `characters/<name>/profile.json`
  - `characters/<name>/system.txt`
  - `characters/<name>/vts_hotkeys.json`

- Change LLM definitions or route setup:
  - `registry/llm.py`

- Change TTS model definitions:
  - `registry/tts.py`

- Change developer-side defaults:
  - `config/defaults.py`

- Change API keys / secret values:
  - `.env`
  - `config/secrets.py`

- Review older compatibility paths:
  - `config/legacy.py`

---

### Recommended development starting point

Use `text_chat` as the safe default preset for regular development.

---

## Repository Naming

Repository name:

`ai-character-framework`

Project / README title:

`AI Character Conversation Framework`

This keeps the repository name short and practical while making the full project purpose clearer in the documentation.

---

## License

Please see `LICENSE.txt` for the full license terms.

This project is intended to be shared and used as a framework, but redistribution, reuse, or resale of the framework itself should follow the license terms carefully.

---

[Next Roadmap]

After v2.0, advanced conversation runtime topics are tracked in:

- `roadmap_feature_v3.0.md`