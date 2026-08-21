# AI Character Conversation Framework

A developer-oriented framework for building real-time AI character experiences with text, voice, and Live2D support.

This project is a framework, not a finished consumer app.

**Target audience:** Developers, VTuber creators, and AI experimenters who want a practical foundation for AI character interaction systems.

---

<!-- FW-RT6-14b-README-CURRENT:BEGIN -->
## Current v6.0.0 source status

| Item | Current truth |
| --- | --- |
| Source version | `6.0.0.dev0` |
| v6.0.0 source candidate | `DOCUMENTATION_FROZEN / NOT_RELEASED` |
| Latest published release | `v5.5.0` |
| Documentation-freeze baseline | `7d65771784ddc5409076909f874d098758486d98` |
| FW-RT6-14b implementation commit | `72cfa09f6551e1fc3d042777733627c900237cdc` |
| FW-RT6-14b documentation freeze | `ACCEPTED / AWAITING_SYNC_COMMIT_PUSH` |
| Root-public surface | 127 names / unchanged |
| Compatibility | v5 standalone sessions preserved; default `RealtimeSession` remains provider-free `v5_skeleton` |

v6 adds a provider-neutral realtime lifecycle, capability snapshots, canonical
events, typed results and errors, cooperative interruption, stale-result rejection,
host playback coordination, guarded real-runtime composition, and provider-free
aggregate conformance. Real execution is always explicit and capability-gated.

An explicit `real_runtime_enabled=True` request selects the guarded `v6_unified`
profile. Missing or failed stage configuration is rejected with a typed result; it
does not silently run the mock path as real work. The completed FW-RT6-13c operator
acceptance does not enable production unified real-provider orchestration through
`RealtimeSession`.

Start with these current documents:

- [Advanced runtime behavior](docs/advanced_runtime.md)
- [v5-to-v6 migration guide](docs/v600_v5_to_v6_session_migration.md)
- [Capability, event, and error reference](docs/v600_capability_event_error_reference.md)
- [App integration contract](docs/app_integration_contract.md)
- [Public facade contract](docs/public_facade.md)
- [Aggregate conformance gate](docs/v600_aggregate_conformance.md)
- [v6 implementation tasklist](docs/v600_tasklist.md)

The framework remains a developer foundation rather than a finished consumer app.
It does not claim default provider/network/device execution, provider hard cancel,
Framework-owned physical playback stop, or completion of FW-RT6-14c packaging and
release work.

All eight FW-RT6-14b documentation and migration tasks passed the provider-free
documentation gate, the FW-RT6-14a aggregate gate, 12 dedicated aggregate tests,
11 current-compatible smoke dependencies, and the complete 828-test unit suite.
The acceptance sync changes no production/test source and does not authorize
FW-RT6-14c implementation. FW-RT6-14c exact contract review becomes authorized
only after this sync is committed, pushed, and remotely verified.
<!-- FW-RT6-14b-README-CURRENT:END -->

---

## What this framework provides

The framework provides a modular foundation for:

- Multi-LLM conversation with routing and fallback
- Text chat runtime
- Voice input and output with STT / TTS
- Live2D / VTube Studio integration
- Emotion-aware response handling
- Character-level expression mapping
- Plugin and hook based runtime extension points
- A public text chat facade for app-style integration

The goal is to let developers focus on character behavior, app features, and integrations instead of rebuilding the core conversation infrastructure from scratch.

---

## Conversation flow

The minimum application flow remains:

```text
User input
-> LLM response
-> text display
-> optional TTS output
-> optional emotion parsing
-> optional VTS expression trigger
```

When explicitly configured capabilities are available, the same application can add
voice input, streaming response delivery, synthesis, host-owned playback, motion,
and cooperative interruption. v6 assigns session/turn/generation identity,
monotonic event ordering, exactly-once terminal outcomes, and stale-result rejection
to the realtime contract. Provider SDKs, microphone capture, physical playback, and
character-specific VTS mapping remain adapter or host responsibilities.

---

## Quick start

For the first run, start with the safest preset:

```env
APP_PRESET=text_chat
```

`text_chat` has the fewest dependencies and is the easiest way to confirm that the framework is working correctly.

Recommended confirmation order:

1. `text_chat` — confirm the basic text conversation flow
2. `text_vts` — confirm text input with Live2D / VTS integration without voice
3. `voice_vts` — try the full voice + Live2D integration preset

---

## Setup

### 1. Clone

```bash
git clone https://github.com/murayan1982/ai-character-framework.git
cd ai-character-framework
```

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

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

Required for the current default LLM route:

```env
GEMINI_API_KEY=your_gemini_api_key_here
```

Optional LLM providers:

```env
XAI_API_KEY=your_xai_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

Optional voice configuration:

```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
VOICE_MASTER=[{"id":"your_voice_id_here","name":"MyVoice"}]
```

Do not commit your `.env` file.

---

## Presets

### `text_chat`

Safe default preset for first run.

- Keyboard input
- Text output
- No Live2D
- No voice input/output

### `text_vts`

Preset for checking text-driven Live2D / VTS behavior without voice features.

- Keyboard input
- Text output
- Live2D enabled
- No voice input/output
- Emotion / VTS expression control enabled

### `voice_vts`

Full voice + Live2D preset.

- Voice input through STT
- Text fallback during STT wait
- Text display
- Voice output through TTS
- Live2D enabled
- Emotion / VTS expression control enabled

### `bilingual_ja_en`

Example preset for bilingual-style testing.

- Japanese input
- English output
- No Live2D
- No voice input/output

---

## Preset matrix

These presets demonstrate framework capabilities for development and testing. They are not standalone consumer apps.

| Preset | Input | Output | Live2D | Emotion / VTS expression | Main purpose |
| --- | --- | --- | --- | --- | --- |
| `text_chat` | Keyboard | Text | Disabled | Disabled | Safest first-run and base LLM conversation check |
| `text_vts` | Keyboard | Text | Enabled | Enabled | Check Live2D expression flow without voice input/output |
| `voice_vts` | STT + text fallback | Text + TTS | Enabled | Enabled | Minimum full-stack voice + Live2D developer check |
| `bilingual_ja_en` | Keyboard Japanese | Text English | Disabled | Disabled | Check input/output language separation |

These presets are representative user-facing conversation presets, not a complete test matrix for every possible STT / TTS / Live2D combination.

---

## Public text chat facade

The framework exposes a small public API for text-only chat usage and app-style integration.

Use this when you want to call the framework from your own Python application without starting the full interactive runtime.

Minimal example:

```python
from framework import create_text_chat_session

session = create_text_chat_session()
response = session.ask("Hello. Please answer briefly.")
print(response)
```

You can pass a text-only preset and character explicitly:

```python
from framework import create_text_chat_session

session = create_text_chat_session(
    preset="text_chat",
    character_name="default",
)

print(session.ask("こんにちは。短く返して"))
```

For typed app-boundary handling, use `ask_result()`:

```python
result = session.ask_result("こんにちは。短く返して")
if result.is_completed:
    print(result.text)
else:
    print(result.public_error_code, result.safe_message)
```

You can also select a provider and model directly:

```python
from framework import create_text_chat_session

session = create_text_chat_session(
    provider="openai",
    model="gpt-4o-mini",
)

print(session.ask("こんにちは。1文で短く返して。"))
```

Text chat sessions expose stable public metadata through `session.info`:

```python
from framework import create_text_chat_session

session = create_text_chat_session(provider="openai", model="gpt-4o-mini")

print(session.info.preset)
print(session.info.character_name)
print(session.info.provider)
print(session.info.model)
print(session.info.output_language_code)
```

`session.info` is intended for external apps that need to inspect the created session without depending on internal runtime objects. It intentionally does not expose `RuntimeConfig`.

Supported public provider names include:

- `openai`
- `gemini`
- `grok`

If `provider` is omitted, the facade keeps the default chat route with fallback. If `provider` is passed without `model`, the facade resolves the default model from `registry/llm.py`.

For app-style integration, catch public facade errors at the application boundary:

```python
from framework import FacadeError, create_text_chat_session

try:
    session = create_text_chat_session(provider="openai", model="gpt-4o-mini")
    print(session.ask("Hello."))
except FacadeError as e:
    print(f"Framework integration error: {e}")
```

The public facade is intentionally text-only for now.

Supported:

- `text_chat`
- other text-only compatible presets such as `bilingual_ja_en`
- direct provider/model selection for text chat
- app boundary error handling through `FacadeError`
- public session metadata through `session.info`
- streaming through `ask_stream()`
- reset through `reset()`
- limited interrupt boundary through `interrupt()`
- app-facing events through `on_event()` and `on_state_change()`

Not supported through this facade yet:

- voice input
- TTS output
- Live2D / VTube Studio control
- full runtime session loop
- provider-level hard cancellation of active LLM requests
- TTS queue cancellation or realtime voice barge-in

Use `main.py` or the preset run scripts when you want the full runtime experience.

For more details, see:

- `docs/public_facade.md`
- `docs/app_integration_contract.md`
- `examples/public_text_chat.py`
- `examples/minimal_app_text_chat.py`
- `examples/app_error_handling.py`
- `examples/app_streaming_text_chat.py`
- `examples/app_reset_text_chat.py`
- `examples/app_session_info.py`
- `examples/app_state_events.py`
- `examples/app_interrupt_text_chat.py`

---

## Public voice output boundary

v5.0.0 adds a public, provider-neutral voice output boundary for host-app integration.

External apps can request voice output through the framework without depending on internal TTS modules or provider-specific settings.

```python
from framework import VoiceOutputRequest, create_voice_output_session

session = create_voice_output_session()
result = session.speak(
    VoiceOutputRequest(
        text="今日は少し早めに休むとよさそうです。",
        voice_profile_id="gentle_mina_default",
        requested_audio_format="mp3",
        utterance_purpose="daily_advice",
        language_code="ja",
    )
)
```

Host apps should provide only provider-neutral intent:

```text
text
voice_profile_id
requested_audio_format
utterance_purpose
language_code
```

Provider selection, provider voice IDs, API keys, model IDs, provider-specific request parameters, SDK calls, and audio artifact handling remain framework responsibilities.

`VoiceOutputResult` is app-safe. Host apps should treat only `request_state=generated` with `audio_ready=True` and exactly one handoff (`audio_url` or `audio_artifact_ref`) as playable. `unavailable`, `skipped`, `rejected`, and `failed` are non-playable states.

Real provider execution is explicit opt-in and remains guarded by `FRAMEWORK_VOICE_OUTPUT_ALLOW_PROVIDER_EXECUTION=1`.

---



### Public session lifecycle

Public sessions expose an idempotent cleanup boundary:

```python
with create_text_chat_session() as session:
    result = session.ask_result("こんにちは。短く返して")

session = create_voice_output_session()
try:
    result = session.speak(request)
finally:
    session.close()
