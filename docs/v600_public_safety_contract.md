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
