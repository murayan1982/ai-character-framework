AI Conversation Framework

A modular AI conversation framework with:

* Multi-LLM routing (Chat / Code)
* Voice input/output support (STT / TTS)
* Live2D emotion integration
* Extensible architecture

---

## Prerequisites

Before starting, ensure you have:

* Python 3.10+
* pip

Optional (for voice features):

* ffmpeg
* Microphone (for STT)
* Speakers (for TTS)

You also need at least one API key:

* OpenAI
* Google (Gemini)
* xAI (Grok)

---

## Quick Start

1. git clone <your-repo>
2. cd <your-project>
3. pip install -r requirements.txt
4. cp .env.example .env

Edit .env:

LLM_PROVIDER=google
GOOGLE_API_KEY=your_api_key_here

Run:

python main.py

Example:

User: hello
AI: Hi there! How can I help you today?

---

## Routing Logic

The framework automatically switches between Chat and Code modes.

How it works:

* Keyword-based detection
* If input matches STRONG_CODE_KEYWORDS -> Code mode
* Otherwise -> Chat mode

Example:

* "write python code" -> Code
* "how are you" -> Chat

You can customize behavior in:

config/settings.py

---

## Features

* Multi-LLM support (OpenAI / Gemini / Grok)
* Automatic routing (Chat / Code)
* STT -> LLM -> TTS pipeline
* Live2D emotion mapping
* Modular plugin-ready structure

---

## Voice Setup Notes

To use STT/TTS features:

- Install ffmpeg (required for audio processing)
  - Windows: choco install ffmpeg
  - Mac: brew install ffmpeg

- Ensure your microphone is properly recognized by your OS

Note:
Some audio libraries may require additional system-level setup.

## Emotion Mapping
Live2D integration uses WebSocket communication (e.g. VTube Studio API).
The system can map AI responses to Live2D expressions.

Example:

* happy -> smile
* angry -> frown
* surprised -> wide eyes

Customize in:

vts/emotion_map.py

---

## Configuration Priority

Settings are loaded in the following order:

1. .env
2. config/settings.py

.env overrides default settings.

---

## Commercial Usage

You are allowed to:

* Sell applications built using this framework
* Create AI characters for streaming (YouTube / Twitch)
* Provide paid AI services or SaaS

You are NOT allowed to:

* Resell this framework itself
* Redistribute source code as a standalone product
* Repackage and sell with minor modifications

---

## Notes

* Model names (e.g. gemini-2.5-flash) may change over time
* Please refer to each provider’s official documentation

## Attribution

When using this framework in a product or service,
you must include attribution to the original author.

Example:

"Powered by AI Conversation Framework by murayan"

This can be placed in:
- Application credits
- Website footer
- Video descriptions

---

## License

This project is licensed under a custom commercial license.

See LICENSE.txt for details.
