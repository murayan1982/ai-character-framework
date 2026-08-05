"""Internal package-resource resolution for the installable SDK.

This module is intentionally not root-public. It resolves provider-neutral
preset and character resources without depending on the process working
directory.
"""

from __future__ import annotations

import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path


def validate_resource_name(value: str, *, kind: str) -> str:
    """Return one safe package-resource segment or raise a path-safe error."""

    name = str(value).strip()
    if (
        not name
        or name in {".", ".."}
        or "\x00" in name
        or "/" in name
        or "\\" in name
        or ":" in name
        or Path(name).is_absolute()
    ):
        raise ValueError(f"Invalid {kind} resource name.")
    return name


def resolve_preset_resource(
    preset_name: str,
    *,
    project_root: str | Path | None = None,
) -> Traversable:
    """Resolve one preset JSON using explicit-root then package precedence."""

    name = validate_resource_name(preset_name, kind="preset")
    filename = f"{name}.json"
    if project_root is not None:
        candidate = Path(project_root).expanduser() / "presets" / filename
        if candidate.is_file():
            return candidate

    packaged = files("presets").joinpath(filename)
    if packaged.is_file():
        return packaged
    raise FileNotFoundError(f"Preset resource not found: {name!r}.")


def resolve_character_directory(
    character_name: str,
    *,
    project_root: str | Path | None = None,
) -> Traversable:
    """Resolve one character directory using explicit-root then package precedence."""

    name = validate_resource_name(character_name, kind="character")
    if project_root is not None:
        candidate = Path(project_root).expanduser() / "characters" / name
        if candidate.is_dir():
            return candidate

    packaged = files("characters").joinpath(name)
    if packaged.is_dir():
        return packaged
    raise FileNotFoundError(f"Character resource not found: {name!r}.")


def read_json_resource(resource: Traversable, *, label: str) -> object:
    """Read JSON without exposing the resolved filesystem/package path."""

    try:
        with resource.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read {label} resource.") from exc


def read_text_resource(resource: Traversable, *, label: str) -> str:
    """Read UTF-8 text without exposing the resolved path."""

    try:
        with resource.open("r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError as exc:
        raise ValueError(f"Unable to read {label} resource.") from exc


__all__ = [
    "read_json_resource",
    "read_text_resource",
    "resolve_character_directory",
    "resolve_preset_resource",
    "validate_resource_name",
]
