# v5.1.0 Release Readiness Gate

This document records the release-readiness gate for v5.1.0.

The v5.1.0 release readiness gate is a mock-safe pre-release checkpoint for
host-app integration boundary work. It does not create release archives, tags, or
provider artifacts.

## Gate coverage

The gate verifies the following checkpoints:

- Python source compileability.
- Public contract inventory.
- Voice output preferred speak() method contract.
- Public factory signature contract.
- Public result/error contract.
- TextChatResult public type contract.
- TextChatResult runtime method contract.
- Capability snapshot contract.
- FW-owned provider config ownership contract.
- Public session lifecycle contract.
- Opaque voice artifact contract.
- Public contract conformance gate.
- Package import readiness from outside the repository root.
- Release package static check.

## Mock-safety contract

The gate must remain mock-safe:

- It must not call real provider APIs.
- It must not generate real voice artifacts.
- It must not read private provider credentials.
- It must not create release archives or tags.
- It must not require host apps to run from the framework checkout root.

## Transition notes

The v5.1.0 gate records these transition baselines:

- create_text_chat_session remains positional-capable for compatibility and is
  not keyword-only yet.
- Provider SDK modules may be loaded during full legacy text-chat conformance
  exercise; public import safety is checked separately and remains the release
  boundary.
- Package import readiness currently validates a source-distribution-like tree of
  FW-owned source packages rather than a wheel/sdist build artifact.

## Release decision

Passing this gate means the v5.1.0 source tree is ready for a release-readiness
decision. It does not by itself mean that a fixed release ZIP, tag, GitHub
release, or downstream DRC validation has been created.
