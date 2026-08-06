# FW-RT6-2a Public Safety Contract

## Control A — recursive public-safety primitives

```text
checkpoint:
FW-RT6-2a Control A

baseline:
463496642f87daac1d280001d0385da1277a9f42

scope:
common recursive sanitization and safe error-classification primitives

existing public consumer migration:
NOT INCLUDED

TextChat raw error event correction:
NOT INCLUDED

root-public names:
121 / UNCHANGED

provider/network/microphone/playback/VTS execution:
False
```

## Purpose

Control A establishes one provider-neutral implementation for values that may
cross a public metadata or diagnostic boundary. It replaces no existing
consumer yet. This separation allows the recursive behavior and redaction
markers to be reviewed before broad session/model migration.

## Recursive value contract

`framework.public_safety.sanitize_public_value()` accepts ordinary scalar values
and recursively sanitizes:

```text
mapping:
immutable MappingProxyType

list:
immutable tuple

tuple:
immutable tuple

dataclass instance:
immutable MappingProxyType keyed by field name

enum:
sanitized enum value
```

The sanitizer never uses arbitrary-object `str()` or `repr()`. Unknown objects,
exceptions, binary values, private paths, cycles, excessive nesting, and
non-finite numbers receive stable redaction markers.

## Secret-key policy

Secret-like key matching is centralized in
`framework.public_safety.is_secret_like_key()`. Separator and case differences
do not bypass matching. The policy covers API keys, authorization/bearer
material, credentials, passwords, secrets, private keys, common access/refresh
tokens, ID tokens, generic token-bearing keys, and cookies.

A secret-like key causes the complete associated value to be replaced before
nested traversal.

## Private path policy

`PathLike` values are always redacted. Strings identifying Windows absolute
paths, UNC paths, POSIX/home paths, explicit relative paths, or common private
directories are redacted. Ordinary HTTP(S) URLs remain public unless they
contain URL user information or a secret-like query key. `file://` URLs are
private.

## Safe error classification

`classify_public_exception()` maps built-in exception categories to stable
provider-neutral codes and messages. It does not return the exception object,
raw exception string, provider payload, or exception class name.

Provider-specific and operation-specific mapping remains a later
consumer-adoption control.

## Explicit deferrals

```text
existing _public_mapping / _redact_mapping migration:
FW-RT6-2a Control B

TextChat error event raw exception removal:
FW-RT6-2a Control C

aggregate acceptance and tasklist sync:
FW-RT6-2a Control D

real provider execution:
not authorized
```

<!-- FW-RT6-2a-B-CONTRACT:BEGIN -->
## Control B — core compatibility-helper migration

Control B migrates the five core public-boundary `_public_mapping` helpers to
the Control A recursive utility while preserving their private names and current
internal imports.

Protected dependent surfaces include realtime metadata, voice-input metadata,
motion metadata, interrupt/output-control metadata, and detailed realtime
capability metadata.

```text
private helper names: PRESERVED
root-public names: 121 / UNCHANGED
public factory signatures: UNCHANGED
TextChat raw exception event: DEFERRED / Control C
remaining inventory / aggregate acceptance: Control D
provider/runtime execution: False
```
<!-- FW-RT6-2a-B-CONTRACT:END -->

<!-- FW-RT6-2a-C-CONTRACT:BEGIN -->
## Control C — TextChat error event and typed-result adoption

Control C removes raw exception material from the public text-chat streaming
event boundary and adopts the Control A safe classifier for both streaming
events and typed results.

### Public error event payload

```text
public_error_code:
provider-neutral stable code

safe_message:
operation-specific message with no provider payload

retryable:
boolean retry hint

public_metadata:
recursively sanitized metadata
```

The previous `error` and `error_type` fields are removed from emitted error
events. The `TextChatSessionEvent` public model itself remains unchanged.

### Classification contract

```text
FacadeConfigError:
configuration_missing

FacadeProviderError:
provider_request_failed

TimeoutError:
timeout

InterruptedError:
request_cancelled

PermissionError:
authentication_required

ConnectionError:
provider_unavailable

TypeError / ValueError:
invalid_request

other exception raised by LLM turn:
provider_request_failed
```

Classification never calls `str(error)` or `repr(error)` and never emits the
exception class name. The original exception is still re-raised by
`ask_stream()` for compatibility.

### Deferrals

```text
aggregate tasklist / gap acceptance:
Control D

event sequencing / subscriber isolation:
FW-RT6-2b
```
<!-- FW-RT6-2a-C-CONTRACT:END -->
