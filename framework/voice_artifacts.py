"""Provider-neutral FW-owned voice artifact store contracts for v6.

FW-RT6-6b Control A defines opaque artifact identity, public-safe lifecycle
records, and a store protocol that separates internal storage from public
``VoiceArtifactRef`` values. Importing this module does not import provider SDKs,
execute providers, access the network, use a microphone, perform playback, or
connect to VTube Studio.

The module is an explicitly stable package as ``framework.voice_artifacts`` but
is not re-exported by the ``framework`` root in Control A.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
import re
import threading
from typing import BinaryIO, Iterable, Protocol, runtime_checkable
from uuid import uuid4

from .audio.voice_output import VoiceArtifactRef
from .identity import GenerationId


_VOICE_ARTIFACT_ID_PATTERN = re.compile(r"^fw_voice_artifact_[0-9a-f]{32}$")


class VoiceArtifactId(str):
    """Opaque Framework-owned identity for one stored voice artifact."""

    _prefix = "fw_voice_artifact_"

    def __new__(cls, value: str) -> "VoiceArtifactId":
        if not isinstance(value, str):
            raise TypeError("VoiceArtifactId value must be a string")
        if value != value.strip() or not _VOICE_ARTIFACT_ID_PATTERN.fullmatch(value):
            raise ValueError("Invalid voice artifact identifier.")
        return str.__new__(cls, value)

    @classmethod
    def new(cls) -> "VoiceArtifactId":
        """Create a new provider-neutral Framework-owned artifact identity."""

        return cls(f"{cls._prefix}{uuid4().hex}")

    @classmethod
    def parse(cls, value: str) -> "VoiceArtifactId":
        """Validate and normalize one serialized artifact identity."""

        if isinstance(value, cls):
            return value
        return cls(value)

    def to_json_value(self) -> str:
        """Return the JSON scalar representation."""

        return str(self)


class VoiceArtifactState(str, Enum):
    """Public-safe lifecycle state for a FW-owned voice artifact."""

    VALID = "valid"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class VoiceArtifactRecord:
    """Public-safe store record with no filesystem or provider details."""

    ref: VoiceArtifactRef
    state: VoiceArtifactState | str = VoiceArtifactState.VALID
    generation_id: GenerationId | str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ref, VoiceArtifactRef):
            raise TypeError("ref must be a VoiceArtifactRef")
        state = (
            self.state
            if isinstance(self.state, VoiceArtifactState)
            else VoiceArtifactState(str(self.state))
        )
        generation_id = self.generation_id
        if generation_id is not None and not isinstance(generation_id, GenerationId):
            generation_id = GenerationId.parse(generation_id)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "generation_id", generation_id)

    @property
    def is_playable(self) -> bool:
        """Whether the artifact may currently be opened for host handoff."""

        return self.state is VoiceArtifactState.VALID


@runtime_checkable
class VoiceArtifactStore(Protocol):
    """FW-owned storage boundary for opaque voice artifacts.

    Storage implementation paths remain private. Provider adapters may write
    artifact bytes through ``store()`` and receive only ``VoiceArtifactRef``.
    Framework orchestration may later associate the returned reference with a
    lifecycle ``GenerationId`` through ``bind_generation()`` without passing
    Framework correlation identities into provider adapters.
    """

    def store(
        self,
        content: bytes | Iterable[bytes],
        *,
        audio_format: str | None = None,
        content_type: str | None = None,
        expires_at: str | None = None,
    ) -> VoiceArtifactRef:
        ...

    def resolve(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> VoiceArtifactRecord | None:
        ...

    def open(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> BinaryIO:
        ...

    def delete(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> bool:
        ...

    def expire(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> bool:
        ...

    def bind_generation(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
        generation_id: GenerationId | str,
    ) -> VoiceArtifactRecord:
        ...


@dataclass(slots=True)
class _StoredVoiceArtifact:
    path: Path
    record: VoiceArtifactRecord


class FileVoiceArtifactStore:
    """Framework-local file-backed reference store.

    This concrete helper is intentionally not part of ``__all__`` in Control A.
    It exists so later provider-adapter wiring can persist streamed provider
    bytes without exposing the internal file path through public results.
    """

    __slots__ = ("_root", "_lock", "_records")

    def __init__(self, root: str | Path) -> None:
        root_path = Path(root).expanduser()
        self._root = root_path
        self._lock = threading.RLock()
        self._records: dict[VoiceArtifactId, _StoredVoiceArtifact] = {}

    def store(
        self,
        content: bytes | Iterable[bytes],
        *,
        audio_format: str | None = None,
        content_type: str | None = None,
        expires_at: str | None = None,
    ) -> VoiceArtifactRef:
        artifact_id = VoiceArtifactId.new()
        normalized_format = _normalize_audio_format(audio_format)
        suffix = f".{normalized_format}" if normalized_format else ".bin"

        with self._lock:
            self._root.mkdir(parents=True, exist_ok=True)
            path = self._root / f"{artifact_id}{suffix}"
            try:
                with path.open("xb") as stream:
                    if isinstance(content, (bytes, bytearray, memoryview)):
                        stream.write(bytes(content))
                    else:
                        for chunk in content:
                            if not isinstance(chunk, (bytes, bytearray, memoryview)):
                                raise TypeError("voice artifact content chunks must be bytes-like")
                            if chunk:
                                stream.write(bytes(chunk))
            except Exception:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise

            ref = VoiceArtifactRef.from_id(
                str(artifact_id),
                audio_format=normalized_format,
                content_type=content_type,
                expires_at=expires_at,
                public_metadata={"ownership": "framework"},
            )
            self._records[artifact_id] = _StoredVoiceArtifact(
                path=path,
                record=VoiceArtifactRecord(ref=ref),
            )
            return ref

    def resolve(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> VoiceArtifactRecord | None:
        artifact_id = _coerce_artifact_id(artifact)
        with self._lock:
            stored = self._records.get(artifact_id)
            return stored.record if stored is not None else None

    def open(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> BinaryIO:
        artifact_id = _coerce_artifact_id(artifact)
        with self._lock:
            stored = self._records.get(artifact_id)
            if stored is None or not stored.record.is_playable:
                raise FileNotFoundError("Voice artifact is not available for playback handoff.")
            path = stored.path
            if not path.is_file():
                raise FileNotFoundError("Voice artifact is not available for playback handoff.")
            return path.open("rb")

    def delete(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> bool:
        artifact_id = _coerce_artifact_id(artifact)
        with self._lock:
            stored = self._records.get(artifact_id)
            if stored is None or stored.record.state is VoiceArtifactState.DELETED:
                return False
            try:
                stored.path.unlink(missing_ok=True)
            except OSError:
                return False
            stored.record = replace(stored.record, state=VoiceArtifactState.DELETED)
            return True

    def expire(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
    ) -> bool:
        artifact_id = _coerce_artifact_id(artifact)
        with self._lock:
            stored = self._records.get(artifact_id)
            if stored is None or stored.record.state is not VoiceArtifactState.VALID:
                return False
            stored.record = replace(stored.record, state=VoiceArtifactState.EXPIRED)
            return True

    def invalidate_generation(
        self,
        generation_id: GenerationId | str,
    ) -> tuple[VoiceArtifactRecord, ...]:
        """Invalidate all valid artifacts bound to one lifecycle generation.

        This is a concrete FW-RT6-6d reference-store extension and is
        intentionally not added to the stable ``VoiceArtifactStore`` protocol.
        Repeated invalidation is idempotent and returns only records that
        transitioned from ``VALID`` to ``INVALIDATED`` in this call.
        """

        normalized_generation = (
            generation_id
            if isinstance(generation_id, GenerationId)
            else GenerationId.parse(generation_id)
        )
        invalidated: list[VoiceArtifactRecord] = []
        with self._lock:
            for stored in self._records.values():
                record = stored.record
                if (
                    record.generation_id == normalized_generation
                    and record.state is VoiceArtifactState.VALID
                ):
                    stored.record = replace(
                        record,
                        state=VoiceArtifactState.INVALIDATED,
                    )
                    invalidated.append(stored.record)
        return tuple(invalidated)

    def bind_generation(
        self,
        artifact: VoiceArtifactRef | VoiceArtifactId | str,
        generation_id: GenerationId | str,
    ) -> VoiceArtifactRecord:
        artifact_id = _coerce_artifact_id(artifact)
        normalized_generation = (
            generation_id
            if isinstance(generation_id, GenerationId)
            else GenerationId.parse(generation_id)
        )
        with self._lock:
            stored = self._records.get(artifact_id)
            if stored is None or not stored.record.is_playable:
                raise FileNotFoundError("Voice artifact is not available for generation binding.")
            existing = stored.record.generation_id
            if existing is not None and existing != normalized_generation:
                raise ValueError("Voice artifact is already bound to another generation.")
            if existing is None:
                stored.record = replace(
                    stored.record,
                    generation_id=normalized_generation,
                )
            return stored.record


def _coerce_artifact_id(
    artifact: VoiceArtifactRef | VoiceArtifactId | str,
) -> VoiceArtifactId:
    if isinstance(artifact, VoiceArtifactRef):
        return VoiceArtifactId.parse(artifact.artifact_id)
    if isinstance(artifact, VoiceArtifactId):
        return artifact
    return VoiceArtifactId.parse(artifact)


def _normalize_audio_format(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().lstrip(".")
    if not normalized:
        return None
    if not re.fullmatch(r"[a-z0-9][a-z0-9._+-]{0,31}", normalized):
        raise ValueError("Invalid public audio format.")
    return normalized


__all__ = [
    "VoiceArtifactId",
    "VoiceArtifactState",
    "VoiceArtifactRecord",
    "VoiceArtifactStore",
]
