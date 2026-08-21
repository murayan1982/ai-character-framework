# Release Package Policy

## Current release

```text
target: v6.0.0
source version: 6.0.0
publication status: RELEASE_CANDIDATE / NOT_RELEASED
latest published release: v5.5.0
```

The official public artifact is a deterministic source ZIP plus an ASCII
SHA-256 sidecar:

```text
release/ai-character-framework_v6.0.0.zip
release/ai-character-framework_v6.0.0.zip.sha256
```

Generated artifacts stay ignored and uncommitted.

## Exact membership

Membership comes from `git ls-files` at the release commit. The builder sorts
normalized POSIX paths and applies only the committed exclusions below. The
official build does not accept untracked or dirty-worktree files.

Excluded:

```text
.git/**
.github/**
.gitignore
.vscode/settings.json
release/**
dist/**
build/**
virtual environments and caches
compiled Python files and logs
```

The package includes the installable Python packages, public configuration
examples, docs, examples, tests, and release tooling. Required members include
`README.md`, `LICENSE.txt`, `.env.example`, `pyproject.toml`, current/fixed
release notes, and the v6 package builder/readiness/operator sources.

## Private artifact rejection

Before exclusions are applied, the builder rejects tracked private artifact
paths, including token/config/evidence directories, `.env` variants other than
`.env.example`, credential/token/evidence JSON names, and captured audio. It
checks path names only and does not open private artifacts.

The public ZIP must not contain credentials, tokens, private configuration,
private evidence, provider identifiers, captured audio, transcripts, generated
voice output, screenshots, raw payloads, or raw exceptions.

## Determinism and archive safety

Every entry has a fixed timestamp, normalized regular-file permissions, sorted
order, and fixed DEFLATE settings. Verification requires:

```text
exact committed membership
byte-identical deterministic rebuild
ZIP integrity
duplicate entry rejection
unsafe/absolute/parent member rejection
private artifact rejection
SHA-256 sidecar integrity
isolated package-import smoke
framework.__version__ == 6.0.0
framework.__all__ count == 127
```

## Release execution boundary

The builder and readiness gates never create tags, push, or call GitHub. The
release operator requires a clean `main`, `HEAD == origin/main`, an absent tag
and GitHub Release, a strict package gate, and three exact confirmations. It
then creates an annotated tag, pushes only that tag, publishes the ZIP and
sidecar, redownloads both assets into a temporary directory, verifies them, and
confirms the repository remains clean.

Implementation review does not authorize public release operations.
