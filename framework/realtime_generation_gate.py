"""Internal provider-neutral generation gate for realtime stage completions.

The gate owns freshness only. It does not emit events, commit terminal results,
execute providers, or expose stage values through a public contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from types import MappingProxyType
from typing import Callable, Generic, Mapping, TypeVar

from .identity import GenerationId, TurnId, normalize_turn_id


CompletionT = TypeVar("CompletionT")


class GenerationAdvanceReason(str, Enum):
    """Stable internal reasons that retire one active generation."""

    NEW_TURN = "new_turn"
    INTERRUPT = "interrupt"
    CANCEL = "cancel"
    RESET = "reset"
    SESSION_CLOSED = "session_closed"
    TURN_TERMINAL = "turn_terminal"


class StaleCompletionReason(str, Enum):
    """Stable internal freshness-rejection reasons."""

    RETIRED_GENERATION = "retired_generation"
    UNKNOWN_GENERATION = "unknown_generation"
    TURN_MISMATCH = "turn_mismatch"


@dataclass(frozen=True, slots=True)
class RealtimeStageCompletionEnvelope(Generic[CompletionT]):
    """Internal generation-bearing completion returned by a future stage."""

    turn_id: TurnId | str
    generation_id: GenerationId | str
    stage: str
    value: CompletionT = field(repr=False)

    def __post_init__(self) -> None:
        turn_id = normalize_turn_id(self.turn_id)
        if turn_id is None:
            raise ValueError("turn_id must identify one realtime turn")
        generation_id = (
            self.generation_id
            if isinstance(self.generation_id, GenerationId)
            else GenerationId.parse(self.generation_id)
        )
        if not isinstance(self.stage, str):
            raise TypeError("stage must be a string")
        stage = self.stage.strip()
        if not stage:
            raise ValueError("stage must be non-empty")
        if len(stage) > 128:
            raise ValueError("stage must contain at most 128 characters")

        object.__setattr__(self, "turn_id", turn_id)
        object.__setattr__(self, "generation_id", generation_id)
        object.__setattr__(self, "stage", stage)


@dataclass(frozen=True, slots=True)
class GenerationAdmissionDecision(Generic[CompletionT]):
    """Atomic freshness decision for one internal stage completion."""

    accepted: bool
    envelope: RealtimeStageCompletionEnvelope[CompletionT]
    stale_reason: StaleCompletionReason | None = None
    retired_by: GenerationAdvanceReason | None = None
    current_generation_id: GenerationId | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.envelope, RealtimeStageCompletionEnvelope):
            raise TypeError("envelope must be a RealtimeStageCompletionEnvelope")
        if type(self.accepted) is not bool:
            raise TypeError("accepted must be a boolean")
        stale_reason = self.stale_reason
        if stale_reason is not None and not isinstance(
            stale_reason,
            StaleCompletionReason,
        ):
            stale_reason = StaleCompletionReason(str(stale_reason))
        retired_by = self.retired_by
        if retired_by is not None and not isinstance(
            retired_by,
            GenerationAdvanceReason,
        ):
            retired_by = GenerationAdvanceReason(str(retired_by))
        current_generation_id = self.current_generation_id
        if current_generation_id is not None and not isinstance(
            current_generation_id,
            GenerationId,
        ):
            current_generation_id = GenerationId.parse(current_generation_id)

        if self.accepted:
            if stale_reason is not None or retired_by is not None:
                raise ValueError(
                    "accepted decisions cannot contain stale or retirement reasons"
                )
        else:
            if stale_reason is None:
                raise ValueError("rejected decisions require a stale reason")
            if (
                stale_reason is not StaleCompletionReason.RETIRED_GENERATION
                and retired_by is not None
            ):
                raise ValueError(
                    "retired_by is valid only for retired-generation rejection"
                )
            if (
                stale_reason is StaleCompletionReason.RETIRED_GENERATION
                and retired_by is None
            ):
                raise ValueError(
                    "retired-generation rejection requires a retirement reason"
                )

        object.__setattr__(self, "stale_reason", stale_reason)
        object.__setattr__(self, "retired_by", retired_by)
        object.__setattr__(
            self,
            "current_generation_id",
            current_generation_id,
        )


@dataclass(frozen=True, slots=True)
class _ActiveGeneration:
    turn_id: TurnId | str
    generation_id: GenerationId


@dataclass(frozen=True, slots=True)
class _RetiredGeneration:
    turn_id: TurnId | str
    generation_id: GenerationId
    retired_by: GenerationAdvanceReason


class RealtimeGenerationGate:
    """Session-owned atomic current-generation and completion-freshness gate."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._active: _ActiveGeneration | None = None
        self._pending_generation_id: GenerationId | None = None
        self._latest_generation_id: GenerationId | None = None
        self._retired: dict[GenerationId, _RetiredGeneration] = {}
        self._known_turns: dict[GenerationId, TurnId | str] = {}
        self._generation_start_count = 0
        self._generation_advance_count = 0
        self._accepted_completion_count = 0
        self._stale_completion_count = 0

    @property
    def current_generation_id(self) -> GenerationId | None:
        with self._lock:
            return (
                self._active.generation_id
                if self._active is not None
                else None
            )

    @property
    def current_turn_id(self) -> TurnId | str | None:
        with self._lock:
            return self._active.turn_id if self._active is not None else None

    @property
    def pending_generation_id(self) -> GenerationId | None:
        """Return the reset replacement reserved for the next admitted turn."""

        with self._lock:
            return self._pending_generation_id

    @property
    def latest_generation_id(self) -> GenerationId | None:
        """Return the latest active, pending, or retired generation identity."""

        with self._lock:
            return self._latest_generation_id

    @property
    def diagnostics(self) -> Mapping[str, int]:
        with self._lock:
            return MappingProxyType(
                {
                    "generation_start_count": self._generation_start_count,
                    "generation_advance_count": self._generation_advance_count,
                    "accepted_completion_count": self._accepted_completion_count,
                    "stale_completion_count": self._stale_completion_count,
                    "active_generation_count": 1 if self._active is not None else 0,
                    "registry_size": len(self._known_turns),
                }
            )

    def start_generation(
        self,
        turn_id: TurnId | str,
    ) -> GenerationId:
        """Start one fresh generation, retiring any active generation first."""

        resolved_turn_id = normalize_turn_id(turn_id)
        if resolved_turn_id is None:
            raise ValueError("turn_id must identify one realtime turn")

        with self._lock:
            if self._active is not None:
                self._retire_active_locked(GenerationAdvanceReason.NEW_TURN)

            generation_id = self._pending_generation_id
            if generation_id is None:
                generation_id = GenerationId.new()
                self._generation_start_count += 1
            else:
                self._pending_generation_id = None
            self._active = _ActiveGeneration(
                turn_id=resolved_turn_id,
                generation_id=generation_id,
            )
            self._known_turns[generation_id] = resolved_turn_id
            self._latest_generation_id = generation_id
            return generation_id

    def reset_generation(self) -> tuple[GenerationId, GenerationId] | None:
        """Advance the sole generation owner across one reset boundary.

        An active generation is retired with the stable ``reset`` reason.  If
        the previous turn is already terminal, its latest generation remains
        the previous identity.  In both cases one distinct replacement is
        reserved and is consumed by the next ``start_generation`` call.

        The pending replacement is not an active turn generation.  A stage
        completion cannot be accepted against it until a turn is explicitly
        admitted and binds that exact identity.
        """

        with self._lock:
            active = self._active
            if active is not None:
                previous_generation_id = active.generation_id
                self._retire_active_locked(GenerationAdvanceReason.RESET)
            else:
                previous_generation_id = (
                    self._pending_generation_id or self._latest_generation_id
                )
            if previous_generation_id is None:
                return None

            replacement_generation_id = GenerationId.new()
            self._pending_generation_id = replacement_generation_id
            self._latest_generation_id = replacement_generation_id
            self._generation_start_count += 1
            return previous_generation_id, replacement_generation_id

    def advance(
        self,
        reason: GenerationAdvanceReason | str,
    ) -> GenerationId | None:
        """Retire the active generation once and return its ID, or None."""

        resolved_reason = (
            reason
            if isinstance(reason, GenerationAdvanceReason)
            else GenerationAdvanceReason(str(reason))
        )
        with self._lock:
            return self._retire_active_locked(resolved_reason)

    def admit_completion(
        self,
        envelope: RealtimeStageCompletionEnvelope[CompletionT],
    ) -> GenerationAdmissionDecision[CompletionT]:
        """Atomically accept a current completion or classify it as stale."""

        if not isinstance(envelope, RealtimeStageCompletionEnvelope):
            raise TypeError("envelope must be a RealtimeStageCompletionEnvelope")

        with self._lock:
            return self._admit_completion_locked(envelope)

    def apply_completion(
        self,
        envelope: RealtimeStageCompletionEnvelope[CompletionT],
        *,
        deliver: Callable[[CompletionT], None],
    ) -> GenerationAdmissionDecision[CompletionT]:
        """Admit and deliver one completion in the same freshness lock section.

        The gate remains the only freshness owner.  A current completion calls
        ``deliver`` exactly once while generation advancement is excluded.  A
        stale completion never calls it and retains the same typed rejection
        reason and count-only diagnostics as :meth:`admit_completion`.

        ``deliver`` is an internal, bounded application callback.  It must not
        perform provider, network, playback, or other unbounded host work.
        """

        if not isinstance(envelope, RealtimeStageCompletionEnvelope):
            raise TypeError("envelope must be a RealtimeStageCompletionEnvelope")
        if not callable(deliver):
            raise TypeError("deliver must be callable")

        with self._lock:
            decision = self._admit_completion_locked(envelope)
            if decision.accepted:
                deliver(envelope.value)
            return decision

    def _admit_completion_locked(
        self,
        envelope: RealtimeStageCompletionEnvelope[CompletionT],
    ) -> GenerationAdmissionDecision[CompletionT]:
        retired = self._retired.get(envelope.generation_id)
        if retired is not None:
            self._stale_completion_count += 1
            return GenerationAdmissionDecision(
                accepted=False,
                envelope=envelope,
                stale_reason=StaleCompletionReason.RETIRED_GENERATION,
                retired_by=retired.retired_by,
                current_generation_id=(
                    self._active.generation_id
                    if self._active is not None
                    else None
                ),
            )

        active = self._active
        known_turn = self._known_turns.get(envelope.generation_id)
        if known_turn is None or active is None:
            self._stale_completion_count += 1
            return GenerationAdmissionDecision(
                accepted=False,
                envelope=envelope,
                stale_reason=StaleCompletionReason.UNKNOWN_GENERATION,
                current_generation_id=(
                    active.generation_id if active is not None else None
                ),
            )

        if envelope.generation_id != active.generation_id:
            self._stale_completion_count += 1
            return GenerationAdmissionDecision(
                accepted=False,
                envelope=envelope,
                stale_reason=StaleCompletionReason.UNKNOWN_GENERATION,
                current_generation_id=active.generation_id,
            )

        if envelope.turn_id != active.turn_id:
            self._stale_completion_count += 1
            return GenerationAdmissionDecision(
                accepted=False,
                envelope=envelope,
                stale_reason=StaleCompletionReason.TURN_MISMATCH,
                current_generation_id=active.generation_id,
            )

        self._accepted_completion_count += 1
        return GenerationAdmissionDecision(
            accepted=True,
            envelope=envelope,
            current_generation_id=active.generation_id,
        )

    def _retire_active_locked(
        self,
        reason: GenerationAdvanceReason,
    ) -> GenerationId | None:
        active = self._active
        if active is None:
            return None
        self._active = None
        self._retired[active.generation_id] = _RetiredGeneration(
            turn_id=active.turn_id,
            generation_id=active.generation_id,
            retired_by=reason,
        )
        self._generation_advance_count += 1
        return active.generation_id


__all__ = [
    "GenerationAdvanceReason",
    "StaleCompletionReason",
    "RealtimeStageCompletionEnvelope",
    "GenerationAdmissionDecision",
    "RealtimeGenerationGate",
]
