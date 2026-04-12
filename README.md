# AI Character Conversation Framework

## What is this?

This is a **developer-oriented framework** for building AI character interaction systems.

It provides a modular foundation combining:

* Multi-LLM conversation (routing + fallback)
* Voice input/output (STT / TTS)
* Live2D (VTube Studio) integration
* Emotion-driven character expression

The goal is to let developers **focus on features**, not infrastructure.

## Features (v1.3.0)

* Multi-LLM support (Gemini / Grok)
* Automatic routing (chat vs code)
* Fallback handling
* Voice input (STT) / output (TTS)
* Live2D (VTS) optional integration
* Hook-based extensibility
* Clean modular architecture

---

## Architecture

```
main.py
  ↓
runtime (init)
  ↓
session (loop)
  ↓
pipeline
  ├── LLM (router + fallback)
  ├── TTS
  ├── VTS (emotion)
  └── Hooks
```

---

## Project Structure

```
core/
  runtime.py
  session.py
  pipeline.py
  events.py

llm/
  base.py
  factory.py
  builder.py
  router_llm.py
  fallback_llm.py

live2d/
  vts_client.py

config/
  settings.py
  models.py

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

Create `.env` from `.env.example`:

- Windows:
  copy .env.example .env

- Mac / Linux:
  cp .env.example .env

Then open `.env` and add your API keys:

# Required
GEMINI_API_KEY=your_api_key_here

# Optional
XAI_API_KEY=your_xai_api_key_here
ELEVENLABS_API_KEY=your_key_here

# Voice configuration (JSON format)
VOICE_MASTER=[{"id":"your_voice_id_here","name":"MyVoice"}]
```

---

## Runtime Configuration

All runtime behavior is controlled in:

```
config/settings.py
```

Key flags:

```python
INPUT_VOICE_ENABLED = False
OUTPUT_VOICE_ENABLED = False
ENABLE_VTS = False
DEBUG_MASTER = False
```

---

## Running Modes (examples)

These are common configurations (fully customizable):

| Mode        | STT | TTS | VTS |
| ----------- | --- | --- | --- |
| Text only   | ❌   | ❌   | ❌   |
| Text + VTS  | ❌   | ❌   | ✅   |
| Voice + VTS | ✅   | ✅   | ✅   |

These are example configurations. STT, TTS, and VTS can be enabled independently.

---

## LLM Routing & Fallback

The framework automatically selects models:

* Chat → fast conversational model
* Code → reasoning-capable model

If a request fails:

* Fallback LLM is automatically used

Configuration:

* `LLM_CATALOG`
* `LLM_ROUTES`
* `STRONG_CODE_KEYWORDS`

---

## Voice Configuration

Voice IDs are loaded from `.env`:

```env
VOICE_MASTER=[{"id":"voice_id","name":"MyVoice"}]
```

Selection is done in `settings.py`:

```python
SELECT_VOICE_INDEX = 0
```

---

## Live2D (VTube Studio)

* Optional feature (`ENABLE_VTS`)
* Token is generated automatically on first run
* Emotion mapping is configurable:

```python
VTS_EMOTION_ALIAS = {
    "smile": "heart eyes",
    "sad": "eyes cry",
}
```

---

## Hooks (Extension Points)

```python
on_user_input(text)
on_llm_chunk(chunk)
on_llm_complete(response)
on_error(error)
```

Use cases:

* Logging
* Streaming UI
* External integrations

---

## Minimal Example

```python
## Minimal Example

import asyncio
from llm.factory import create_llm

async def main():
    llm = create_llm(
        provider="google",
        system_instruction="You are a helpful AI",
        model="gemini-2.5-flash"
    )

    for chunk, emotions in llm.ask_stream("Hello"):
        print(chunk, end="")

asyncio.run(main())
```

---

## Roadmap

* Runtime mode presets (v1.4)
* Plugin system
* Local LLM support
* GUI launcher

---

## License

Custom License

* Personal / commercial use: allowed
* Modification: allowed
* Redistribution: restricted

---

## Notes

* `.env` must match `.env.example`
* Voice IDs are required only when TTS is enabled
* VTS requires VTube Studio running locally

---

## Author

Framework for building **AI-powered character interaction systems**.

## 💡 Support

If you find this project useful, consider supporting development:

Gumroad: https://murayan7.gumroad.com/l/qhxey
BOOTH: https://murayan.booth.pm/items/8182937