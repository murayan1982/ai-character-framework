# AI Character Conversation Framework

A developer-oriented framework for building real-time AI character experiences with text, voice, and Live2D support.

This project is a framework, not a finished consumer app.

**Target audience:** Developers, VTuber creators, and AI experimenters who want a practical foundation for AI character interaction systems.

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

The current minimum conversation flow is:

```text
User input
-> LLM response
-> text display
-> optional TTS output
-> optional emotion parsing
-> optional VTS expression trigger
```

When voice and Live2D features are enabled, the same flow can drive speech output and expression changes.

The current runtime is intended to be understandable and extendable. More advanced real-time voice behavior, such as latency-oriented streaming speech, interruption, and richer conversation state handling, is tracked as future runtime work.

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
  - Public text chat facade details

- `docs/app_integration_contract.md`
  - External app integration boundaries

- `docs/advanced_runtime.md`
  - Runtime state, interruption boundaries, TTS stop behavior, and voice output policy

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

The README is intended to stay as the project entry point. Current release details should live in `docs/RELEASE_NOTES.md` instead of being accumulated here.

Historical release notes are preserved by Git tags and GitHub Releases.

---

## Roadmap

Current major roadmap topics are tracked in:

```text
docs/roadmap_feature_v4.0.0.md
docs/roadmap_feature_v5.0.0.md
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
