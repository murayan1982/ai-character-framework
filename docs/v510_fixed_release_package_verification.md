# v5.1.0 Fixed Release Package Verification

This document records the v5.1.0 fixed release package verification gate.

## Purpose

The v5.1.0 fixed release package verification gate checks that the release
package builder output can be treated as a host-app-facing SDK handoff artifact.

The gate is intentionally mock-safe. It does not publish a release, create a git
tag, call provider APIs, generate real audio, or commit release artifacts.

## Required local artifacts

The gate uses the v5.1.0 fixed release package builder to create local release
artifacts:

- `release/ai-character-framework_v5.1.0.zip`
- `release/ai-character-framework_v5.1.0_manifest.json`

These generated files are local release evidence. They are not required to be
tracked in git.

## Verification scope

The fixed release package verification must confirm:

- the builder script exists and completes successfully;
- the fixed v5.1.0 release zip exists after the builder runs;
- the fixed v5.1.0 release manifest exists after the builder runs;
- the release zip contains the public `framework` package;
- the release zip excludes local-only artifacts such as virtual environments,
  token files, runtime logs, patch helpers, and nested release outputs;
- the extracted package imports from outside the repository root;
- the extracted package exposes the v5.1.0 public API baseline;
- the extracted package can run a mock-safe public Voice Output request;
- provider SDKs and voice/TTS internals are not eagerly imported during the
  package import check.

## Transition note

v5.1.0 still has top-level FW-owned source package imports from the public
framework facade, such as `llm.*` and `config.*`. The fixed package verification
therefore validates the built source-distribution-like release zip rather than a
single `framework/` directory copy.

A wheel/sdist packaging contract can be added in a later release once installable
SDK metadata is introduced.

## Local secret hygiene

Release/package readiness excludes local token and secret artifacts, including
`config/tokens/`, `*_token.json`, `.env`, generated audio files, and runtime
output directories.

## Environment template hygiene

`.env` and private environment files are excluded from fixed release packages.
`.env.example` remains included because it is a public configuration template
and is required by release package checks.

