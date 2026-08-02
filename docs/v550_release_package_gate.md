# v5.5.0 Deterministic Release Package Gate

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

## Purpose

FW-VTS-0f4a converts the accepted v5.5.0 source-tree readiness state into a
deterministic source-package boundary. It verifies package construction in
temporary directories only. The final release ZIP and SHA-256 sidecar remain
deferred until the final tag-readiness checkpoint is committed and pushed.

## Package target

The later final operator build will create:

```text
release/ai-character-framework_v5.5.0.zip
release/ai-character-framework_v5.5.0.zip.sha256
```

FW-VTS-0f4a does not create either final artifact.

## Deterministic package boundary

The builder:

- reads the sorted git-tracked source set;
- permits an explicitly supplied exact local checkpoint surface for pre-commit
  temporary verification;
- rejects tracked private VTube Studio token, configuration, and evidence paths
  before package filtering;
- requires the accepted v5.5.0 real-motion runtime, public-safe operator
  tooling, source-tree readiness gate, and package-gate sources;
- writes every ZIP entry with a fixed timestamp and fixed regular-file
  permissions;
- uses deterministic compression and archive ordering;
- writes a SHA-256 sidecar using the exact ZIP filename.

## Hard rejection of tracked private VTS artifacts

Package construction fails if the git-tracked source set contains:

```text
config/tokens/**
*_token.json
vts_private_config.json
bootstrap_evidence.json
real_motion_operator_evidence.json
operator_evidence/**
```

This is a rejection boundary, not merely an archive exclusion. The builder
checks tracked path names only and never opens the private artifacts.

## Normal package exclusions

The package excludes:

```text
release/**
.git/**
.vscode/settings.json
virtual environments
__pycache__/**
*.pyc
*.pyo
*.pyd
private .env files
*.wav
cache directories
generated local artifacts
```

The public `.env.example` template remains eligible for the source package.
Public-safe operator and validator source files remain eligible. Token values,
private configuration values, private evidence, private identifiers, raw
provider payloads, and screenshots remain outside the repository and package.

## Required v5.5.0 entries

The package gate requires the public motion API, guarded transport, root-public
composition, accepted public-safe operator/validator source, source-tree
readiness, and package-gate tooling. Required entries include:

```text
framework/__init__.py
framework/motion.py
framework/motion_adapter_execution.py
framework/motion_session.py
framework/vtube_studio_transport.py
framework/vtube_studio_pyvts_transport.py
framework/vtube_studio_motion_composition.py
docs/v550_real_motion_adapter_readiness.md
docs/v550_vtube_studio_operator_acceptance.md
docs/v550_release_readiness_gate.md
docs/v550_release_package_gate.md
scripts/operator_v550_vtube_studio_token_bootstrap.py
scripts/operator_v550_vtube_studio_real_motion_acceptance.py
scripts/verify_v550_vtube_studio_private_evidence.py
scripts/smoke_v550_release_readiness_gate.py
scripts/smoke_v550_release_package_gate.py
scripts/build_v550_release_package.py
```

## Gate behavior

Run:

```powershell
python scripts\smoke_v550_release_package_gate.py
```

The gate builds the source package twice in separate temporary directories and
verifies:

```text
SHA-256 digests: identical
ZIP bytes: identical
entry order: identical
membership: exact package file set
ZIP integrity: PASS
duplicate entries: absent
private/local/generated artifacts: absent
final release directory: unchanged
```

The gate also runs only current-compatible dependencies:

```text
scripts/smoke_v550_release_readiness_gate.py
scripts/smoke_v550_vtube_studio_real_motion_acceptance_sync.py
scripts/check_release_package.py
```

Historical package/tag gates from earlier versions are not executable
dependencies because they freeze older tags, package names, and checkpoint
worktree surfaces.

## Final-package presence compatibility

The source-tree readiness gate accepts an explicit:

```text
--allow-final-package
```

mode for the later strict final verification. In that mode, the v5.5.0 ZIP and
sidecar must both already exist and must remain byte-for-byte unchanged by the
readiness gate. The readiness gate never creates, deletes, or updates them.

## Explicit non-actions

FW-VTS-0f4a:

- does not read a VTube Studio token;
- does not read private VTS configuration or evidence;
- does not import actual pyvts or a WebSocket client in the package gate;
- does not connect to VTube Studio;
- does not execute a real hotkey or motion;
- does not modify Framework runtime, operator tooling, or requirements;
- does not create the final release ZIP or sidecar;
- does not create or push a tag;
- does not publish a release;
- does not modify DRC.

## Acceptance markers

```text
v550_release_package_gate_status: accepted
v550_release_package_dry_run_succeeded: True
v550_release_package_deterministic: True
v550_release_package_file_set_exact: True
v550_release_package_created_in_release_dir: False
v550_release_package_temporary_sha256_present: True
v550_release_package_rejects_config_tokens: True
v550_release_package_rejects_token_json: True
v550_release_package_rejects_private_config: True
v550_release_package_rejects_private_evidence: True
v550_actual_pyvts_imported_in_package_gate: False
v550_websocket_connected_in_package_gate: False
v550_network_execution_in_package_gate: False
v550_private_token_read_in_package_gate: False
v550_private_evidence_read_in_package_gate: False
v550_real_motion_execution_in_package_gate: False
v550_drc_repo_changed: False
v550_tag_created: False
v550_push_performed: False
v550_next_authorization: ready-for-FW-VTS-0f4b
```