```

Host applications can call `close()` or `dispose()` when evicting sessions. The
cleanup boundary is provider-neutral and does not require host apps to inspect FW
internals.

## App integration examples

The `examples/` directory includes small, copy-friendly examples for external application integration.

### Basic public facade example

```powershell
python examples/public_text_chat.py
```

### Minimal app wrapper

```powershell
python examples/minimal_app_text_chat.py
```

With direct provider/model selection:

```powershell
python examples/minimal_app_text_chat.py --provider openai --model gpt-4o-mini --message "こんにちは。1文で短く返して。"
```

### Offline-safe error handling

```powershell
python examples/app_error_handling.py
```

This demonstrates public facade errors without calling an external LLM API.

Optional live check:

```powershell
python examples/app_error_handling.py --live --provider openai --model gpt-4o-mini
```

### Streaming response example

```powershell
python examples/app_streaming_text_chat.py --provider openai --model gpt-4o-mini --message "こんにちは。1文で短く返して。"
```

### Reset example

```powershell
python examples/app_reset_text_chat.py --provider openai --model gpt-4o-mini
```

### Session info example

```powershell
python examples/app_session_info.py --provider openai --model gpt-4o-mini
```

### App-facing state/events example

```powershell
python examples/app_state_events.py --provider openai --model gpt-4o-mini --message "こんにちは。1文で短く返して。"
```

### Interrupt boundary example

```powershell
python examples/app_interrupt_text_chat.py --provider openai --model gpt-4o-mini
```

`interrupt()` is a limited public boundary in v4.0.0. It does not guarantee provider-level hard cancellation, TTS queue cancellation, or realtime voice barge-in.

---

## Demo applications

- [Daily Rhythm Companion (DRC)](https://github.com/murayan1982/daily-rhythm-companion-public) — A public demo application for AI-Character-Framework integration. DRC demonstrates host-app integration patterns around Flutter/FastAPI, character-side app orchestration, daily advice flow, and public FW voice/text boundaries.

## Runtime modes

### Full runtime

Use the full runtime when you want text, voice, TTS, Live2D, emotion parsing, and plugins to run through the normal application loop.

```bash
python main.py
```

Or use the provided run scripts, such as:

```text
run.bat
scripts/run_text_chat.bat
scripts/run_text_vts.bat
scripts/run_voice_vts.bat
```

### Framework API

Use the public facade when you want a lightweight framework API for text chat integration.

```python
from framework import create_text_chat_session

session = create_text_chat_session()
print(session.ask("Hello."))
```

---

## Current features

- Multi-LLM support: Gemini, Grok, and OpenAI
- Automatic routing between chat/code style usage
- Fallback handling
- Voice input through STT
- Voice output through TTS
- Optional Live2D / VTube Studio integration
- Emotion tag generation and parsing
- Character-level VTS hotkey mapping
- Plugin-based VTS emotion handling
- Hook and plugin extension points
- Public text chat facade for framework-style usage
- Facade-level provider/model selection for app integration
- Public facade error classes for application boundary handling
- Public text chat session metadata through `session.info`
- Public text chat interrupt boundary through `session.interrupt()`
- App-facing text session events through `session.on_event()` and `session.on_state_change()`
- App integration examples for error handling, streaming, reset, session info, state/events, and interrupt handling
- Explicit runtime conversation state tracking
- Plugin-facing state change events
- Voice-friendly output policy for TTS-enabled sessions
- Interruption-ready runtime boundaries for future barge-in work

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

- Hooks are event-style extension points used inside the runtime flow
- Plugins are lifecycle-oriented extensions used for setup, startup, shutdown, and integration behavior

This keeps the core runtime small while making it easier to add logging, integrations, or custom runtime behavior.

For runtime event hooks such as `on_state_change`, see [Plugin Runtime Events](docs/plugin_events.md).

---

## Character customization

Character-related files define who the character is. Preset and runtime settings define how the framework runs.

A character is managed as one directory under `characters/`.

```text
characters/
  default/
    profile.json
    system.txt
    vts_hotkeys.json
