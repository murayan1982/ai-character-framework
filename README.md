# AI Voice Bot Framework

A modular AI bot framework that integrates **LLM (Gemini) + TTS (ElevenLabs) + Live2D**.

Build your own interactive AI character with voice and animation.

---

👉 Get the ready-to-use version:
https://murayan7.gumroad.com/l/qhxey

---

## ✨ Features

- 🧠 Natural conversation using Google Gemini
- 🔊 High-quality voice synthesis via ElevenLabs
- 🎭 Live2D integration support
- ⚙️ Flexible configuration (models, voice, speed, etc.)
- 🧩 Modular structure for easy customization

---

## 🚀 Quick Start

### 1. Clone repository

```
git clone https://github.com/murayan1982/AI-bot-Prj.git
cd AI-bot-Prj
```

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Create `.env`

Create a `.env` file in the root directory:

```
GEMINI_API_KEY=your_api_key_here
ELEVENLABS_API_KEY=your_api_key_here

# LLM Model (optional)
GOOGLE_MODEL=gemini-2.5-flash

# Voice settings (REQUIRED for TTS)
# Replace with your own Voice ID from ElevenLabs
VOICE_MASTER='[{"name":"My Voice","id":"YOUR_VOICE_ID"}]'
```

---

### 🔊 How to get Voice ID (ElevenLabs)

1. Go to ElevenLabs
2. Select a voice
3. Copy the **Voice ID**
4. Paste it into `.env`

---

⚠️ If you do not set a valid Voice ID, voice output will not work.

---

## ⚙️ Configuration

Main settings are located in:

```
config/settings.py
```

You can adjust:

* LLM model selection
* Voice settings (via `.env`)
* TTS speed
* Engine switches (STT / TTS)

### 4. Run

```
python main.py
```

---

## 🎯 Who is this for?

- Developers who want to build AI-powered characters
- People interested in voice-based AI interaction
- Anyone experimenting with LLM + TTS + Live2D

---

## 🗂 Project Structure

```
my-ai-bot/
├── config/        # Settings and model configuration
├── llm/           # LLM integration (Gemini)
├── tts/           # Voice engine (ElevenLabs)
├── live2d/        # Live2D integration
├── prompts/       # System prompts
├── utils/         # Utility scripts
├── main.py        # Entry point
```

---

## ⚙️ Configuration

Main settings are located in:

```
config/settings.py
```

You can adjust:

- LLM model selection
- Voice settings
- TTS speed
- Engine switches (STT / TTS)

### 🎛 Voice Control

You can enable/disable voice input and output in:

```
config/settings.py
```

```python
INPUT_VOICE_ENABLED = True   # Enable speech-to-text
OUTPUT_VOICE_ENABLED = True  # Enable text-to-speech
```

Examples:

* Input ON / Output OFF → Text chatbot with voice input
* Input OFF / Output ON → Text-to-speech only
* Both ON → Full voice interaction

---

## 🧪 Example Use Cases

- AI VTuber prototype
- Voice assistant with personality
- Interactive character systems

---

## ⚠️ Notes

- `.env` is required for API keys
- FFmpeg (`ffplay`) must be installed for audio playback

---

## 📌 Roadmap

- Streaming TTS
- Improved Live2D sync
- UI for configuration

---

## 📄 License
Please refer to LICENSE.txt for details. Redistribution and resale are prohibited.

## ⚠️ Important Notice / Disclaimer

1. **API Keys**  
   This product does **not** include any API keys. Users must supply their own keys for the following services:
   - ElevenLabs (Text-to-Speech)
   - Google Gemini API

2. **User Responsibility**  
   Users are responsible for complying with the terms of service, usage limits, and payment obligations of any third-party services they use.

3. **Generated Content**  
   Any content generated using third-party APIs may be used in the provider's machine learning, testing, or development processes according to their terms. The author of this product is **not responsible** for how generated content is used by these services.

4. **Live2D / Other Assets**  
   This product does **not** include any proprietary Live2D models or licensed assets. Users must obtain and use their own assets according to their licenses.

5. **Liability**  
   This software is provided "as-is" without warranty. The author is not responsible for any damages, data loss, or issues resulting from the use of this software.

By using this product, you agree to these terms.
---

## 💡 Author

Created by murayan

