# Developer Configuration Guide

## Purpose

This document explains how configuration is organized in the v1.6 structure.

It is intended to help developers quickly understand:

- where runtime behavior is selected
- where character-specific differences are stored
- where model registries live
- where developer defaults and secrets belong
- which files to change for common customization tasks

This guide describes the current v1.6 configuration flow.
It is not a full architecture redesign document.

---

## Configuration Responsibility Map

The current structure is organized around the following responsibilities.

### 1. Presets

Presets define startup mode.

Examples:

- `text_chat`
- `text_vts`
- `voice_vts`
- `bilingual_ja_en`

Presets are responsible for things like:

- input language
- output language
- voice on/off
- VTS on/off
- emotion on/off
- selected character
- TTS provider

Location:

- `presets/*.json`

---

### 2. Characters

Characters define character-specific differences.

Character data is responsible for:

- profile
- system prompt
- VTS hotkey mapping

Location:

- `characters/<name>/profile.json`
- `characters/<name>/system.txt`
- `characters/<name>/vts_hotkeys.json`

Characters do not define the general runtime mode.
That is the responsibility of presets.

---

### 3. RuntimeConfig

`RuntimeConfig` is the runtime source of truth.

At startup, the loader reads preset data and character data,
then assembles a `RuntimeConfig` instance.

After initialization, runtime behavior should prefer reading from
`RuntimeConfig` rather than older global config paths.

Main location:

- `config/loader.py`

---

### 4. Registries

Registries contain static definition tables.

Current examples:

- `registry/llm.py`
- `registry/tts.py`

These files should contain static model/provider definitions,
not user-specific environment values.

Examples of registry responsibilities:

- LLM catalog
- LLM routes
- TTS model definitions

---

### 5. Secrets

Secrets are environment-backed values such as API keys.

Main locations:

- `.env`
- `config/secrets.py`

Secrets should not be mixed with runtime defaults or static registries.

---

### 6. Developer Defaults

Developer defaults are local development-side selections.

Examples:

- debug switches
- default voice index
- default TTS model index

Main location:

- `config/defaults.py`

These values are meant to support development convenience,
not to define the full runtime mode.

---

### 7. Legacy Compatibility

Legacy compatibility is kept separate from the preferred runtime path.

Examples:

- old global flags
- backward-compatibility aliases
- older compatibility mappings

Main location:

- `config/legacy.py`

These values remain only to avoid breaking older paths.
Preferred new behavior should be driven by presets, characters, and `RuntimeConfig`.

---

## Startup Flow

The current startup flow is:

```text
.env
-> APP_PRESET
-> presets/<preset>.json
-> character selection
-> characters/<name>/*
-> RuntimeConfig assembly
-> runtime uses RuntimeConfig
```

This means:

- `.env` selects the startup preset
- the preset defines runtime mode
- character files provide character-specific differences
- the loader assembles `RuntimeConfig`
- the runtime should treat `RuntimeConfig` as the final source of truth

---

## What To Edit For Common Changes

### Change the startup mode

Edit:

- `.env`
- `APP_PRESET=text_chat` or another preset

Or modify preset files under:

- `presets/*.json`

---

### Change character behavior

Edit character files:

- `characters/<name>/profile.json`
- `characters/<name>/system.txt`
- `characters/<name>/vts_hotkeys.json`

Use this for:

- changing character identity
- changing system prompt behavior
- changing VTS hotkey mapping per character

---

### Change LLM configuration

Edit:

- `registry/llm.py`

Use this for:

- changing provider/model definitions
- changing route definitions
- adjusting which model is used for chat/code paths

---

### Change TTS model definitions

Edit:

- `registry/tts.py`

Use this for:

- changing available TTS model definitions
- adjusting TTS-side registry values

---

### Change API keys or secret values

Edit:

- `.env`

Reference loading lives in:

- `config/secrets.py`

Use this for:

- Gemini key
- xAI key
- ElevenLabs key
- other environment-backed secrets

---

### Change developer-side defaults

Edit:

- `config/defaults.py`

Use this for:

- debug switches
- default selection indices
- other local development defaults

---

### Review compatibility behavior

Edit or inspect:

- `config/legacy.py`

Use this when working with:

- old compatibility flags
- old alias paths
- temporary compatibility retention

Do not treat this as the preferred location for new runtime behavior.

---

## Recommended Development Flow

For regular development, start with:

```env
APP_PRESET=text_chat
```

Why:

- safest default behavior
- no STT required
- no TTS required
- no VTS dependency required
- easiest way to confirm the main runtime path

Then move to:

- `text_vts` when testing TTS + VTS from keyboard input
- `voice_vts` when testing the full voice path
- `bilingual_ja_en` when testing input/output language split

---

## Notes For Future Cleanup

The v1.6 structure is cleaner than earlier versions, but some cleanup is still intentionally incremental.

Examples of remaining areas that may evolve later:

- stronger typing for runtime dictionaries
- more explicit provider capability separation
- additional developer-facing docs
- further cleanup of remaining legacy/global paths

The goal of v1.6 is not to finalize everything,
but to make the configuration structure easier to read, maintain, and extend.

---

## Summary

At a high level:

- presets choose the runtime mode
- characters choose character-specific differences
- registries hold static model definitions
- secrets hold environment-backed values
- defaults hold developer-side convenience values
- legacy is isolated from the preferred runtime path
- `RuntimeConfig` is the runtime source of truth

If you are unsure where to start, begin with:

1. `.env`
2. `presets/*.json`
3. `characters/*`
4. `config/loader.py`