```

Character files:

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

A simple rule:

- Character = who the assistant is
- Preset / Runtime = how the framework runs

Examples:

- Change speaking style -> character (`system.txt`)
- Change displayed name / description -> character (`profile.json`)
- Change emotion-to-VTS mapping -> character (`vts_hotkeys.json`)
- Change selected character -> preset (`character_name`)
- Change text/voice mode -> preset (`presets/*.json`)

---

## Adding a new character

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

## Runtime configuration

Runtime behavior is controlled mainly by:

- `APP_PRESET`
- `presets/*.json`
- character files under `characters/*`

Character files and runtime settings have different responsibilities.

- `characters/*` defines who the character is
- `APP_PRESET` and `presets/*.json` define how the framework runs
- `RuntimeConfig` is assembled from both and becomes the runtime source of truth

Configuration flow:

1. `.env` selects the startup preset through `APP_PRESET`
2. `presets/*.json` defines the runtime mode
3. `characters/*` provides character-specific differences
4. `config/loader.py` assembles `RuntimeConfig`
5. Runtime behavior reads from `RuntimeConfig` as the source of truth

---

## Developer flow

For regular development, start from the smallest working setup and then add features step by step.

Recommended flow:

1. Start with `APP_PRESET=text_chat`
2. Confirm the basic text conversation flow
3. Customize the character under `characters/*`
4. Switch to `text_vts` for Live2D expression checks
5. Switch to `voice_vts` for voice + Live2D checks
6. Edit registry files only when you want to change LLM or TTS definitions

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

- `framework/`
  - Provides the public facade for framework-style usage

- `examples/`
  - Provides small examples for public facade and app integration usage

A simple rule:

- Change who the assistant is -> edit `characters/*`
- Change how the framework runs -> edit `.env` or `presets/*.json`
- Change provider definitions -> edit `registry/*`

---

## Validation and smoke checks

Current v6 documentation and aggregate gates are provider-free:

```bash
python scripts/check_v600_documentation_freeze.py
python scripts/check_v600_aggregate_conformance.py --source-only
python -m unittest discover -s tests
```

The documentation checker verifies the exact FW-RT6-14b surface and invokes the
aggregate contract, including the complete 828-test unit suite. It does not read
private configuration/evidence or execute provider, network, microphone, playback,
or VTS operations.

Compile check:

```bash
python -m compileall -q .
```

Runtime boundary checks:

```bash
python scripts/test_prompt_builder.py
python scripts/test_interruption_state.py
python scripts/test_tts_stop_boundary.py
python scripts/test_runtime_state_flow.py
python scripts/test_session_interrupt_command.py
```

LLM registry validation:

```bash
python -c "from llm.builder import validate_llm_registry; validate_llm_registry(); print('LLM registry OK')"
```

Public facade smoke check:

```bash
python scripts/smoke_public_facade.py
```

App SDK boundary smoke check:

```bash
python scripts/smoke_app_sdk.py
```

Live one-turn facade check:

```bash
python scripts/smoke_public_facade.py --provider openai --model gpt-4o-mini --ask "こんにちは。短く返して"
```

Basic offline-safe example checks:

```bash
python examples/app_error_handling.py
python examples/public_text_chat.py
python examples/minimal_app_text_chat.py
```

Optional app integration examples that may create provider clients and require API keys:

```bash
python examples/app_streaming_text_chat.py
python examples/app_reset_text_chat.py
python examples/app_session_info.py
python examples/app_state_events.py
python examples/app_interrupt_text_chat.py
```

---

## Project structure

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
  factory.py
  router_llm.py
  fallback_llm.py
  gemini_engine.py
  grok_engine.py
  openai_engine.py

live2d/
  vts_client.py

plugins/
  base.py
  manager.py
  builtin/
  samples/

config/
  loader.py
  prompt_builder.py
  secrets.py
  defaults.py
  legacy.py

registry/
  llm.py
  tts.py

framework/
  __init__.py
  facade.py

examples/
  public_text_chat.py
  minimal_app_text_chat.py
  app_error_handling.py
  app_streaming_text_chat.py
  app_reset_text_chat.py
  app_session_info.py
  app_state_events.py
  app_interrupt_text_chat.py

scripts/
  smoke_public_facade.py
  smoke_app_sdk.py
  test_prompt_builder.py
  test_interruption_state.py
  test_tts_stop_boundary.py
  test_runtime_state_flow.py
  test_session_interrupt_command.py

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

## Documentation

Detailed documentation is split by responsibility:

- `docs/public_facade.md`
  - Frozen public facade, compatibility, capability, event, and ownership details

- `docs/app_integration_contract.md`
  - External app integration and host-owned execution boundaries

- `docs/advanced_runtime.md`
  - v6 runtime profiles, lifecycle, interruption, TTS work, playback, and security

- `docs/v600_v5_to_v6_session_migration.md`
  - Capability-first migration from retained v5 standalone sessions to v6

- `docs/v600_capability_event_error_reference.md`
  - Frozen capability fields, event types, outcomes, errors, and recovery actions

- `docs/v600_aggregate_conformance.md`
  - Provider-free v6 aggregate conformance contract and current smoke classification

- `docs/v600_tasklist.md`
  - Append-only v6 implementation and acceptance history

- `docs/plugin_events.md`
  - Runtime plugin event hooks such as `on_state_change`

- `docs/voice_output_policy.md`
  - TTS-friendly output policy design for voice-enabled sessions

- `docs/RELEASE_NOTES.md`
  - Current release notes

- `docs/release_package_policy.md`
  - Public release package include / exclude rules

- `docs/roadmap_feature_v4.0.0.md`
  - App Integration SDK Foundation roadmap

- `docs/roadmap_feature_v5.0.0.md`
  - Public Voice Output / TTS Boundary Foundation roadmap

- `docs/voice_output_real_tts_opt_in_checklist.md`
  - Real TTS opt-in boundary and mock-safe provider behavior

- `docs/voice_output_artifact_result_contract.md`
  - App-safe voice output handoff result contract

- `docs/voice_output_real_provider_execution_guard.md`
  - Guard required before FW can call a real TTS provider

- `docs/voice_output_v500_release_readiness_checklist.md`
  - v5.0.0 mock-safe release readiness criteria

- `docs/host_app_voice_output_integration_handoff.md`
  - General host app voice output integration handoff

- `docs/voice_output_v500_package_readiness.md`
  - v5.0.0 package readiness and final verification command set

The top of this README is the current project entry point. The material after the
`Historical development log (append-only)` heading is retained source evidence and
must not be used as the current setup, API, test-count, or release-status contract.
Published release details remain in `docs/RELEASE_NOTES.md`, Git tags, and GitHub
Releases.

---

## Roadmap

Current major roadmap topics are tracked in:

```text
docs/roadmap_feature_v4.0.0.md
docs/roadmap_feature_v5.0.0.md
docs/roadmap_feature_v6.0.0.md
```

v4.0.0 focuses on App Integration SDK Foundation:

- stable public text session APIs
- app-safe session metadata
- reset and limited interrupt boundaries
- app-facing event callbacks
- SDK examples and documentation

v5.0.0 focuses on Public Voice Output / TTS Boundary Foundation:

- mock-safe public voice output boundary for host apps
- provider-neutral `VoiceOutputRequest` / `VoiceOutputResult` contract
- lazy provider adapter and explicit real provider execution guard
- app-safe audio handoff semantics for `audio_url` / `audio_artifact_ref`
- host app integration guidance before deeper realtime voice runtime work

v5.0.0 is not the full realtime voice runtime release. Realtime interruption, stronger TTS stop/flush behavior, and always-on microphone / barge-in work remain follow-up runtime topics.

v6.0.0 freezes a provider-neutral realtime foundation:

- shared session, turn, generation, event, and terminal semantics;
- capability-first integration and typed unavailability;
- cooperative interruption, TTS work control, and stale-result rejection;
- explicit host ownership of microphone capture and physical playback;
- retained v5 standalone compatibility profiles;
- guarded real-runtime composition and provider-free aggregate conformance.

The source candidate is documentation frozen but not released. FW-RT6-14c package,
release, tag, and publication work remains separately gated and is not authorized by
the FW-RT6-14b documentation freeze.

---

## Repository naming

Repository name:

```text
ai-character-framework
```

Project / README title:

```text
AI Character Conversation Framework
```

This keeps the repository name short and practical while making the full project purpose clearer in the documentation.

---

## License

Please see `LICENSE.txt` for the full license terms.

This project may be used as a component in larger applications, including commercial products and services, as long as the use follows the license terms.

Redistribution, repackaging, or resale of the framework itself as a standalone product, starter kit, template, boilerplate, or similar package is restricted by the license.

<!-- README-HISTORICAL-DEVELOPMENT-LOG:BEGIN -->
## Historical development log (append-only)

Everything below this heading is preserved chronological implementation evidence.
It may describe older versions, baselines, test counts, authorization states, or
future plans that have since changed. Use the current v6 section and linked frozen
documents above for present behavior.

### v5.1.0 release readiness gate

Before creating v5.1.0 release artifacts, run:

```bash
python scripts/smoke_v510_release_readiness_gate.py
```

The gate is mock-safe. It does not call real provider APIs, generate real voice
artifacts, or create release tags/archives.

## v5.1.0 fixed release package verification

Before using the generated v5.1.0 release package as host app handoff evidence,
run:

```powershell
python scripts/smoke_v510_fixed_release_package_verification.py
```

This builds the local fixed release package, verifies the manifest and zip
hygiene, extracts the package outside the repository root, and imports the
public framework API from a host-app-like working directory. The check is
mock-safe and does not publish a release or create a tag.

### v5.1.0 final release tag readiness

Before creating the `v5.1.0` tag, run the final mock-safe release tag
readiness gate:

```powershell
python scripts/smoke_v510_final_release_tag_readiness.py --require-clean-tree --expected-tag v5.1.0
```

The generated `release/ai-character-framework_v5.1.0.zip` and manifest are
local release artifacts/evidence and are not intended to be committed.

### v5.1.0 release notes

The v5.1.0 release notes are available in
[`docs/release_notes_v5.1.0.md`](docs/release_notes_v5.1.0.md).

They summarize the Installable SDK / Stable Host App Integration Boundary
release, including public contract inventory, typed Text Chat results, Voice
Output `speak()`, capability snapshots, FW-owned provider config, session
lifecycle, opaque voice artifacts, package import readiness, fixed release
package verification, and release artifact policy.

### v5.2.0 planning roadmap

The next framework development cycle is tracked in
[`docs/roadmap_feature_v5.2.0.md`](docs/roadmap_feature_v5.2.0.md).

This roadmap is driven by DRC RT-1 requirements and prioritizes public
voice-input / STT session contracts, unified realtime lifecycle/events, hard
cancel / TTS queue / flush / barge-in behavior, and public motion / Live2D /
VTube Studio adapter boundaries before returning to DRC.

### v5.2.0 voice-input / STT inventory

The first v5.2.0 implementation track is the public voice-input / STT session
boundary.

Inventory notes are recorded in
[`docs/v520_voice_input_stt_inventory.md`](docs/v520_voice_input_stt_inventory.md).

The goal is to prevent DRC and other host apps from depending on FW internal STT
modules, provider-specific clients, raw audio paths, token files, or temporary
checkout-layout workarounds.

### v5.2.0 public voice-input types

v5.2.0 begins the public voice-input / STT boundary with provider-neutral public
types:

- `VoiceInputOutcome`
- `VoiceInputErrorCode`
- `VoiceInputRequest`
- `VoiceInputResult`

See [`docs/v520_voice_input_public_types.md`](docs/v520_voice_input_public_types.md).

### v5.2.0 public voice-input session skeleton

v5.2.0 now includes a mock-safe public voice-input session skeleton:

- `create_voice_input_session(...)`
- `VoiceInputSession`
- `VoiceInputSessionInfo`

The session exposes `listen_result(...)`, `text_fallback_result(...)`,
`on_event(...)`, `close()`, `dispose()`, `is_closed`, and context manager
support without executing real STT providers by default.

See [`docs/v520_voice_input_session_skeleton.md`](docs/v520_voice_input_session_skeleton.md).

### v5.2.0 voice-input capability preflight

v5.2.0 now includes a public voice-input / STT capability preflight:

- `VoiceInputProviderStatus`
- `VoiceInputProviderConfig`
- `VoiceInputCapabilities`
- `resolve_voice_input_provider_config(...)`
- `get_voice_input_capabilities(...)`

The preflight reports disabled, missing credential, guard-blocked, unsupported,
or not-yet-implemented real STT status without importing provider SDKs or
executing real providers.

See [`docs/v520_voice_input_capability_preflight.md`](docs/v520_voice_input_capability_preflight.md).

### v5.2.0 voice-input session preflight wiring

`VoiceInputSession` now uses the public capability preflight internally.

A session exposes:

- `session.capabilities`
- `session.info.provider_status`
- status-specific `listen_result(...)` unavailable results

See [`docs/v520_voice_input_session_preflight_wiring.md`](docs/v520_voice_input_session_preflight_wiring.md).

### v5.2.0 voice-input host-app examples

Mock-safe public voice-input examples are available:

- `examples/app_voice_input_capability_preflight.py`
- `examples/app_voice_input_session_text_fallback.py`
- `examples/app_voice_input_missing_credentials.py`

They demonstrate capability preflight, public session text fallback, and typed
missing-credential handling without importing FW internals or STT provider SDKs.

See [`docs/v520_voice_input_host_app_examples.md`](docs/v520_voice_input_host_app_examples.md).

### v5.2.0 voice-input public contract conformance gate

A mock-safe conformance gate now verifies the public voice-input / STT boundary:

- public exports
- provider-safe `import framework`
- keyword-only `create_voice_input_session(...)`
- typed request/result helpers
- capability preflight
- session lifecycle and events
- public-only host-app examples

See [`docs/v520_voice_input_public_contract_conformance_gate.md`](docs/v520_voice_input_public_contract_conformance_gate.md).

### v5.2.0 realtime lifecycle / event inventory

Priority 2 of the DRC-driven v5.2.0 work is the unified realtime lifecycle /
event contract.

Inventory notes are recorded in
[`docs/v520_realtime_lifecycle_event_inventory.md`](docs/v520_realtime_lifecycle_event_inventory.md).

The goal is to give DRC one stable public event surface across voice input, text
chat, voice output, future motion, interruption, failure, and cleanup states.

### v5.2.0 public realtime lifecycle event types

v5.2.0 now begins the unified realtime lifecycle / event contract with
provider-neutral public types:

- `RealtimeState`
- `RealtimeEventType`
- `RealtimeErrorCode`
- `RealtimeEvent`
- `RealtimeTurn`
- `RealtimeTurnResult`

See [`docs/v520_realtime_lifecycle_event_types.md`](docs/v520_realtime_lifecycle_event_types.md).

### v5.2.0 public realtime session skeleton

v5.2.0 now includes a mock-safe public realtime session skeleton:

- `create_realtime_session(...)`
- `RealtimeSession`
- `RealtimeSessionInfo`

The session exposes `on_event(...)`, `emit_created()`, `run_turn(...)`,
`close()`, `dispose()`, `is_closed`, `state`, `info`, and context manager support
without executing real STT / LLM / TTS / motion providers by default.

See [`docs/v520_realtime_session_skeleton.md`](docs/v520_realtime_session_skeleton.md).

### v5.2.0 realtime host-app examples

Mock-safe public realtime examples are available:

- `examples/app_realtime_session_event_flow.py`
- `examples/app_realtime_event_payload_mapping.py`
- `examples/app_realtime_closed_session_behavior.py`

They demonstrate public event callbacks, event payload mapping, and
closed-session behavior without importing FW internals or realtime provider SDKs.

See [`docs/v520_realtime_host_app_examples.md`](docs/v520_realtime_host_app_examples.md).

### v5.2.0 realtime public contract conformance gate

A mock-safe conformance gate now verifies the public realtime lifecycle / event
boundary:

- public exports
- provider-safe `import framework`
- keyword-only `create_realtime_session(...)`
- lifecycle/event/turn types
- session lifecycle and deterministic events
- public-only host-app examples

See [`docs/v520_realtime_public_contract_conformance_gate.md`](docs/v520_realtime_public_contract_conformance_gate.md).

### v5.2.0 hard cancel / TTS queue / flush / barge-in inventory

Priority 3 of the DRC-driven v5.2.0 work is the public interruption and output
control contract.

Inventory notes are recorded in
[`docs/v520_cancel_tts_queue_barge_in_inventory.md`](docs/v520_cancel_tts_queue_barge_in_inventory.md).

The goal is to give DRC provider-neutral public controls for current-turn
interruption, LLM/TTS cancellation where supported, TTS queue flush, output stop
handoff, and barge-in policy handling without depending on FW internals.

### v5.2.0 public interrupt / output control types

v5.2.0 now begins the hard cancel / TTS queue / flush / barge-in boundary with
provider-neutral public types:

- `InterruptScope`
- `InterruptReason`
- `InterruptOutcome`
- `InterruptRequest`
- `InterruptResult`
- `TTSQueueState`
- `OutputFlushOutcome`
- `OutputFlushRequest`
- `OutputFlushResult`
- `BargeInPolicyMode`
- `BargeInPolicy`
- `BargeInDecision`

See [`docs/v520_interrupt_output_control_types.md`](docs/v520_interrupt_output_control_types.md).

### v5.2.0 realtime interrupt / output-control wiring

`RealtimeSession` now exposes mock-safe public output-control methods:

- `get_tts_queue_state()`
- `interrupt(...)`
- `cancel_current_turn(...)`
- `flush_output(...)`
- `set_barge_in_policy(...)`
- `decide_barge_in(...)`

The methods return typed provider-neutral results and do not overclaim real hard
cancel, real queue flush, playback stop, or provider cancellation support.

See [`docs/v520_realtime_interrupt_output_control_wiring.md`](docs/v520_realtime_interrupt_output_control_wiring.md).

### v5.2.0 interrupt / output-control host-app examples

Mock-safe public interrupt / output-control examples are available:

- `examples/app_realtime_interrupt_handling.py`
- `examples/app_realtime_output_flush_handling.py`
- `examples/app_realtime_barge_in_policy.py`

They demonstrate typed interrupt results, empty-queue output flush results, and
barge-in policy decisions without importing FW internals or provider SDKs.

See [`docs/v520_interrupt_output_control_host_app_examples.md`](docs/v520_interrupt_output_control_host_app_examples.md).

### v5.2.0 interrupt / output-control public contract conformance gate

A mock-safe conformance gate now verifies the public hard cancel / TTS queue /
flush / barge-in boundary:

- public exports
- provider-safe `import framework`
- interrupt / output flush / barge-in public types
- `RealtimeSession` output-control methods
- honest capability flags
- public realtime events
- public-only host-app examples

See [`docs/v520_interrupt_output_control_public_contract_conformance_gate.md`](docs/v520_interrupt_output_control_public_contract_conformance_gate.md).

### v5.2.0 motion / Live2D / VTS adapter inventory

Priority 4 of the DRC-driven v5.2.0 work is the public motion / Live2D /
VTube Studio adapter contract.

Inventory notes are recorded in
[`docs/v520_motion_live2d_vts_adapter_inventory.md`](docs/v520_motion_live2d_vts_adapter_inventory.md).

The goal is to give DRC provider-neutral public motion controls for expression,
emotion, speaking state, gesture, look direction, stop/reset behavior, and
adapter preflight without depending on FW internals, VTS WebSocket state, token
files, or private model paths.

### v5.2.0 public motion adapter types

v5.2.0 now begins the public motion / Live2D / VTube Studio adapter boundary with
provider-neutral public types:

- `MotionAdapterStatus`
- `MotionState`
- `MotionEventType`
- `MotionErrorCode`
- `MotionIntent`
- `MotionOutcome`
- `MotionCapability`
- `MotionRequest`
- `MotionResult`

See [`docs/v520_motion_adapter_types.md`](docs/v520_motion_adapter_types.md).

### v5.2.0 public motion session skeleton

v5.2.0 now includes a mock-safe public motion session skeleton:

- `create_motion_session(...)`
- `MotionSession`
- `MotionSessionInfo`

The session exposes `preflight()`, `apply_motion(...)`, `on_event(...)`,
`emit_created()`, `close()`, `dispose()`, `is_closed`, `state`, `info`,
`capability`, and context manager support without connecting to real Live2D or
VTube Studio by default.

See [`docs/v520_motion_session_skeleton.md`](docs/v520_motion_session_skeleton.md).

### v5.2.0 motion host-app examples

Mock-safe public motion examples are available:

- `examples/app_motion_session_expression_flow.py`
- `examples/app_motion_adapter_preflight.py`
- `examples/app_motion_closed_session_behavior.py`
- `examples/app_motion_real_adapter_guard.py`

They demonstrate public motion session usage, adapter preflight, closed-session
behavior, and real-adapter guard handling without importing FW internals or
provider SDKs.

See [`docs/v520_motion_host_app_examples.md`](docs/v520_motion_host_app_examples.md).

### v5.2.0 motion public contract conformance gate

A mock-safe conformance gate now verifies the public motion / Live2D / VTS
adapter boundary:

- public exports
- provider-safe `import framework`
- motion adapter types
- `create_motion_session(...)`
- `MotionSession` lifecycle, preflight, events, and results
- honest real-adapter guard / not-implemented behavior
- public-only host-app examples

See [`docs/v520_motion_public_contract_conformance_gate.md`](docs/v520_motion_public_contract_conformance_gate.md).

### v5.2.0 release readiness gate

A source-tree release readiness gate now verifies the DRC-driven v5.2.0 public
runtime contracts before fixed release packaging begins.

The gate covers:

- public voice-input / STT session
- unified realtime lifecycle / event contract
- hard cancel / TTS queue / flush / barge-in public control
- public motion / Live2D / VTS adapter

See [`docs/v520_release_readiness_gate.md`](docs/v520_release_readiness_gate.md).

### v5.2.0 fixed release package builder

A fixed release package builder is available for v5.2.0:

```powershell
python scripts/build_v520_release_package.py
```

It runs the v5.2.0 release readiness gate, requires a clean working tree by
default, creates a deterministic zip, embeds `RELEASE_MANIFEST_v5.2.0.json`, and
writes a SHA-256 sidecar.

See [`docs/v520_fixed_release_package_builder.md`](docs/v520_fixed_release_package_builder.md).

### v5.2.0 fixed release package verification

A fixed release package verifier is available for v5.2.0:

```powershell
python scripts/verify_v520_release_package.py
```

It verifies the package SHA-256 sidecar, deterministic zip structure, embedded
`RELEASE_MANIFEST_v5.2.0.json`, release-safe exclusions, manifest file hashes,
and required public runtime contract files.

See [`docs/v520_fixed_release_package_verification.md`](docs/v520_fixed_release_package_verification.md).

### v5.2.0 final release tag readiness

A final tag-readiness gate is available for v5.2.0:

```powershell
python scripts/smoke_v520_final_release_tag_readiness.py --require-package
```

It verifies the release readiness gate, fixed package builder smoke, fixed package
verification smoke, package tooling, git state, tag availability, and optionally
the final fixed package before creating `v5.2.0`.

See [`docs/v520_final_release_tag_readiness.md`](docs/v520_final_release_tag_readiness.md).

## v5.3.0 development: Public Voice Input / Real STT Provider Boundary

v5.3.0 begins the real STT provider boundary work needed by DRC RT-3.

Current checkpoint:

```text
STT-1a: ACCEPTED
STT-1b: READY pending next small commit
```

See:

- [`docs/roadmap_feature_v5.3.0.md`](docs/roadmap_feature_v5.3.0.md)
- [`docs/v530_real_stt_provider_boundary_inventory.md`](docs/v530_real_stt_provider_boundary_inventory.md)
- [`docs/v530_real_stt_small_commit_checklist.md`](docs/v530_real_stt_small_commit_checklist.md)

## v5.3.0 STT-1b host-audio source contract

STT-1b adds a provider-neutral public contract for host-captured audio handoff:

- `VoiceInputAudioSourceKind`
- `VoiceInputAudioEncoding`
- `VoiceInputAudioFormat`
- `VoiceInputAudioRef`
- `VoiceInputAudioSource`

See [`docs/v530_host_audio_source_contract.md`](docs/v530_host_audio_source_contract.md).

### v5.3.0 STT-1b acceptance status

```text
STT-1b: ACCEPTED
STT-1c: READY pending next small commit
```

STT-1b added only a provider-neutral host-captured audio source contract. It did
not read audio, access microphones, execute providers, or change DRC.

## v5.3.0 STT-1c lazy provider adapter + fake adapter

STT-1c adds a lazy provider adapter protocol and fake adapter:

- `VoiceInputProviderAdapter`
- `VoiceInputProviderAdapterInfo`
- `FakeVoiceInputProviderAdapter`

See [`docs/v530_lazy_provider_adapter_fake.md`](docs/v530_lazy_provider_adapter_fake.md).

### v5.3.0 STT-1c acceptance status

```text
STT-1c: ACCEPTED
STT-1d: READY pending next small commit
```

STT-1c added only a lazy provider adapter protocol and fake adapter. It did not
read audio, access microphones, execute real providers, or change DRC.

## v5.3.0 STT-1d VoiceInputSession adapter wiring

STT-1d wires host-captured audio and lazy adapters into the public
`VoiceInputSession` boundary:

- `VoiceInputSession.transcribe_audio_result(...)`
- `VoiceInputSession.listen_audio_result(...)`

See [`docs/v530_voice_input_session_adapter_wiring.md`](docs/v530_voice_input_session_adapter_wiring.md).

### v5.3.0 STT-1d acceptance status

```text
STT-1d: ACCEPTED
STT-1e: READY pending next small commit
```

STT-1d wired host-captured audio and lazy adapters into public
`VoiceInputSession` methods. It did not read audio, access microphones, execute
real providers, or change DRC.

## v5.3.0 STT-1e guarded real provider adapter

STT-1e adds the first guarded real-provider adapter boundary:

- `GuardedRealVoiceInputProviderAdapter`

The adapter exposes typed guard behavior for provider execution opt-in,
missing credentials, and real-STT-not-implemented status.

See [`docs/v530_guarded_real_provider_adapter.md`](docs/v530_guarded_real_provider_adapter.md).

### v5.3.0 STT-1e acceptance status

```text
STT-1e: ACCEPTED
STT-1f: READY pending next small commit
```

STT-1e added a guarded real-provider adapter boundary. It reports typed guard
outcomes for provider execution not allowed, missing credentials, and real STT
not implemented. It did not import provider SDKs, read API keys, read audio,
access microphones, execute real providers, or change DRC.

## v5.3.0 STT-1f DRC public handoff verification

STT-1f verifies the DRC-facing public handoff shape:

```text
DRC host app capture -> opaque/private audio source -> FW public VoiceInputSession -> lazy adapter -> typed VoiceInputResult
```

See [`docs/v530_drc_public_handoff_verification.md`](docs/v530_drc_public_handoff_verification.md) and
[`examples/voice_input_drc_public_handoff.py`](examples/voice_input_drc_public_handoff.py).

### v5.3.0 STT-1f acceptance status

```text
STT-1f: ACCEPTED
v5.3.0 release readiness: READY pending next small commit
```

STT-1f verified the DRC-facing public handoff shape using only public framework
imports. It did not change DRC, read audio, access microphones, execute real
providers, read API keys, create a release package, or create a tag.

## v5.3.0 release readiness gate

The v5.3.0 source-tree release readiness gate checks all accepted STT-1a through
STT-1f public voice-input / real STT provider boundary checkpoints.

See [`docs/v530_release_readiness_gate.md`](docs/v530_release_readiness_gate.md).

Current status:

```text
v5.3.0 release readiness: IMPLEMENTED / NOT_ACCEPTED
v5.3.0 release package/tag: BLOCKED pending release readiness acceptance
```

### v5.3.0 release readiness acceptance status

```text
v5.3.0 release readiness: ACCEPTED
v5.3.0 release package/tag: READY pending next small commit
```

The source-tree release readiness gate passed after accepted STT-1a through
STT-1f checkpoints. This did not create a release package, tag, or remote push.
Real provider execution remains unimplemented and DRC RT-3 remains blocked
pending real provider execution.

## v5.3.0 release package gate

The v5.3.0 release package gate adds a deterministic source package builder:

```text
scripts/build_v530_release_package.py
scripts/smoke_v530_release_package_gate.py
```

The final package target is:

```text
release/ai-character-framework_v5.3.0.zip
release/ai-character-framework_v5.3.0.zip.sha256
```

See [`docs/v530_release_package_gate.md`](docs/v530_release_package_gate.md).

Current status:

```text
v5.3.0 release package gate: IMPLEMENTED / NOT_ACCEPTED
v5.3.0 tag/push: BLOCKED pending release package acceptance
```

### v5.3.0 release package gate acceptance status

```text
v5.3.0 release package gate: ACCEPTED
v5.3.0 tag/push: READY pending final release package build
```

The package gate dry-run passed and confirmed the package set excludes local
VS Code settings, private/operator evidence, env files, and generated release
artifacts. This did not create the final `release/` package, tag, or remote push.

## v5.4.0 candidate development: Real STT Provider Execution

v5.4.0 is the candidate next Framework development line for explicit real STT provider execution through the public Voice Input API.

The requirements are driven by DRC v3.0.0 RT-3d, which remains blocked until a released Framework version can execute a real STT provider from a DRC-owned private WAV through public APIs and return a provider-neutral typed transcript.

See:

- [`docs/v540_real_stt_provider_execution_requirements.md`](docs/v540_real_stt_provider_execution_requirements.md)
- [`docs/v540_real_stt_provider_execution_small_commit_checklist.md`](docs/v540_real_stt_provider_execution_small_commit_checklist.md)

Current status:

```text
requirements definition: ACCEPTED
implementation: NOT_STARTED
private real-provider acceptance: NOT_STARTED
release readiness: BLOCKED pending implementation acceptance
```
## v5.4.0 candidate REQ-1 provider execution configuration and status

REQ-1 adds a separate explicit-only configuration snapshot for later real STT
provider execution:

- `VoiceInputProviderExecutionConfig`
- `resolve_voice_input_provider_execution_config`
- `get_voice_input_provider_execution_status`

It records explicit opt-in, provider configuration, credential availability,
and conservative capability status without reading credential values, importing
provider SDKs, creating clients, reading audio, opening microphones, or executing
STT.

See
[`docs/v540_provider_execution_configuration_status.md`](docs/v540_provider_execution_configuration_status.md).

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```
## v5.4.0 candidate REQ-2 OpenAI adapter/client-injection contract

REQ-2 adds the first concrete provider-specific voice-input adapter contract:

- `OpenAIVoiceInputProviderAdapter`
- `OpenAIVoiceInputClient`
- `OpenAIVoiceInputClientFactory`
- `OpenAIVoiceInputPreflight`
- `OpenAIVoiceInputPreflightStatus`

The selected later execution boundary is
`client.audio.transcriptions.create(...)`, but REQ-2 does not call it.

REQ-2 validates only explicit configuration and public source metadata:
FILE_PATH, WAV, and a host-provided duration bound. It does not import the
OpenAI SDK, invoke a client factory, read credentials, open an audio file,
access a microphone, execute a provider, or change DRC.

See
[`docs/v540_openai_adapter_client_injection_contract.md`](docs/v540_openai_adapter_client_injection_contract.md).

```text
REQ-1: ACCEPTED
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```
## v5.4.0 candidate REQ-3 bounded audio / fake execution boundary

REQ-3 adds a bounded FILE_PATH reader and a provider-shaped execution path
that can call only a directly injected client inheriting
`OpenAIVoiceInputFakeClientMarker`.

The host must explicitly provide:

- `allow_fake_client_execution=True`
- a positive `max_audio_bytes`
- the accepted REQ-2 FILE_PATH/WAV/duration-bound source contract
- a directly injected marked fake client

Client factories, unmarked clients, oversized files, missing files, and
non-regular files are rejected without execution.

REQ-3 may read bounded local bytes and call the marked fake client's
`client.audio.transcriptions.create(...)`. It does not import the OpenAI SDK,
read credential values, create a provider client, execute a real provider,
access a microphone, expose paths/raw audio/provider payloads, or change DRC.

See
[`docs/v540_openai_fake_execution_boundary.md`](docs/v540_openai_fake_execution_boundary.md).

```text
REQ-2: ACCEPTED
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```
## v5.4.0 candidate REQ-4 lazy OpenAI real-provider runtime

REQ-4 adds the first concrete real-provider runtime:

- `OpenAIVoiceInputPrivateCredential`
- `OpenAIVoiceInputRealProviderPolicy`
- `OpenAIVoiceInputRealClientFactory`
- `OpenAIVoiceInputRealProviderExecutor`

The OpenAI SDK, client creation, and real execution each have separate
false-by-default host-controlled gates. The Framework does not read credential
environment variables. A private credential is explicitly injected and
redacted from representations and public results.

The actual SDK is imported lazily only after every gate passes. The call shape
is `client.audio.transcriptions.create(...)`, using the accepted bounded
FILE_PATH/WAV contract and a sanitized in-memory `audio.wav` object.

REQ-4 smoke uses an injected SDK test double. It does not import the actual SDK,
create an actual provider client, use a real credential, or execute a network
request.

See
[`docs/v540_openai_real_provider_runtime.md`](docs/v540_openai_real_provider_runtime.md).

```text
REQ-3: ACCEPTED
REQ-4: ACCEPTED
REQ-5: IMPLEMENTED / NOT_ACCEPTED
release readiness: BLOCKED pending REQ-5 acceptance
```
\

## v5.4.0 candidate REQ-5 private real-provider operator acceptance

REQ-5 adds operator-only tooling for the first actual OpenAI transcription
acceptance run.

The source commit adds:

- a private operator runner;
- an outside-repository evidence format;
- a private evidence validator;
- network-free source/operator smoke checks.

The operator requires a private WAV, private credential, explicit execution
confirmation, and private evidence root outside the repository. It uses the
accepted REQ-4 public runtime and stores the full transcript only in a private
outside-repository file.

The operator console and committed files exclude credential values, private
paths, raw audio, complete transcript text, provider payloads, and exception
details. A temporary staged WAV is deleted after the provider call.

See
[`docs/v540_openai_private_real_provider_operator_acceptance.md`](docs/v540_openai_private_real_provider_operator_acceptance.md).

```text
REQ-4: ACCEPTED
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

### REQ-5 accepted private evidence checkpoint

A private operator run completed with the actual OpenAI SDK, an actual provider
client, real provider execution, a real transcript, and a provider-neutral
Framework result. The public-safe validator accepted the private evidence.

The API key, private WAV path, raw audio, provider payload, transcript text,
private evidence JSON, and private run details were not committed. Private
evidence remained outside the repository, private staged audio cleanup was
verified, the worktree remained clean before and after the run, the microphone
was not accessed, and DRC was not changed.

```text
v540_req5_private_evidence_status: accepted-by-validator
v540_req5_public_acceptance_sync_status: accepted
v540_req5_release_readiness_authorization: ready-for-next-small-commit
REQ-5: ACCEPTED
release readiness: READY pending next small commit
```

\
## v5.4.0 release readiness gate

The v5.4.0 source-tree release-readiness gate aggregates the accepted REQ-1
through REQ-5 checks, v5.3.0 and v5.2.0 release-readiness regressions, and the
baseline release-package check:

```powershell
python scripts\smoke_v540_release_readiness_gate.py
```

The gate relies only on committed public acceptance markers. The private WAV,
transcript, evidence JSON, API key, private paths, and provider response remain
outside the repository and are not read by the gate.

```text
v5.4.0 release readiness: ACCEPTED
v5.4.0 release package/tag: READY pending next small commit
v540_release_readiness_gate_status: accepted
v540_req5_private_evidence_status: accepted-by-validator
v540_release_package_authorization: ready-for-release-package-gate
```

This checkpoint does not import the actual OpenAI SDK, read private evidence,
execute a network request, access the microphone, modify DRC, create the release
package, create a tag, push, or publish.

See
[`docs/v540_release_readiness_gate.md`](docs/v540_release_readiness_gate.md).

\
## v5.4.0 release package gate

The deterministic v5.4.0 package builder creates a source ZIP from the sorted
git-tracked public file set:

```powershell
python scripts\build_v540_release_package.py --dry-run
python scripts\smoke_v540_release_package_gate.py
```

The package gate builds twice in temporary directories and verifies identical
SHA-256 digests, ZIP integrity, exact archive membership, and exclusion of
local/private/generated artifacts.

```text
v5.4.0 release package gate: ACCEPTED
v5.4.0 tag/push: READY pending final release package build
v540_release_package_gate_status: accepted
v540_release_package_deterministic: True
v540_tag_authorization: ready-for-final-release-package-build
```

This checkpoint does not create the final release package, checksum sidecar,
tag, push, or GitHub Release. It also does not import the actual OpenAI SDK,
read private evidence/audio/transcripts or an API key, execute a real provider,
access the microphone, or modify DRC.

See
[`docs/v540_release_package_gate.md`](docs/v540_release_package_gate.md).

## v5.4.0 final release tag readiness

The final pre-tag gate verifies the clean committed source tree, release notes,
release-package gate, final ZIP and sidecar, exact current-HEAD archive
membership, deterministic package bytes, Framework remote/branch state, and
absence of an existing local `v5.4.0` tag.

Before committing this checkpoint:

```powershell
python scripts\smoke_v540_final_release_tag_readiness.py --allow-dirty
```

After committing, the existing ZIP generated from `3108109` is stale because
the tracked source set has changed. Delete it, rebuild from the new clean commit,
and run:

```powershell
python scripts\build_v540_release_package.py

python scripts\smoke_v540_final_release_tag_readiness.py `
  --require-clean-tree `
  --require-package
```

```text
v5.4.0 final tag readiness: ACCEPTED
v5.4.0 tag/push: READY after clean committed package rebuild
v540_final_tag_readiness_status: accepted
v540_final_package_rebuild_required_after_checkpoint_commit: True
v540_tag_authorization: ready-after-strict-package-verification
```

This checkpoint does not create a tag, push, publish, upload assets, execute a
real provider, read private evidence/audio/transcripts or an API key, access the
microphone, or modify DRC.

See:

- [`docs/v540_final_release_tag_readiness.md`](docs/v540_final_release_tag_readiness.md)
- [`docs/release_notes_v5.4.0.md`](docs/release_notes_v5.4.0.md)

## v5.5.0 candidate real motion adapter readiness

FW-VTS-0a inventories the existing root-public motion skeleton and the legacy
Live2D / VTube Studio hotkey runtime before any real-adapter implementation.

```text
FW-VTS-0a: IMPLEMENTED / AWAITING_REVIEW
FW-VTS-0b through FW-VTS-0f: NOT_AUTHORIZED
real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

The v5.2.0 public MotionSession contract remains frozen and mock-compatible.
Host applications import only `MotionRequest`, `MotionResult`, and
`create_motion_session` from `framework`. They do not import `live2d`, plugins,
internal adapters, or pyvts and do not own WebSocket or token handling.

The candidate real adapter remains default-off:

```env
FRAMEWORK_MOTION_REAL_ADAPTER=0
FRAMEWORK_MOTION_ALLOW_PROVIDER_EXECUTION=0
FRAMEWORK_MOTION_ADAPTER=mock
```

These variables are reserved documentation in FW-VTS-0a and do not yet change
runtime behavior.

DRC RT-7 remains blocked until FW-VTS-0f acceptance and a released Framework
root-public real-motion adapter.

See
[`docs/v550_real_motion_adapter_readiness.md`](docs/v550_real_motion_adapter_readiness.md).

## v5.5.0 candidate motion adapter configuration/status

FW-VTS-0b adds an explicit-only provider-neutral configuration and capability
foundation for the future real VTube Studio adapter.

Public symbols:

```python
from framework import (
    MotionAdapterExecutionConfig,
    get_motion_adapter_execution_capability,
    resolve_motion_adapter_execution_config,
)
```

This checkpoint is fake-only and execution-free. It does not read environment
variables or files, import pyvts/WebSocket modules, create a provider client,
connect to VTube Studio, inspect token/model paths, or execute real motion.

`MotionAdapterStatus.CONFIGURED` means only that explicit boolean declarations
are complete. It does not mean a real transport is bound or available.
`MotionSession` composition remains deferred to FW-VTS-0e.

See
[`docs/v550_motion_adapter_configuration_status.md`](docs/v550_motion_adapter_configuration_status.md).

## v5.5.0 candidate internal VTube Studio transport Protocol/fake

FW-VTS-0c adds an internal async VTube Studio transport Protocol and a
deterministic in-memory fake for later real-adapter composition.

The transport symbols are not exported from the Framework root. Host apps and
DRC continue to use only provider-neutral root-public APIs. This checkpoint
does not import pyvts/WebSocket modules, connect or authenticate, resolve
provider hotkey IDs, trigger a real hotkey, execute motion, or change
MotionSession.

See
[`docs/v550_vtube_studio_transport_protocol_fake.md`](docs/v550_vtube_studio_transport_protocol_fake.md).

## v5.5.0 candidate guarded lazy pyvts transport

FW-VTS-0d adds an internal guarded pyvts transport implementation behind the
FW-VTS-0c async Protocol.

The transport requires explicit real-adapter and provider-execution opt-in,
then lazily imports pyvts only after endpoint, runtime, authentication-material,
and model-selection guards pass. Connect, authentication, hotkey inventory,
hotkey trigger, and close are individually bounded by timeouts.

This checkpoint does not export provider-specific symbols from the Framework
root, compose the transport into MotionSession, bootstrap or persist tokens,
retry, reconnect, create background tasks, or execute an actual VTube Studio
connection during validation.

See
[`docs/v550_vtube_studio_pyvts_transport.md`](docs/v550_vtube_studio_pyvts_transport.md).

## v5.5.0 candidate root-public VTube Studio MotionSession composition

FW-VTS-0e composes the accepted internal VTube Studio transport into the
root-public `MotionSession` boundary without exporting provider-specific types.
The existing mock path and the legacy three-argument VTS `not_implemented` path
remain compatible.

The real-capable path is explicit-only and default-off. Host applications must
provide all readiness assertions, endpoint values, authentication material, and
hotkey bindings directly:

```python
from framework import MotionRequest, create_motion_session

session = create_motion_session(
    adapter="vts",
    real_adapter_enabled=True,
    allow_provider_execution=True,
    runtime_available=True,
    model_selected=True,
    vts_endpoint_host="<explicit-host>",
    vts_endpoint_port=8001,
    vts_authentication_token="<explicit-authentication-material>",
    vts_hotkey_bindings={
        "expression:happy": "<configured-hotkey-name>",
    },
)

capability = session.preflight()
result = session.apply_motion(MotionRequest.expression_change("happy"))
session.close()
```

A VTS session owns one lazily started worker thread and one persistent asyncio
event loop so preflight, trigger, and close reuse the same provider-client loop.
There is no per-call `asyncio.run`, automatic retry, reconnect loop, token-file
fallback, or background polling task.

FW-VTS-0e validation injects deterministic in-memory transports only. Actual
pyvts import, WebSocket connection, VTube Studio authentication, hotkey trigger,
and real motion remain **NOT_AUTHORIZED** until FW-VTS-0f.

See
[`docs/v550_motion_session_real_adapter_composition.md`](docs/v550_motion_session_real_adapter_composition.md).

## v5.5.0 candidate VTube Studio operator acceptance tooling

FW-VTS-0f1 adds operator-only token bootstrap, root-public real-motion
acceptance, and private evidence validation commands. These commands require a
clean repository, explicit confirmations, pyvts 0.3.3, a loopback only endpoint,
and absolute private paths that keep token, configuration, and evidence
repository outside.

The committed smoke is source-only. It validates imports, private configuration
shape, bounded evidence schemas, and command help without importing actual
pyvts, opening a WebSocket, reading or writing a real token, or executing real
motion.

FW-VTS-0f1 does not authorize private token bootstrap or real VTube Studio
execution. Both remain **NOT_AUTHORIZED** until the operator checkpoint is
reviewed, committed, pushed, and separately authorized.

See
[`docs/v550_vtube_studio_operator_acceptance.md`](docs/v550_vtube_studio_operator_acceptance.md).

<!-- FW-VTS-0f1c-OPTIONAL-STOP-CORRECTIVE -->
## FW-VTS-0f1c optional stop_motion corrective

Baseline:

```text
1f737128554d701150427da4ce1c146759881255
```

Status:

```text
implementation: COMPLETED / AWAITING REVIEW
private token bootstrap: COMPLETED / ACCEPTED / REUSE
real VTS execution: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

This corrective supersedes the earlier operator-only exact-five requirement.
VTube Studio hotkey acceptance now has four required intents:

```text
expression
emotion
gesture
reset_expression
```

`stop_motion` is optional and may be configured only when the selected adapter
and model have an actually proven stop operation. A four-binding private config
is valid and must report `supports_stop_motion == false`. A five-binding private
config is valid only when its fifth binding is a real stop operation; renaming
`RemoveAllExpressions` or `TriggerAnimation` to `stop_motion` does not prove
stop support.

The operator executes and visually verifies the four required intents. It
executes and verifies `stop_motion` only when the optional binding is present.
Private evidence records:

```text
required_four_intents_verified
stop_motion_supported
stop_motion_verified
optional_stop_motion_contract
```

Accepted bootstrap evidence may remain tied to the accepted bootstrap commit
when that commit is an ancestor of the corrective acceptance commit and
`scripts/operator_v550_vtube_studio_token_bootstrap.py` is unchanged between
the two commits.

The corrective is an exact ten-file surface limited to six documentation files
and four operator/checker scripts. Framework runtime, public API, pyvts
transport, token bootstrap tooling, release files, and DRC are frozen.

<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:BEGIN -->
## FW-VTS-0f2 public real-motion acceptance sync

This block supersedes earlier pre-execution authorization status for the
FW-VTS-0f operator checkpoint. It records only public-safe facts already
accepted by the private evidence validator.

```text
checkpoint: FW-VTS-0f2
status: IMPLEMENTED / AWAITING_REVIEW
accepted framework head: b7b9639dfa1f675ba04a33cd8ce297429f98fd15
accepted bootstrap head: 1f737128554d701150427da4ce1c146759881255
pyvts version: 0.3.3
actual pyvts import: VERIFIED
actual WebSocket connection: VERIFIED
actual VTube Studio authentication: VERIFIED
model loaded: VERIFIED
hotkey inventory loaded: VERIFIED
expression: VERIFIED
emotion: VERIFIED
gesture: VERIFIED
reset_expression: VERIFIED
required four intents: VERIFIED
stop_motion_supported: False
stop_motion_verified: False
optional stop_motion contract: VERIFIED
real hotkey execution: VERIFIED
real motion execution: VERIFIED
operator visual confirmation: COMPLETE
session close: VERIFIED
bridge thread termination: VERIFIED
bootstrap evidence reused: VERIFIED
bootstrap operator unchanged: VERIFIED
private evidence: ACCEPTED_BY_VALIDATOR
DRC repository changed: False
private values recorded in repository: False
real VTS execution repeated by this sync: False
private evidence read by this sync: False
commit / push: NOT_AUTHORIZED
```

No token material, private path, endpoint value, hotkey identity, selector
value, model identity, provider payload, raw exception, evidence document,
or screenshot is part of this public acceptance record.
<!-- FW-VTS-0f2-REAL-MOTION-ACCEPTANCE-SYNC:END -->

<!-- FW-VTS-0f3-RELEASE-READINESS:BEGIN -->
## FW-VTS-0f3 aggregate release readiness

This block records only public, repository-safe facts. It does not repeat the
private VTube Studio operator run and does not read private token,
configuration, or evidence files.

```text
checkpoint: FW-VTS-0f3
status: IMPLEMENTED / AWAITING_REVIEW
baseline head: a1c39369bd35b21196b25a93a82798f47f1dad30
accepted real-motion head: b7b9639dfa1f675ba04a33cd8ce297429f98fd15
accepted bootstrap head: 1f737128554d701150427da4ce1c146759881255
FW-VTS-0a: ACCEPTED / PUSHED
FW-VTS-0b: ACCEPTED / PUSHED
FW-VTS-0c: ACCEPTED / PUSHED
FW-VTS-0d: ACCEPTED / PUSHED
FW-VTS-0e: ACCEPTED / PUSHED
FW-VTS-0f1: ACCEPTED / PUSHED
FW-VTS-0f2: ACCEPTED / PUSHED
required four intents: ACCEPTED
stop_motion_supported: False
stop_motion_verified: False
optional stop_motion contract: ACCEPTED
private real-motion evidence: ACCEPTED_BY_PUBLIC_SYNC
release package created: False
v5.5.0 tag created: False
DRC repository changed: False
release package authorization: READY_FOR_FW-VTS-0f4_AFTER_REVIEW
commit / push: NOT_AUTHORIZED
```
<!-- FW-VTS-0f3-RELEASE-READINESS:END -->

<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:BEGIN -->
## FW-VTS-0f4a deterministic release-package gate

This checkpoint adds the deterministic v5.5.0 source-package builder and
temporary package gate. It does not create the final release package, tag,
push, publish, connect to VTube Studio, or read private VTS artifacts.

```text
checkpoint: FW-VTS-0f4a
status: IMPLEMENTED / AWAITING_REVIEW
baseline head: a83f7efe85d489887b1d97122b2756e2a1b57ff5
package version: 5.5.0
deterministic temporary builds required: 2
tracked private VTS artifact rejection: REQUIRED
final release ZIP created: False
final SHA-256 sidecar created: False
v5.5.0 tag created: False
DRC repository changed: False
next authorization: READY_FOR_FW-VTS-0f4b_AFTER_REVIEW
commit / push: NOT_AUTHORIZED
```
<!-- FW-VTS-0f4a-RELEASE-PACKAGE-GATE:END -->

<!-- FW-VTS-0f4b-FINAL-TAG-READINESS:BEGIN -->
## FW-VTS-0f4b final tag readiness and DRC handoff

This public checkpoint fixes the v5.5.0 release notes, final pre-tag package
verification contract, and released DRC RT-7 handoff boundary. It does not
create the final package, tag, push, publish, or modify DRC.

```text
checkpoint: FW-VTS-0f4b
status: IMPLEMENTED / AWAITING_REVIEW
baseline head: 77a6a679f35cbf03fffeff7e8fee8a1c8863fc26
release version: 5.5.0
release theme: Real Motion Adapter / VTube Studio
release notes present: True
DRC handoff present: True
DRC RT-7 status: READY_AFTER_V5.5.0_TAG_PUSH
accepted required intents: expression, emotion, gesture, reset_expression
stop_motion_supported: False
stop_motion_verified: False
optional stop_motion contract: ACCEPTED
final package rebuild required after checkpoint commit: True
final package verified for checkpoint commit: False
v5.5.0 tag created: False
DRC repository changed: False
tag authorization: READY_AFTER_STRICT_PACKAGE_VERIFICATION
commit / push: NOT_AUTHORIZED
```
<!-- FW-VTS-0f4b-FINAL-TAG-READINESS:END -->

<!-- FW-RT6-0a-SOURCE-INVENTORY:BEGIN -->
## v6.0.0 Unified Realtime Character Runtime planning baseline

FW-RT6-0a records the current-source gap inventory, v6.0.0 roadmap, and
implementation tasklist against the accepted v5.5.0 baseline. This checkpoint
is documentation/test only and does not implement the unified runtime.

```text
checkpoint: FW-RT6-0a
baseline head: f56697b6de066b062794ac7bb01330d2d9e91759
status: IMPLEMENTED / AWAITING_REVIEW
release baseline: v5.5.0 TAGGED / PUSHED / ACCEPTED / PUBLISHED
target release: v6.0.0
theme: Unified Realtime Character Runtime
exact change surface: 6 files
runtime Python changed: False
provider execution: False
network execution: False
microphone use: False
audio playback: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-0b
FW-RT6-0b implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Planning documents:

- [`docs/roadmap_feature_v6.0.0.md`](docs/roadmap_feature_v6.0.0.md)
- [`docs/v600_current_source_gap_inventory.md`](docs/v600_current_source_gap_inventory.md)
- [`docs/v600_tasklist.md`](docs/v600_tasklist.md)

The inventory intentionally reports missing sequence/generation fields, absent
terminal/stale guards, incomplete real-stage composition, stale capability
status, split TTS ownership, SDK packaging gaps, and test-architecture gaps as
not implemented. It does not treat roadmap intent as released behavior.
<!-- FW-RT6-0a-SOURCE-INVENTORY:END -->

<!-- FW-RT6-0b-D-PUBLIC-SDK-HYGIENE-ACCEPTANCE:BEGIN -->
## v6.0.0 public SDK baseline hygiene checkpoint

FW-RT6-0b Controls A through C align the root-public manifest, consolidate the
`VoiceOutputSession` lifecycle, and centralize source/API/schema version
metadata without changing the accepted v5 public contracts. Control D adds the
aggregate docs/test acceptance gate only.

```text
checkpoint: FW-RT6-0b Control D
baseline head: 136be27c9f6fe62b7753c64f4fed02ae94f98da9
status: IMPLEMENTED / AWAITING_REVIEW
Control A canonical public API manifest: ACCEPTED
Control B VoiceOutputSession lifecycle hygiene: ACCEPTED
Control C central version metadata: ACCEPTED
root-public name count: 95
framework source version: 6.0.0.dev0
latest published release: 5.5.0
public API/schema compatibility values changed: False
provider execution: False
network execution: False
microphone use: False
audio playback: False
VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-0c
FW-RT6-0c implementation: NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

Remaining work is not reclassified as complete: installable packaging and
resource-root resolution remain FW-RT6-0c, capability truthfulness remains
FW-RT6-1d, and unified realtime orchestration remains later FW-RT6 work.
<!-- FW-RT6-0b-D-PUBLIC-SDK-HYGIENE-ACCEPTANCE:END -->

<!-- FW-RT6-0c-A-PACKAGE-METADATA:BEGIN -->
## v6.0.0 installable SDK package metadata

FW-RT6-0c Control A adds `pyproject.toml` and resource-package markers for the
future installable SDK. The distribution is named `ai-character-framework`;
applications continue to import the provider-neutral API from `framework`.

```text
checkpoint: FW-RT6-0c Control A
status: IMPLEMENTED / AWAITING_REVIEW
source development version: 6.0.0.dev0
latest published release: 5.5.0
canonical root-public names: 95
core dependency: python-dotenv
provider/runtime dependencies: OPTIONAL EXTRAS
preset/character lookup behavior changed: False
voice artifact path behavior changed: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next control: FW-RT6-0c Control B
next control authorized: False
commit / push: NOT_AUTHORIZED
```

See `docs/v600_installable_sdk_contract.md` for the package and dependency
boundary. Resource-root behavior remains unchanged until Control B.
<!-- FW-RT6-0c-A-PACKAGE-METADATA:END -->

<!-- FW-RT6-0c-C-INSTALLABLE-SDK-ISOLATION:BEGIN -->
## v6.0.0 installable SDK isolation checkpoint

FW-RT6-0c Control C verifies both editable and wheel installations from
repository-external working directories. Public examples now import the
installed `framework` package directly and no longer insert the checkout root
into `sys.path`.

```text
checkpoint: FW-RT6-0c Control C
baseline head: e51a07e62045b185799cd32d64127170c30ebe56
status: IMPLEMENTED / AWAITING_REVIEW
editable install: PASS
wheel build/install: PASS
import outside checkout: PASS
bundled preset/character lookup outside CWD: PASS
public example sys.path mutation: False
canonical root-public names: 95
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next control: FW-RT6-0c Control D
next control authorized: False
commit / push: NOT_AUTHORIZED
```

The gate installs no provider extras and performs no live model, voice, motion,
or host-application operation. Aggregate task/gap acceptance remains Control D.
<!-- FW-RT6-0c-C-INSTALLABLE-SDK-ISOLATION:END -->

<!-- FW-RT6-0c-D-INSTALLABLE-SDK-ACCEPTANCE:BEGIN -->
## v6.0.0 installable SDK aggregate acceptance

FW-RT6-0c Controls A through C establish normal package metadata, package-based
preset/character resolution, a CWD-independent public voice artifact default,
and isolated editable/wheel installation. Control D records aggregate
acceptance only; it does not change package or runtime behavior.

```text
checkpoint: FW-RT6-0c Control D
baseline head: cf9949579d971de68b2b763928f1c8052cf49921
status: IMPLEMENTED / AWAITING_REVIEW
Control A package metadata: ACCEPTED
Control B resource resolution: ACCEPTED
Control C isolated installation: ACCEPTED
distribution name: ai-character-framework
source development version: 6.0.0.dev0
editable install: PASS
wheel build/install: PASS
import outside checkout: PASS
public preset/character CWD dependency: False
public voice artifact CWD dependency: False
public example sys.path mutation: False
canonical root-public names: 95
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-1a
next checkpoint authorized: False
commit / push: NOT_AUTHORIZED
```

Legacy `main.py` and legacy runtime CWD-relative paths, capability truthfulness,
normal deterministic unit-test architecture, and unified realtime composition
remain separate later work. This checkpoint does not reclassify them as done.
<!-- FW-RT6-0c-D-INSTALLABLE-SDK-ACCEPTANCE:END -->


<!-- FW-RT6-1a-D-PUBLIC-IDENTITY-ACCEPTANCE:BEGIN -->
## v6.0.0 public identity foundation aggregate acceptance

FW-RT6-1a Controls A through C establish provider-neutral scalar identities,
Realtime session/turn adoption, and Motion session adoption. Control D records
aggregate acceptance only; it does not add event ordering, generation wiring,
terminal/recovery models, or unified realtime stage orchestration.

```text
checkpoint: FW-RT6-1a Control D
baseline head: 9d955955d4462006ed8aacc8e4c6e43ae487fb35
status: IMPLEMENTED / AWAITING_REVIEW
Control A public identity primitives: ACCEPTED
Control B Realtime identity adoption: ACCEPTED
Control C Motion identity adoption: ACCEPTED
SessionId root-public: VERIFIED
TurnId root-public: VERIFIED
GenerationId root-public: VERIFIED
EventSequence root-public: VERIFIED
legacy root-public prefix: 95 names / SAME ORDER
canonical root-public total: 99
Framework-generated Realtime session/turn identities: TYPED
Framework-generated Motion session identity: TYPED
provider identifier promoted to Framework identity: False
all-stage result correlation wiring completed: False
RealtimeEvent sequence/generation wiring completed: False
unified phase/outcome/recovery models completed: False
unified realtime runtime implemented: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-1b
next checkpoint authorized: False
commit / push: NOT_AUTHORIZED
```

Legacy non-`fw_` host identifiers remain temporarily compatible. Reserved
`fw_*` values are validated by kind, and provider/VTS request identifiers are
not reclassified as Framework-owned session, turn, or generation identities.
<!-- FW-RT6-1a-D-PUBLIC-IDENTITY-ACCEPTANCE:END -->

<!-- FW-RT6-1b-D-LIFECYCLE-ACCEPTANCE:BEGIN -->
## v6.0.0 public lifecycle foundation aggregate acceptance

FW-RT6-1b Controls A through C establish separate transient phase, terminal
turn outcome, normalized recovery action, and canonical RealtimeSession phase
models. Control D records aggregate acceptance only; it does not add ordered v6
event fields, a per-session terminal registry, duplicate suppression, stale
result rejection, or real unified stage orchestration.

```text
checkpoint: FW-RT6-1b Control D
baseline head: 8bc71a990762c8161d262bc7617a44e0dfb2c8e3
status: IMPLEMENTED / AWAITING_REVIEW
Control A lifecycle primitives: ACCEPTED
history baseline corrective: ACCEPTED
Control B turn outcome/recovery adoption: ACCEPTED
Control C RealtimeSession phase adoption: ACCEPTED
legacy root-public prefix: 99 names / SAME ORDER
canonical root-public total: 104
transient phase / terminal outcome: SEPARATE
RealtimeTurnResult canonical outcome: TurnOutcome
RealtimeTurnResult recovery_action: RecoveryAction
RealtimeSession canonical phase: RealtimePhase | None
legacy RealtimeState compatibility: PRESERVED
invalid transition: TYPED FAILURE
terminal state regression: PROHIBITED BY VALIDATION PRIMITIVE
per-session terminal registry: False
atomic first-terminal commit: False
duplicate terminal suppression runtime: False
exactly-once terminal enforcement: False
RealtimeEvent v6 fields added: False
real unified orchestration: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-1c
next checkpoint authorized: False
commit / push: NOT_AUTHORIZED
```

`RealtimePhase` remains transient-only. `TurnOutcome` remains terminal-only.
The validation primitive rejects duplicate or regressive terminal transitions,
but no session-owned terminal registry or atomic exactly-once commit exists yet.
Those runtime guarantees remain later work.
<!-- FW-RT6-1b-D-LIFECYCLE-ACCEPTANCE:END -->

<!-- FW-RT6-1c-E-REALTIME-EVENT-ACCEPTANCE:BEGIN -->
## v6.0.0 ordered realtime event foundation aggregate acceptance

FW-RT6-1c Controls A through D establish provider-neutral typed payload models,
the canonical v6 event envelope, the explicit lossy v5 adapter, and ordered
`RealtimeSession` callback adoption. Control E records aggregate acceptance
only; it does not add a terminal registry, duplicate suppression, automatic
stale-result rejection, a bounded event queue, provider partial/delta callbacks,
or real unified stage orchestration.

```text
checkpoint: FW-RT6-1c Control E
baseline head: 80e5c550bbb994bc8dfc3340340691c881f0449d
status: IMPLEMENTED / AWAITING_REVIEW
Control A typed payload models: ACCEPTED
encoding-corrupt corrective: SUPERSEDED / PRESERVED IN HISTORY
encoding repair: ACCEPTED
Control B RealtimeEvent v6 envelope: ACCEPTED
Control C explicit v5 adapter: ACCEPTED
Control D ordered RealtimeSession adoption: ACCEPTED
legacy root-public prefix: 104 names / SAME ORDER
canonical root-public total: 114
canonical completed-turn events: 9
legacy projected completed-turn events: 8
EventSequence session lifetime: ADOPTED
EventSequence reset between turns: False
GenerationId per admitted turn: ADOPTED
generation for session-only/rejected-before-admission events: None
typed payload by canonical runtime category: ADOPTED
automatic timestamp and monotonic_timestamp: ADOPTED
authoritative ordering: EventSequence
terminal registry / duplicate suppression: DEFERRED
automatic stale-result rejection: DEFERRED
bounded event queue / overflow runtime: DEFERRED
provider partial transcript / response delta callbacks: DEFERRED
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-1d
next checkpoint authorized: False
commit / push: NOT_AUTHORIZED
```

The canonical event vocabulary includes partial/final transcript, response
started/delta/completed, synthesis, audio, motion, stale-result, and overflow
categories. Acceptance of those public categories does not claim that every
provider-driven category is already emitted by a real runtime.
<!-- FW-RT6-1c-E-REALTIME-EVENT-ACCEPTANCE:END -->

<!-- FW-RT6-1d-D-CAPABILITY-ACCEPTANCE:BEGIN -->
## v6.0.0 detailed capability snapshot aggregate acceptance

FW-RT6-1d Controls A through C establish the immutable detailed capability
models, a truthful global aggregation behind the v5.1 compatibility snapshot,
and a session-scoped `RealtimeSession.capabilities` snapshot.

Control D records aggregate acceptance only. It does not add real unified
orchestration, provider execution, provider hard cancellation, TTS queue
runtime, motion wiring inside `RealtimeSession`, or real STT composition.

```text
checkpoint: FW-RT6-1d Control D
baseline head: 753748d463f800647b251c788d217a5c5adc4049
Control D exact change surface: 6 files
root-public names: 121 / UNCHANGED
v5 compatibility schema: v5.1.capabilities / PRESERVED
detailed schema: v6.realtime_capabilities
global detailed snapshot: ACCEPTED
session-scoped snapshot: ACCEPTED
snapshot scope / generation: ACCEPTED
configured / runtime_available / guarded separation: ACCEPTED
fake runtime / real runtime separation: ACCEPTED
cooperative cancel / provider hard cancel separation: ACCEPTED
voice input current status accurate: True
realtime current status accurate: True
motion current status accurate: True
unsupported overclaim: False
real unified runtime: NOT_IMPLEMENTED
motion wired into RealtimeSession: False
provider/network/microphone/playback/VTS execution: False
next checkpoint: FW-RT6-2a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-1d-D-CAPABILITY-ACCEPTANCE:END -->

<!-- FW-RT6-2a-D-PUBLIC-SAFETY-ACCEPTANCE:BEGIN -->
## v6.0.0 recursive public-safety aggregate acceptance

FW-RT6-2a Controls A through C establish one recursive public-safe metadata
utility, migrate five core compatibility helpers to that utility, and remove raw
exception material from TextChat public error events.

```text
checkpoint: FW-RT6-2a Control D
baseline head: 888d689fcf894fa7fa83eb6d0daa18b41f77726a
status: IMPLEMENTED / AWAITING_REVIEW
Control A recursive public-safety primitives: ACCEPTED
Control B core metadata consumer migration: ACCEPTED
Control C TextChat public error safety: ACCEPTED
Control D exact change surface: 6 files
root-public names: 121 / UNCHANGED
recursive mapping/list/tuple/dataclass sanitization: PASS
secret-like key policy centralized: True
core compatibility helpers delegated: 5
nested credential redaction: PASS
private path exposed: False
raw exception exposed: False
TextChat raw exception string exposed: False
TextChat exception class name exposed: False
ask_stream exception re-raise preserved: True
all repository metadata paths claimed migrated: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
next checkpoint: FW-RT6-2b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

The common utility and migrated boundaries are accepted without claiming that
every historical metadata-bearing path in the repository has already been
rewritten. Further consumers must use the accepted utility as they are touched.
<!-- FW-RT6-2a-D-PUBLIC-SAFETY-ACCEPTANCE:END -->

<!-- FW-RT6-2b-D-EVENT-HUB-ACCEPTANCE:BEGIN -->
## v6.0.0 realtime event hub aggregate acceptance

FW-RT6-2b Controls A through C establish the internal event sequencer/subscriber
hub, adopt it in `RealtimeSession`, connect typed overflow diagnostics, and seal
event emission after the close boundary.

Control D records aggregate acceptance only. It does not add a terminal
registry, duplicate-terminal suppression, generation stale-result rejection,
real provider orchestration, an asynchronous subscriber queue, or background
callback workers.

```text
checkpoint: FW-RT6-2b Control D
baseline head: d12e562a0c0b0111386776d50286b1a4cbdf54d2
status: IMPLEMENTED / AWAITING_REVIEW
Control A event-hub primitives: ACCEPTED
Control B RealtimeSession hub adoption: ACCEPTED
Control C close/concurrent-operation hardening: ACCEPTED
Control D exact change surface: 6 files
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeSession factory signature changed: False
session-local sequence monotonic: PASS
callback registration/unregistration token: ACCEPTED
callback exception breaks turn: False
bounded event history: ACCEPTED / LIMIT 64
slow subscriber policy: SYNCHRONOUS SERIALIZED / RETAIN AND ACCOUNT
silent overflow: False
typed EVENT_OVERFLOW: ACCEPTED
overflow v5 projection: None
concurrent/reentrant event emission: SERIALIZED
operation-level lock: RLock
concurrent operation event groups interleave: False
reentrant close deferred: True
SESSION_CLOSED emitted once: True
event hub sealed after close: True
close後active event: False
asynchronous subscriber queue: NOT CLAIMED
terminal registry / exactly-once enforcement: DEFERRED / FW-RT6-2c
generation stale-result rejection: DEFERRED / FW-RT6-2d
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-2c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

The accepted bounded structure is canonical event history. Delivery remains
synchronous and serialized, so this checkpoint does not claim an asynchronous
per-subscriber queue, timeout eviction, or background delivery worker.
<!-- FW-RT6-2b-D-EVENT-HUB-ACCEPTANCE:END -->

<!-- FW-RT6-2c-D-TERMINAL-REGISTRY-ACCEPTANCE:BEGIN -->
## v6.0.0 realtime terminal registry aggregate acceptance

FW-RT6-2c Controls A through C establish the internal per-session terminal
registry, atomically retain the first terminal record/result, adopt that boundary
in `RealtimeSession`, suppress sequential and concurrent duplicate terminal
delivery, and reject reentrant late non-terminal transitions before mutation.

Control D records aggregate acceptance only. It does not add generation-based
stale completion rejection, provider-driven failure/cancel/reject orchestration,
real provider execution, or the normal unit-test architecture.

```text
checkpoint: FW-RT6-2c Control D
baseline head: 8393c82a312af73f0b18db106b6e32c959f251a2
status: IMPLEMENTED / AWAITING_REVIEW
Control A terminal registry primitives: ACCEPTED
Control B RealtimeSession registry adoption: ACCEPTED
Control C reentrant/concurrent terminal hardening: ACCEPTED
Control D exact change surface: 6 files
runtime source changed: False
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeTurnResult public model changed: False
RealtimeSession factory signature changed: False
event_diagnostics keys changed: False
terminal_results: READ-ONLY / COMMIT ORDER
terminal_diagnostics: IMMUTABLE / COUNT-ONLY
terminal registry primitive supports terminal outcomes: True
current verified RealtimeSession first-terminal path: TURN_COMPLETED
all provider-driven terminal paths wired: False / NOT CLAIMED
first terminal commit atomic: PASS
one terminal event per current completed turn: PASS
duplicate terminal suppression: PASS
terminal regression rejection: PASS
late non-terminal rejected before mutation: PASS
terminal reason/result retained: PASS
same-turn concurrent lifecycle groups: 1
same-turn terminal events: 1
same-turn terminal records: 1
first committed result identity preserved: True
terminal callback late events: 0
different-turn operation groups serialized: PASS
close contract preserved: PASS
generation stale-result rejection: DEFERRED / FW-RT6-2d
STALE_RESULT_DROPPED runtime use: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-2d
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

The accepted exactly-once claim is bounded to the terminal registry primitive and
the currently wired mock `TURN_COMPLETED` session path. Other typed terminal
outcomes remain available to later orchestration checkpoints but are not claimed
as provider-driven runtime paths here.
<!-- FW-RT6-2c-D-TERMINAL-REGISTRY-ACCEPTANCE:END -->


<!-- FW-RT6-2d-D-GENERATION-GATE-ACCEPTANCE:BEGIN -->
## v6.0.0 realtime generation-gate aggregate acceptance

FW-RT6-2d Controls A through C establish the internal provider-neutral
generation gate, adopt one central stage-completion ingress in
`RealtimeSession`, and verify deterministic race behavior plus semantic
alignment with the existing VTube Studio lifecycle-generation boundary.
Control C corrective 1 preserves terminal-registry late-operation rejection
inside a terminal callback after the active generation has been retired.

Control D records aggregate acceptance only. It changes no runtime source and
does not add real stage protocols, provider-driven orchestration, a public
`RealtimeSession.reset()` method, single-active-turn lifecycle enforcement, or
normal unit-test infrastructure.

```text
checkpoint: FW-RT6-2d Control D
baseline head: aee53d77840f49450d9319a1ff5208cec7471757
status: IMPLEMENTED / AWAITING_REVIEW
Control A generation-gate primitives: ACCEPTED
Control B RealtimeSession generation-gate adoption: ACCEPTED
Control C race / VTS alignment: ACCEPTED
Control C corrective 1 terminal callback compatibility: ACCEPTED
Control D initial candidate: ROLLED BACK / PRESERVED IN HISTORY
Control D exact change surface: 6 files
runtime source changed: False
root-public names: 121 / UNCHANGED
RealtimeEvent public model changed: False
RealtimeTurnResult public model changed: False
create_realtime_session signature changed: False
generation / event / terminal diagnostics keys changed: False
current generation registry: ACCEPTED
central stage completion ingress: ACCEPTED
old turn response delta delivered: False
old TTS artifact delivered: False
interrupt / cancel late audio delivered: False
close-requested / post-close completion delivered: False
open-session stale drop observable: True
close-requested / post-close stale event emitted: False / COUNT-ONLY OBSERVABLE
stale diagnostic legacy projection: None
VTS source changed: False
VTS alignment verification: IN-MEMORY FAKE / PASS
terminal callback interrupt events: 0
terminal callback cancel events: 0
terminal callback state / phase / history mutation: False
normal post-turn no-active interrupt: PRESERVED
all real provider-driven stage paths wired: False / NOT CLAIMED
public RealtimeSession reset method: NOT ADDED
single-active-turn lifecycle enforcement: DEFERRED / LATER CHECKPOINT
normal deterministic unit-test architecture: UNRESOLVED / FW-RT6-3c
real unified turn orchestration: UNRESOLVED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-3a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

The accepted stale boundary applies to completions entering through the current
central `_apply_stage_completion(...)` ingress. It does not claim that every
future real provider callback has already been connected to that ingress.
<!-- FW-RT6-2d-D-GENERATION-GATE-ACCEPTANCE:END -->

<!-- FW-RT6-3a-C-STAGE-PROTOCOL-ACCEPTANCE:BEGIN -->
## v6.0.0 realtime stage-protocol aggregate acceptance

FW-RT6-3a Control A establishes the explicitly stable provider-neutral package
`framework.realtime_stage`, four stage protocols, and generation-bearing public
stage context/result envelopes. Control B adds four optional keyword-only stage
bindings to `RealtimeSession` and `create_realtime_session(...)`, validates fake
implementations without provider execution, and gives session close once-only
best-effort ownership of injected stage shutdown.

Control C records aggregate acceptance only. It changes no runtime source and
does not execute injected stages from the current mock `run_turn()` path. Real
legacy adapter migration, capability/preflight composition, provider-driven stage
ordering, cancellation coordination, and unified turn orchestration remain later
work.

```text
checkpoint: FW-RT6-3a Control C
baseline head: 8db6a4ff1c9687b9e9d04b2f55a38611e27e0a5e
status: IMPLEMENTED / AWAITING_REVIEW
Control A provider-neutral stage protocols: ACCEPTED
Control B RealtimeSession stage injection: ACCEPTED
Control C exact change surface: 6 files
runtime source changed: False
stable public package: framework.realtime_stage
stage protocol count: 4
common lifecycle methods: preflight / capability / start / cancel / close
stage context: session / turn / generation
provider-specific public objects: False
factory parameters: 7 / KEYWORD-ONLY
stage injection: provider-neutral
fake stage injection: PASS
constructor stage lifecycle calls: 0
current run_turn injected stage starts: 0 / DEFERRED
session close stage ownership: ONCE PER INJECTED STAGE
stage close exception exposure: False / COUNT-ONLY
root-public names: 121 / UNCHANGED
provider SDK root import: False
real legacy adapter migration: UNRESOLVED / LATER CHECKPOINT
preflight / capability runtime composition: NOT EXECUTED / DEFERRED
real unified turn orchestration: UNRESOLVED
FW-RT6-3b deterministic fake runtime controller: NOT IMPLEMENTED
FW-RT6-3c normal unit-test layer: NOT IMPLEMENTED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
v6.0.0 released: False
next checkpoint: FW-RT6-3b
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

The accepted injection boundary is a composition contract, not a claim that the
legacy STT, LLM, TTS, or motion implementations already run behind
`RealtimeSession`.
<!-- FW-RT6-3a-C-STAGE-PROTOCOL-ACCEPTANCE:END -->

<!-- FW-RT6-3b-C-FAKE-RUNTIME-ACCEPTANCE:BEGIN -->
## v6.0.0 deterministic fake-runtime aggregate acceptance

FW-RT6-3b Control A establishes the explicit provider-neutral
`framework.realtime_fake_runtime` package, deterministic integer-tick
clock/scheduler, stage pause/resume, artificial delay, late completion,
duplicate terminal, cancellation timeout, queue overflow, and exact
metadata-free trace assertions. Control B adds the explicit
`DeterministicRealtimeRaceHarness`, which drives the accepted
`RealtimeGenerationGate` and `RealtimeTerminalRegistry` without changing
`RealtimeSession` orchestration.

Control C records aggregate acceptance only. It changes no runtime source and
does not add event-hub trace projection, normal `tests/` coverage, real provider
adapters, or unified production turn orchestration.

```text
checkpoint: FW-RT6-3b Control C
baseline head: 5a565afbb19e81f55d35e89486c2327a47d87ab5
status: IMPLEMENTED / AWAITING_REVIEW
Control A deterministic fake runtime controller: ACCEPTED
Control B generation-gate / terminal-registry adoption: ACCEPTED
Control C exact change surface: 6 files
runtime source changed: False
explicit package: framework.realtime_fake_runtime
deterministic controller: DeterministicFakeRuntimeController
deterministic race harness: DeterministicRealtimeRaceHarness
fake clock / scheduler: ACCEPTED
stage pause / resume: ACCEPTED
artificial delay: ACCEPTED
late completion injection: ACCEPTED
duplicate terminal injection: ACCEPTED
cancellation timeout injection: ACCEPTED
queue overflow injection: ACCEPTED
deterministic event trace assertion helper: ACCEPTED
actual generation gate adoption: True
actual terminal registry adoption: True
race reproducible: True
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
event-hub trace projection: DEFERRED
normal unit-test layer: DEFERRED / FW-RT6-3c
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-3c
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```
<!-- FW-RT6-3b-C-FAKE-RUNTIME-ACCEPTANCE:END -->

<!-- FW-RT6-3c-C-RUNTIME-UNIT-TEST-ACCEPTANCE:BEGIN -->
## v6.0.0 normal runtime unit-test aggregate acceptance

FW-RT6-3c establishes a non-empty normal `tests/` layer using the Python
standard-library `unittest` runner. Control A covers identity/models and
lifecycle transitions. Control B covers terminal ownership, generation and
stale-completion admission, subscriber/event-hub behavior, and the deterministic
fake runtime including its actual generation-gate and terminal-registry harness.

The 45-test suite is provider-free and network-free. Existing smoke/check
scripts remain aggregate, compatibility, and release gates rather than being
replaced by the normal unit-test layer. Control C records aggregate acceptance
only and changes no production runtime source.

```text
checkpoint: FW-RT6-3c Control C
baseline head: e368a3db3e1ae6160d6a3c3f01929eb6f256c57a
status: IMPLEMENTED / AWAITING_REVIEW
Control A unit-test foundation: ACCEPTED
Control B runtime primitive coverage: ACCEPTED
Control C exact change surface: 6 files
tests directory non-empty: True
selected runner: unittest
identity/model tests: 12
transition tests: 7
terminal registry tests: 5
generation/stale tests: 6
subscriber/event-hub tests: 7
deterministic fake-runtime tests: 8
full discovered unit tests: 45
unit tests network-free: True
full unit suite: PASS
existing smoke/check scripts retained as aggregate/release gates: True
production runtime source changed: False
root-public names: 121 / UNCHANGED
RealtimeSession orchestration changed: False
event-hub projection into deterministic fake trace: DEFERRED
provider / network / microphone / playback / real VTS execution: False
DRC repository accessed or changed: False
root-draft stash accessed or changed: False
next checkpoint: FW-RT6-4a
next checkpoint status: READY_FOR_EXACT_CONTRACT_REVIEW / NOT_AUTHORIZED
commit / push: NOT_AUTHORIZED
```

FW-RT6-3c accepts a fast provider-neutral regression layer. It does not claim
real provider execution, production stage orchestration, or release readiness.
<!-- FW-RT6-3c-C-RUNTIME-UNIT-TEST-ACCEPTANCE:END -->

<!-- README-HISTORICAL-DEVELOPMENT-LOG:END -->
