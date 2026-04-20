# AI Character Conversation Framework

## What is this?

This is a **developer-oriented framework** for building AI character interaction systems.

It provides a modular foundation combining:

- Multi-LLM conversation (routing + fallback)
- Voice input/output (STT / TTS)
- Live2D (VTube Studio) integration
- Emotion-aware response handling
- Character-level expression mapping

The goal is to let developers **focus on features**, not infrastructure.

---

## Features (v1.5.0)

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

Main v1.5 emotion flow:

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

config/
  loader.py
  runtime_config.py
  settings.py
  models.py

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

## Setup

### 1. Clone

```bash
git clone https://github.com/murayan1982/AI-bot-Prj.git
cd AI-bot-Prj
```

### 2. Install

```bash
pip install -r requirements.txt
```

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

## Runtime Configuration

Runtime behavior is controlled mainly by:

- `APP_PRESET`
- `presets/*.json`
- character files under `characters/*`

Example:

```env
APP_PRESET=text_chat
```

The framework loads the selected preset and builds a `RuntimeConfig` object at startup.

### RuntimeConfig controls things like:

- input language
- output language
- STT on/off
- TTS on/off
- VTS on/off
- emotion on/off
- VTS emotion on/off
- selected character
- selected character hotkey mapping

Recommended default preset for development:

```env
APP_PRESET=text_chat
```

---

## Presets

### text_chat

Safe default preset for regular development.

- keyboard input
- text output only
- VTS disabled
- emotion disabled

### text_vts

Keyboard input + TTS + VTube Studio expression control.

- keyboard input
- voice output
- VTS enabled
- emotion enabled

### voice_vts

Voice input + TTS + VTube Studio expression control.

- STT input
- voice output
- VTS enabled
- emotion enabled

### bilingual_ja_en

Japanese input with English output.

- keyboard input
- text output only
- VTS disabled
- emotion disabled
- output language forced to English

---

## Emotion / VTS Expression Control

When emotion is enabled, the LLM outputs one emotion tag at the beginning of the response.

Example:

```text
[emotion:happy]
Hello! I'm glad to see you.
```

The framework parses this into:

- emotion key: `happy`
- visible / spoken text: `Hello! I'm glad to see you.`

The emotion tag is removed from:

- console display
- TTS text

If VTS emotion control is enabled, the framework resolves the emotion key to a character-specific VTube Studio hotkey name and triggers it safely.

### Standard emotion keys

```text
neutral
happy
sad
angry
surprised
confused
```

Unknown or invalid emotion values fall back to `neutral`.

---

## Character Hotkey Mapping

The framework does **not** hardcode VTube Studio hotkey names.

Instead, each character provides its own mapping file:

```text
characters/default/vts_hotkeys.json
```

Example:

```json
{
  "neutral": "Remove Expressions",
  "happy": "Heart Eyes",
  "sad": "Eyes Cry",
  "angry": "Angry Sign",
  "surprised": "Shock Sign",
  "confused": null
}
```

Rules:

- the framework handles abstract emotion keys only
- the actual VTS hotkey name is defined per character
- `null` means "do nothing"
- if a hotkey is missing or VTS is unavailable, the conversation continues

---

## LLM Routing & Fallback

The framework automatically selects models by route.

Typical routing:

- chat -> fast conversational model
- code -> reasoning-capable model

If a request fails:

- fallback LLM is automatically used

Current configuration is defined in:

- `LLM_CATALOG`
- `LLM_ROUTES`

---

## Voice Configuration

Voice IDs are loaded from `.env`:

```env
VOICE_MASTER=[{"id":"voice_id","name":"MyVoice"}]
```

Selection is currently done through developer-side defaults in `settings.py`, for example:

```python
SELECT_VOICE_INDEX = 0
SELECT_TTS_MODEL_INDEX = 2
```

TTS is optional.

For regular development, `text_chat` is the safest default.  
Use `text_vts` or `voice_vts` when you want to verify TTS / VTS behavior.

---

## Live2D (VTube Studio)

- Optional feature
- Token is generated automatically on first run
- Emotion control is handled through character-level hotkey mapping
- VTS hotkeys are triggered safely through the VTS client
- If VTube Studio is not running, the conversation continues

---

## Plugins

The framework includes a minimal plugin system.

Current built-in plugins include:

- `ConsoleLoggerPlugin`
- `EmotionVTSPlugin`

Typical responsibilities:

- logging runtime activity
- reacting to parsed emotion events
- triggering VTS hotkeys from character mappings

---

## Hooks (Extension Points)

Current runtime hooks include:

```python
on_user_input(text)
on_llm_chunk(chunk)
on_llm_complete(response)
on_emotion_detected(emotion)
on_error(error)
```

Use cases:

- logging
- streaming UI
- external integrations
- character behavior extensions

---

## Minimal Example

```python
import asyncio
from llm.factory import create_llm

async def main():
    llm = create_llm(
        provider="google",
        system_instruction="You are a helpful AI assistant.",
        model="gemini-2.5-flash"
    )

    for chunk, emotions in llm.ask_stream("Hello"):
        print(chunk, end="")

asyncio.run(main())
```

---

## Recommended Development Flow

For regular development:

1. Start with `text_chat`
2. Verify emotion / VTS behavior with `text_vts`
3. Verify full STT / TTS / VTS flow with `voice_vts`

This keeps the default development loop lightweight while still allowing full behavior checks when needed.

---

## Roadmap

- Runtime mode presets
- Plugin-based extension flow
- More provider cleanup / config responsibility separation
- Local LLM support
- GUI launcher

---

## License

- Personal use: allowed
- Commercial use: allowed
- Modification: allowed
- Use in your own applications and services: allowed
- Redistribution or resale of the framework itself: not allowed
- Redistribution or resale of lightly modified or repackaged versions of the framework: not allowed

See LICENSE.txt for details.

---

## Notes

- .env must match .env.example
- Voice IDs are required only when TTS is enabled
- VTS requires VTube Studio running locally
- If a VTS hotkey is not configured, expression control is skipped safely
- In the current v1.5 implementation, long TTS playback may occasionally trigger a wait timeout warning even when playback still works in practice

---

## Author

Framework for building **AI-powered character interaction systems**.

## 💡 Support

If you find this project useful, consider supporting development.

Optional ready-to-run packaged versions for quick testing:

Gumroad: https://murayan7.gumroad.com/l/qhxey

BOOTH: https://murayan.booth.pm/items/8182937