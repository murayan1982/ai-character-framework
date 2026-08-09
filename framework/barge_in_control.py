"""Provider-neutral barge-in decision-to-control-plan contract.

FW-RT6-9c Control A keeps policy decision separate from runtime execution.  It
converts one accepted :class:`BargeInDecision` and one immutable capability
snapshot into a truthful, side-effect-free plan.  The plan never opens a
microphone, calls a provider, flushes output, or executes an interrupt.

Runtime adoption remains Control B work.  Control B may submit the plan's
``coordinator_request`` to the already accepted interrupt owner/coordinator;
it must not reinterpret the policy or bypass that coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from .output_control import (
    BargeInDecision,
    BargeInPolicyMode,
    InterruptReason,
    InterruptRequest,
    InterruptScope,
)
from .public_safety import public_mapping
from .realtime_capabilities import RealtimeCapabilitySnapshot


_HARD_CANCEL_MODES = frozenset(
    {
        BargeInPolicyMode.HARD_CANCEL,
        BargeInPolicyMode.TURN_TAKEOVER,
    }
)


def _effective_mode(
    decision: BargeInDecision,
    capabilities: RealtimeCapabilitySnapshot,
) -> BargeInPolicyMode:
    requested = decision.policy.mode
    if not decision.accepted or requested is BargeInPolicyMode.DISABLED:
        return BargeInPolicyMode.DISABLED
    if requested in _HARD_CANCEL_MODES and not capabilities.hard_cancel_supported:
        return BargeInPolicyMode.SOFT_INTERRUPT
    if (
        requested is BargeInPolicyMode.FLUSH_OUTPUT
        and not capabilities.tts_queue_flush_supported
    ):
        return BargeInPolicyMode.DISABLED
    return requested


@dataclass(frozen=True, slots=True)
class BargeInControlPlan:
    """Immutable, non-executing projection of one barge-in decision.

    Requested facts remain separate from supported and planned facts.  This is
    especially important for ``hard_cancel`` and ``turn_takeover``: when the
    snapshot cannot support provider hard cancellation, the effective mode is
    the weaker cooperative ``soft_interrupt`` mode.
    """

    decision: BargeInDecision
    requested_mode: BargeInPolicyMode | str
    effective_mode: BargeInPolicyMode | str
    coordinator_request: InterruptRequest | None
    execute_interrupt: bool
    provider_hard_cancel_requested: bool
    provider_hard_cancel_supported: bool
    provider_hard_cancel_planned: bool
    queue_flush_requested: bool
    queue_flush_supported: bool
    queue_flush_planned: bool
    turn_takeover_requested: bool
    capability_downgraded: bool
    microphone_detection_required: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, BargeInDecision):
            raise TypeError("decision must be a BargeInDecision")
        requested_mode = (
            self.requested_mode
            if isinstance(self.requested_mode, BargeInPolicyMode)
            else BargeInPolicyMode(str(self.requested_mode))
        )
        effective_mode = (
            self.effective_mode
            if isinstance(self.effective_mode, BargeInPolicyMode)
            else BargeInPolicyMode(str(self.effective_mode))
        )
        bool_fields = {
            "execute_interrupt": self.execute_interrupt,
            "provider_hard_cancel_requested": self.provider_hard_cancel_requested,
            "provider_hard_cancel_supported": self.provider_hard_cancel_supported,
            "provider_hard_cancel_planned": self.provider_hard_cancel_planned,
            "queue_flush_requested": self.queue_flush_requested,
            "queue_flush_supported": self.queue_flush_supported,
            "queue_flush_planned": self.queue_flush_planned,
            "turn_takeover_requested": self.turn_takeover_requested,
            "capability_downgraded": self.capability_downgraded,
            "microphone_detection_required": self.microphone_detection_required,
        }
        for field_name, value in bool_fields.items():
            if type(value) is not bool:
                raise TypeError(f"{field_name} must be a boolean")

        expected_hard_requested = requested_mode in _HARD_CANCEL_MODES
        expected_takeover = requested_mode is BargeInPolicyMode.TURN_TAKEOVER
        expected_queue_requested = self.decision.should_flush_queue is True
        expected_hard_planned = (
            self.execute_interrupt
            and expected_hard_requested
            and self.provider_hard_cancel_supported
        )
        expected_queue_planned = (
            self.execute_interrupt
            and expected_queue_requested
            and self.queue_flush_supported
        )
        expected_downgrade = (
            expected_hard_requested and not self.provider_hard_cancel_supported
        ) or (expected_queue_requested and not self.queue_flush_supported)
        if (
            not self.decision.accepted
            or requested_mode is BargeInPolicyMode.DISABLED
        ):
            expected_effective_mode = BargeInPolicyMode.DISABLED
        elif expected_hard_requested and not self.provider_hard_cancel_supported:
            expected_effective_mode = BargeInPolicyMode.SOFT_INTERRUPT
        elif (
            requested_mode is BargeInPolicyMode.FLUSH_OUTPUT
            and not self.queue_flush_supported
        ):
            expected_effective_mode = BargeInPolicyMode.DISABLED
        else:
            expected_effective_mode = requested_mode
        expected_execute = (
            expected_effective_mode is not BargeInPolicyMode.DISABLED
        )

        if requested_mode is not self.decision.policy.mode:
            raise ValueError("requested_mode must match the decision policy")
        if self.provider_hard_cancel_requested is not expected_hard_requested:
            raise ValueError("provider hard-cancel request fact is inconsistent")
        if self.turn_takeover_requested is not expected_takeover:
            raise ValueError("turn-takeover request fact is inconsistent")
        if self.queue_flush_requested is not expected_queue_requested:
            raise ValueError("queue-flush request fact is inconsistent")
        if self.provider_hard_cancel_planned is not expected_hard_planned:
            raise ValueError("provider hard-cancel plan overclaims capability")
        if self.queue_flush_planned is not expected_queue_planned:
            raise ValueError("queue-flush plan overclaims capability")
        if self.capability_downgraded is not expected_downgrade:
            raise ValueError("capability downgrade fact is inconsistent")
        if effective_mode is not expected_effective_mode:
            raise ValueError("effective_mode does not match policy and capability")
        if self.execute_interrupt is not expected_execute:
            raise ValueError("execute_interrupt does not match effective_mode")
        if self.microphone_detection_required:
            raise ValueError("Framework core must not own microphone detection")

        if self.execute_interrupt:
            if not self.decision.accepted:
                raise ValueError("a rejected decision cannot execute")
            if effective_mode is BargeInPolicyMode.DISABLED:
                raise ValueError("a disabled effective mode cannot execute")
            if not isinstance(self.coordinator_request, InterruptRequest):
                raise TypeError(
                    "an executing plan requires one coordinator InterruptRequest"
                )
            if self.coordinator_request.reason is not InterruptReason.USER_BARGE_IN:
                raise ValueError("coordinator request must retain user_barge_in reason")
            source_request = self.decision.interrupt_request
            if source_request is None:
                raise ValueError("an executing decision requires an interrupt request")
            expected_scope = (
                InterruptScope.CURRENT_TURN
                if effective_mode is BargeInPolicyMode.SOFT_INTERRUPT
                else self.decision.policy.interrupt_scope
            )
            expected_request_facts = (
                expected_scope,
                source_request.turn_id,
                expected_queue_planned,
                expected_queue_planned and expected_hard_requested,
                expected_hard_planned,
                self.decision.should_cancel_current_turn,
                source_request.timeout_seconds,
            )
            actual_request_facts = (
                self.coordinator_request.scope,
                self.coordinator_request.turn_id,
                self.coordinator_request.flush_output,
                self.coordinator_request.cancel_tts_queue,
                self.coordinator_request.cancel_llm_stream,
                self.coordinator_request.stop_motion,
                self.coordinator_request.timeout_seconds,
            )
            if actual_request_facts != expected_request_facts:
                raise ValueError(
                    "coordinator request does not match the truthful control plan"
                )
        else:
            if self.coordinator_request is not None:
                raise ValueError("a non-executing plan cannot carry a request")
            if effective_mode is not BargeInPolicyMode.DISABLED:
                raise ValueError("a non-executing plan must be effectively disabled")

        if (
            effective_mode in _HARD_CANCEL_MODES
            and not self.provider_hard_cancel_supported
        ):
            raise ValueError("effective hard cancel requires advertised capability")
        if (
            effective_mode is BargeInPolicyMode.FLUSH_OUTPUT
            and not self.queue_flush_supported
        ):
            raise ValueError("effective flush requires advertised capability")

        object.__setattr__(self, "requested_mode", requested_mode)
        object.__setattr__(self, "effective_mode", effective_mode)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    @property
    def decision_is_execution(self) -> bool:
        """A decision or plan never performs its described control effects."""

        return False

    @property
    def side_effect_free(self) -> bool:
        """Control A models are pure projections only."""

        return True


def build_barge_in_control_plan(
    decision: BargeInDecision,
    *,
    capabilities: RealtimeCapabilitySnapshot,
) -> BargeInControlPlan:
    """Build one truthful, non-executing plan from policy and capabilities."""

    if not isinstance(decision, BargeInDecision):
        raise TypeError("decision must be a BargeInDecision")
    if not isinstance(capabilities, RealtimeCapabilitySnapshot):
        raise TypeError("capabilities must be a RealtimeCapabilitySnapshot")

    requested_mode = decision.policy.mode
    effective_mode = _effective_mode(decision, capabilities)
    execute_interrupt = effective_mode is not BargeInPolicyMode.DISABLED
    hard_requested = requested_mode in _HARD_CANCEL_MODES
    queue_requested = decision.should_flush_queue is True
    hard_planned = (
        execute_interrupt
        and hard_requested
        and capabilities.hard_cancel_supported
    )
    queue_planned = (
        execute_interrupt
        and queue_requested
        and capabilities.tts_queue_flush_supported
    )
    downgraded = (
        hard_requested and not capabilities.hard_cancel_supported
    ) or (queue_requested and not capabilities.tts_queue_flush_supported)

    coordinator_request: InterruptRequest | None = None
    if execute_interrupt:
        source_request = decision.interrupt_request
        if source_request is None:
            raise ValueError("an accepted barge-in decision requires an interrupt request")
        scope = (
            InterruptScope.CURRENT_TURN
            if effective_mode is BargeInPolicyMode.SOFT_INTERRUPT
            else decision.policy.interrupt_scope
        )
        coordinator_request = InterruptRequest(
            scope=scope,
            reason=InterruptReason.USER_BARGE_IN,
            turn_id=source_request.turn_id,
            flush_output=queue_planned,
            cancel_tts_queue=queue_planned and hard_requested,
            cancel_llm_stream=hard_planned,
            stop_motion=decision.should_cancel_current_turn,
            public_metadata={
                **dict(source_request.public_metadata),
                "boundary": "barge_in_control",
                "requested_policy_mode": requested_mode.value,
                "effective_policy_mode": effective_mode.value,
                "capability_downgraded": downgraded,
                "microphone_detection_required": False,
            },
            timeout_seconds=source_request.timeout_seconds,
        )

    return BargeInControlPlan(
        decision=decision,
        requested_mode=requested_mode,
        effective_mode=effective_mode,
        coordinator_request=coordinator_request,
        execute_interrupt=execute_interrupt,
        provider_hard_cancel_requested=hard_requested,
        provider_hard_cancel_supported=capabilities.hard_cancel_supported,
        provider_hard_cancel_planned=hard_planned,
        queue_flush_requested=queue_requested,
        queue_flush_supported=capabilities.tts_queue_flush_supported,
        queue_flush_planned=queue_planned,
        turn_takeover_requested=(
            requested_mode is BargeInPolicyMode.TURN_TAKEOVER
        ),
        capability_downgraded=downgraded,
        microphone_detection_required=False,
        public_metadata=MappingProxyType(
            {
                "boundary": "barge_in_control",
                "requested_policy_mode": requested_mode.value,
                "effective_policy_mode": effective_mode.value,
                "capability_downgraded": downgraded,
                "microphone_detection_required": False,
            }
        ),
    )


__all__ = [
    "BargeInControlPlan",
    "build_barge_in_control_plan",
]
