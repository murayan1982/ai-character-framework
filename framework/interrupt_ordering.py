"""Provider-neutral whole-request interrupt ordering contract.

FW-RT6-9b Control A fixes identity, duplicate, and race policy as explicit
models only.  It does not install a runtime owner, wait for a duplicate,
reserve a terminal boundary, flush output, close a session, or reject a turn.
Runtime adoption remains a separately authorized control.

One interrupt operation is identified by the already accepted Framework
session and resolved turn identities.  A second public request identifier is
deliberately not introduced: one turn can have only one terminal boundary, so
allowing multiple interrupt identities for that turn would weaken rather than
strengthen idempotency.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .identity import (
    SessionId,
    TurnId,
    normalize_session_id,
    normalize_turn_id,
)


class InterruptOrderingRule(str, Enum):
    """Exact provider-neutral rules selected for FW-RT6-9b."""

    RESOLVED_TURN_IDENTITY = "resolved_turn_identity"
    REPLAY_OWNER_TERMINAL_RESULT = "replay_owner_terminal_result"
    FIRST_TERMINAL_RESERVATION_WINS = "first_terminal_reservation_wins"
    FIRST_ADMISSION_WINS = "first_admission_wins"
    OWNER_FLUSH_BEFORE_TERMINAL = "owner_flush_before_terminal"
    TYPED_REJECT_NEW_TURN = "typed_reject_new_turn"


@dataclass(frozen=True, slots=True)
class InterruptOrderingPolicy:
    """Immutable policy that Control B must adopt without reinterpretation."""

    request_identity: InterruptOrderingRule | str = (
        InterruptOrderingRule.RESOLVED_TURN_IDENTITY
    )
    duplicate_interrupt: InterruptOrderingRule | str = (
        InterruptOrderingRule.REPLAY_OWNER_TERMINAL_RESULT
    )
    normal_completion_race: InterruptOrderingRule | str = (
        InterruptOrderingRule.FIRST_TERMINAL_RESERVATION_WINS
    )
    close_race: InterruptOrderingRule | str = (
        InterruptOrderingRule.FIRST_ADMISSION_WINS
    )
    flush_race: InterruptOrderingRule | str = (
        InterruptOrderingRule.OWNER_FLUSH_BEFORE_TERMINAL
    )
    new_turn_during_interrupt: InterruptOrderingRule | str = (
        InterruptOrderingRule.TYPED_REJECT_NEW_TURN
    )

    def __post_init__(self) -> None:
        expected = {
            "request_identity": InterruptOrderingRule.RESOLVED_TURN_IDENTITY,
            "duplicate_interrupt": (
                InterruptOrderingRule.REPLAY_OWNER_TERMINAL_RESULT
            ),
            "normal_completion_race": (
                InterruptOrderingRule.FIRST_TERMINAL_RESERVATION_WINS
            ),
            "close_race": InterruptOrderingRule.FIRST_ADMISSION_WINS,
            "flush_race": InterruptOrderingRule.OWNER_FLUSH_BEFORE_TERMINAL,
            "new_turn_during_interrupt": (
                InterruptOrderingRule.TYPED_REJECT_NEW_TURN
            ),
        }
        for field_name, expected_rule in expected.items():
            value = getattr(self, field_name)
            rule = (
                value
                if isinstance(value, InterruptOrderingRule)
                else InterruptOrderingRule(str(value))
            )
            if rule is not expected_rule:
                raise ValueError(
                    f"{field_name} must use the accepted {expected_rule.value} rule"
                )
            object.__setattr__(self, field_name, rule)

    @property
    def request_id_required(self) -> bool:
        """Whether callers must invent a second identity for an interrupt."""

        return False

    @property
    def idempotency_key_fields(self) -> tuple[str, str]:
        """Stable fields used to converge requests for the same turn."""

        return ("session_id", "resolved_turn_id")


@dataclass(frozen=True, slots=True)
class InterruptOrderingKey:
    """One session-local, turn-terminal interrupt idempotency key."""

    session_id: SessionId | str
    resolved_turn_id: TurnId | str

    def __post_init__(self) -> None:
        session_id = normalize_session_id(self.session_id)
        turn_id = normalize_turn_id(self.resolved_turn_id)
        if session_id is None:
            raise ValueError("session_id must identify one Framework session")
        if turn_id is None:
            raise ValueError("resolved_turn_id must identify one Framework turn")
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "resolved_turn_id", turn_id)


class InterruptAdmissionOutcome(str, Enum):
    """Typed decision made at the whole-request ordering boundary."""

    OWNER = "owner"
    DUPLICATE_REPLAY = "duplicate_replay"
    EXISTING_TERMINAL = "existing_terminal"
    ALREADY_CLOSED = "already_closed"
    NEW_TURN_REJECTED = "new_turn_rejected"


@dataclass(frozen=True, slots=True)
class InterruptOrderingDecision:
    """Truthful, side-effect-free result of one ordering admission decision.

    This model reports ownership facts only.  It never claims that provider or
    output-control work has executed.
    """

    outcome: InterruptAdmissionOutcome | str
    key: InterruptOrderingKey | None = None
    execute_interrupt: bool = False
    reuse_owner_terminal_result: bool = False
    terminal_reserved: bool = False
    typed_reject: bool = False

    def __post_init__(self) -> None:
        outcome = (
            self.outcome
            if isinstance(self.outcome, InterruptAdmissionOutcome)
            else InterruptAdmissionOutcome(str(self.outcome))
        )
        if self.key is not None and not isinstance(self.key, InterruptOrderingKey):
            raise TypeError("key must be an InterruptOrderingKey or None")
        bool_fields = {
            "execute_interrupt": self.execute_interrupt,
            "reuse_owner_terminal_result": self.reuse_owner_terminal_result,
            "terminal_reserved": self.terminal_reserved,
            "typed_reject": self.typed_reject,
        }
        for field_name, value in bool_fields.items():
            if type(value) is not bool:
                raise TypeError(f"{field_name} must be a boolean")

        expected_flags = {
            InterruptAdmissionOutcome.OWNER: (True, False, True, False),
            InterruptAdmissionOutcome.DUPLICATE_REPLAY: (
                False,
                True,
                False,
                False,
            ),
            InterruptAdmissionOutcome.EXISTING_TERMINAL: (
                False,
                False,
                False,
                False,
            ),
            InterruptAdmissionOutcome.ALREADY_CLOSED: (
                False,
                False,
                False,
                False,
            ),
            InterruptAdmissionOutcome.NEW_TURN_REJECTED: (
                False,
                False,
                False,
                True,
            ),
        }
        actual_flags = (
            self.execute_interrupt,
            self.reuse_owner_terminal_result,
            self.terminal_reserved,
            self.typed_reject,
        )
        if actual_flags != expected_flags[outcome]:
            raise ValueError(
                f"{outcome.value} requires its exact ordering decision flags"
            )
        if outcome is InterruptAdmissionOutcome.ALREADY_CLOSED:
            if self.key is not None:
                raise ValueError("already_closed must not invent a turn key")
        elif self.key is None:
            raise ValueError(f"{outcome.value} requires one resolved turn key")

        object.__setattr__(self, "outcome", outcome)

    @classmethod
    def owner(cls, key: InterruptOrderingKey) -> "InterruptOrderingDecision":
        """Reserve the sole interrupt terminal owner for a resolved turn."""

        return cls(
            outcome=InterruptAdmissionOutcome.OWNER,
            key=key,
            execute_interrupt=True,
            terminal_reserved=True,
        )

    @classmethod
    def duplicate_replay(
        cls,
        key: InterruptOrderingKey,
    ) -> "InterruptOrderingDecision":
        """Require replay of the owner's terminal result without reexecution."""

        return cls(
            outcome=InterruptAdmissionOutcome.DUPLICATE_REPLAY,
            key=key,
            reuse_owner_terminal_result=True,
        )

    @classmethod
    def existing_terminal(
        cls,
        key: InterruptOrderingKey,
    ) -> "InterruptOrderingDecision":
        """Report that a normal or interrupt terminal already won."""

        return cls(outcome=InterruptAdmissionOutcome.EXISTING_TERMINAL, key=key)

    @classmethod
    def already_closed(cls) -> "InterruptOrderingDecision":
        """Report that close admission won before a turn key was reserved."""

        return cls(outcome=InterruptAdmissionOutcome.ALREADY_CLOSED)

    @classmethod
    def new_turn_rejected(
        cls,
        key: InterruptOrderingKey,
    ) -> "InterruptOrderingDecision":
        """Produce the typed reject decision for admission during interrupt."""

        return cls(
            outcome=InterruptAdmissionOutcome.NEW_TURN_REJECTED,
            key=key,
            typed_reject=True,
        )

    @property
    def side_effect_free(self) -> bool:
        """Whether this decision forbids repeat interrupt side effects."""

        return not self.execute_interrupt


DEFAULT_INTERRUPT_ORDERING_POLICY = InterruptOrderingPolicy()


__all__ = [
    "DEFAULT_INTERRUPT_ORDERING_POLICY",
    "InterruptAdmissionOutcome",
    "InterruptOrderingDecision",
    "InterruptOrderingKey",
    "InterruptOrderingPolicy",
    "InterruptOrderingRule",
]
