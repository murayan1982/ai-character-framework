## Configuration Flow

Runtime behavior is configured in the following order:

1. `.env` selects the startup preset through `APP_PRESET`
2. `presets/*.json` defines the runtime mode
3. `characters/*` provides character-specific differences
4. `config/loader.py` assembles `RuntimeConfig`
5. Runtime behavior should read from `RuntimeConfig` as the source of truth

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

### Recommended development starting point

Use `text_chat` as the safe default preset for regular development.

Recommended example:

```env
APP_PRESET=text_chat
```

Move to `text_vts` or `voice_vts` only when you want to verify TTS / VTS behavior.
