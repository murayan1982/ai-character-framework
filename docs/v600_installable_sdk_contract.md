# v6.0.0 Installable SDK Contract

## FW-RT6-0c Control A — package metadata and wheel skeleton

Status:

```text
IMPLEMENTED / AWAITING_REVIEW
```

Control A adds the distribution metadata and resource-package skeleton needed
for later editable/wheel installation checks. It does not yet change preset,
character, project-root, or voice-artifact resolution behavior.

## Distribution identity

```text
distribution name: ai-character-framework
public import package: framework
source development version: 6.0.0.dev0
latest published release: 5.5.0
Python requirement: >=3.10
build backend: setuptools.build_meta
```

The distribution version is read from
`framework.version.FRAMEWORK_SOURCE_VERSION`; this does not mark v6.0.0 as a
published release.

## Included package families

```text
framework*
config*
llm*
registry*
presets
characters
```

`presets` and `characters` are resource-only packages. Their names are not
added to `framework.__all__`, and the canonical root-public count stays 95.

Bundled package data:

```text
presets/*.json
characters/*/*.json
characters/*/*.txt
```

## Dependency boundary

The core install requires only `python-dotenv`. Provider/runtime SDKs remain
optional extras grouped by LLM, voice input, voice output, motion, and full
runtime use. Importing `framework` after metadata creation must remain provider
safe.

`requirements.txt` remains the full development/runtime environment source for
this checkpoint. Control A does not remove or rewrite it.

## Deferred to later controls

```text
preset/character resource resolver: FW-RT6-0c Control B
public artifact default directory: FW-RT6-0c Control B
example sys.path cleanup: FW-RT6-0c Control C
isolated editable/wheel install acceptance: FW-RT6-0c Control C
aggregate gap sync: FW-RT6-0c Control D
```

## Non-execution record

```text
resource lookup behavior changed: False
factory signatures changed: False
artifact path behavior changed: False
framework.__all__ changed: False
provider/network/microphone/playback/VTS execution: False
DRC repository accessed or changed: False
```

<!-- FW-RT6-0c-B-RESOURCE-RESOLUTION:BEGIN -->
## Control B — package resource resolution

```text
preset lookup uses process CWD: False
character lookup uses process CWD: False
explicit project_root override: Preserved / keyword-only
package resource fallback: presets + characters
public voice artifact CWD fallback: Removed
public voice artifact default: system temp/ai-character-framework/voice_output
framework.__all__ count: 95 / unchanged
provider execution: False
network execution: False
next control: FW-RT6-0c Control C
next control authorized: False
```
<!-- FW-RT6-0c-B-RESOURCE-RESOLUTION:END -->
