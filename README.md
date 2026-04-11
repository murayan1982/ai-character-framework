# AI Character Framework (LLM + Voice + Live2D)

A modular framework for building **interactive AI characters**
with voice, emotion, and Live2D integration.

This project is designed for developers who want to build, extend, and experiment with AI-driven character systems.

---

## ✨ Features

* 🧩 Event hook system for extending behavior without modifying core code
* ⚙️ Clear separation of concerns (runtime / session / pipeline / events)
* 🔌 **LLM-agnostic design** (OpenAI / Grok / Gemini / others)
* 🔊 **TTS integration** (e.g. ElevenLabs)
* 🎭 **Live2D support** via VTube Studio (VTS)
* 🧠 **Emotion mapping system** (text → expression / hotkey)
* ⚙️ **Modular architecture** for easy extension

---

## 🎯 Target Users

* Developers building AI character applications
* VTuber tool creators
* Researchers / hobbyists experimenting with human-AI interaction

---

## 🧠 Design Philosophy

* Keep components loosely coupled
* Make each module replaceable
* Enable fast experimentation
* Expose extension points via event hooks

---

## 🧩 Architecture Overview

```
User Input
↓
[Session]
↓
[Pipeline]
↓
├─→ [LLM] → (OpenAI / Grok / Gemini / etc.)
├─→ [TTS Engine]
└─→ [Live2D / VTS]

[Events] ← hooks can intercept at multiple stages
```
---

## 📁 Project Structure

```
project/
├─ core/
│  ├─ runtime.py
│  ├─ session.py
│  ├─ pipeline.py      # Response processing pipeline
│  ├─ events.py        # Event hook system
│  └─ utils/
│     └─ logging.py    # Logging utilities
│
├─ llm/                # LLM providers (OpenAI, Grok, Gemini, etc.)
├─ tts/                # Text-to-Speech engines
├─ stt/                # Speech-to-Text engines
├─ live2d/             # VTube Studio integration
├─ config/             # Settings & environment config
├─ prompts/            # System prompts / character prompts
│
└─ main.py             # Entry point
```
---

## 🔌 Extending with Hooks

You can extend behavior without modifying core logic:

```python
from core.events import register_hook

def on_user_input(text):
    print("User said:", text)

register_hook(runtime, "on_user_input", on_user_input)
```

## 🧪 Minimal Example (LLM Only)

Run a simple LLM interaction without TTS or VTS:

```python
import asyncio
from llm.factory import create_llm

async def main():
    llm = create_llm("You are a helpful AI.")

    user_input = "Hello"
    full_text = ""

    for text, emotions in llm.ask_stream(user_input):
        print(text, end="", flush=True)
        full_text += text

    print("\n---")
    print("Final:", full_text)

asyncio.run(main())
```

This is the core building block of the framework.

---

## 🔌 Extensibility

### Add a new LLM provider

1. Implement a new adapter in `llm/`
2. Match the interface:

```python
class BaseLLM: 
   def ask_stream(self, prompt: str): 
      yield text, emotions
```

3. Register it in config

---

### Replace TTS engine

* Modify `tts/` module
* Ensure output format compatibility

---

## ⚙️ Setup

```bash
git clone <repo>
cd project
pip install -r requirements.txt
```

Create `.env`:

```
LLM_PROVIDER=openai
OPENAI_API_KEY=xxx

TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=xxx
```

---

## 🚀 Quick Start (Full System)

Run the full pipeline (LLM + TTS + VTS):

```bash
python main.py
```

---

## 🚧 Roadmap

* [ ] Multi-LLM runtime switching
* [ ] Plugin system
* [ ] GUI for configuration
* [ ] Local LLM support (Ollama, etc.)

---

## 📄 License

Please refer to LICENSE.txt for details. Redistribution and resale are prohibited.

---

## 💡 Notes

This is a **framework**, not a polished end-user application.
It is intended to be used as a base for building custom AI character systems.

