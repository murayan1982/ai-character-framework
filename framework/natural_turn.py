"""Provider-neutral experimental natural-turn capability contracts.

FW-RT6-12c Control A names seven independent experimental extensions without
activating any of them. Importing this explicit-only module does not access a
microphone, start background work, load a provider SDK, perform network work,
play audio, connect to VTube Studio, or change an existing session runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from .public_safety import public_mapping


NATURAL_TURN_API_VERSION = "6.0"


class NaturalTurnExtension(str, Enum):
    """One separately gated experimental natural-turn extension."""

    MICROPHONE_LISTENING_WHILE_SPEAKING = "microphone_listening_while_speaking"
    VAD_BASED_AUTOMATIC_DETECTION = "vad_based_automatic_detection"
    WAKE_WORD = "wake_word"
    BACKGROUND_INPUT_MONITORING = "background_input_monitoring"
    AUTOMATIC_NEXT_TURN_CAPTURE = "automatic_next_turn_capture"
    ECHO_CANCELLATION = "echo_cancellation"
    NOISE_SUPPRESSION = "noise_suppression"


class NaturalTurnOwnership(str, Enum):
    """Owner of any future execution advertised by one capability."""

    HOST_APPLICATION = "host_application"
    EXPLICIT_ADAPTER = "explicit_adapter"


def _enum(value: object, enum_type: type[Enum], *, field_name: str) -> Enum:
    try:
        return value if isinstance(value, enum_type) else enum_type(str(value))
    except ValueError as error:
        raise ValueError(f"{field_name} is invalid") from error


@dataclass(frozen=True, slots=True)
class NaturalTurnCapability:
    """Truthful support and ownership for one independent extension."""

    extension: NaturalTurnExtension | str
    supported: bool = False
    experimental: bool = True
    owner: NaturalTurnOwnership | str = NaturalTurnOwnership.HOST_APPLICATION
    explicit_activation_required: bool = True
    microphone_device_access: bool = False
    background_execution: bool = False
    provider_execution: bool = False
    network_execution: bool = False
    public_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        extension = _enum(
            self.extension,
            NaturalTurnExtension,
            field_name="extension",
        )
        owner = _enum(self.owner, NaturalTurnOwnership, field_name="owner")
        for name in (
            "supported",
            "experimental",
            "explicit_activation_required",
            "microphone_device_access",
            "background_execution",
            "provider_execution",
            "network_execution",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be a boolean")
        if not self.experimental:
            raise ValueError("natural-turn extensions must remain experimental")
        if not self.explicit_activation_required:
            raise ValueError("natural-turn extensions require explicit activation")
        if self.supported:
            if owner is not NaturalTurnOwnership.EXPLICIT_ADAPTER:
                raise ValueError(
                    "supported natural-turn extensions require an explicit adapter"
                )
        elif (
            owner is not NaturalTurnOwnership.HOST_APPLICATION
            or self.microphone_device_access
            or self.background_execution
            or self.provider_execution
            or self.network_execution
        ):
            raise ValueError(
                "unsupported natural-turn extensions must remain host-owned "
                "and must not advertise execution"
            )
        object.__setattr__(self, "extension", extension)
        object.__setattr__(self, "owner", owner)
        object.__setattr__(self, "public_metadata", public_mapping(self.public_metadata))

    def as_dict(self) -> Mapping[str, object]:
        """Return an immutable public-safe capability projection."""

        return MappingProxyType(
            {
                "extension": self.extension.value,
                "supported": self.supported,
                "experimental": self.experimental,
                "owner": self.owner.value,
                "explicit_activation_required": self.explicit_activation_required,
                "microphone_device_access": self.microphone_device_access,
                "background_execution": self.background_execution,
                "provider_execution": self.provider_execution,
                "network_execution": self.network_execution,
                "public_metadata": dict(self.public_metadata),
            }
        )


def _default_capabilities() -> tuple[NaturalTurnCapability, ...]:
    return tuple(NaturalTurnCapability(extension) for extension in NaturalTurnExtension)


@dataclass(frozen=True, slots=True)
class NaturalTurnCapabilitySet:
    """Exact seven-extension capability inventory with no combined mode."""

    capabilities: tuple[NaturalTurnCapability, ...] = field(
        default_factory=_default_capabilities
    )

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, tuple):
            raise TypeError("capabilities must be a tuple")
        if not all(
            isinstance(capability, NaturalTurnCapability)
            for capability in self.capabilities
        ):
            raise TypeError("capabilities must contain NaturalTurnCapability values")
        extensions = tuple(
            capability.extension for capability in self.capabilities
        )
        expected = tuple(NaturalTurnExtension)
        if len(set(extensions)) != len(extensions):
            raise ValueError("natural-turn extension capabilities must be unique")
        if set(extensions) != set(expected) or len(extensions) != len(expected):
            raise ValueError(
                "capabilities must contain each natural-turn extension exactly once"
            )

    def for_extension(
        self,
        extension: NaturalTurnExtension | str,
    ) -> NaturalTurnCapability:
        """Return one exact extension capability."""

        normalized = _enum(
            extension,
            NaturalTurnExtension,
            field_name="extension",
        )
        for capability in self.capabilities:
            if capability.extension is normalized:
                return capability
        raise AssertionError("validated capability set is incomplete")

    @property
    def supported_extensions(self) -> tuple[NaturalTurnExtension, ...]:
        return tuple(
            capability.extension
            for capability in self.capabilities
            if capability.supported
        )

    def as_dict(self) -> Mapping[str, object]:
        """Return the exact immutable inventory without collapsing features."""

        return MappingProxyType(
            {
                "api_version": NATURAL_TURN_API_VERSION,
                "capabilities": tuple(
                    dict(capability.as_dict()) for capability in self.capabilities
                ),
            }
        )


def default_natural_turn_capability_set() -> NaturalTurnCapabilitySet:
    """Return seven host-owned, unsupported, execution-free capabilities."""

    return NaturalTurnCapabilitySet()


__all__ = (
    "NATURAL_TURN_API_VERSION",
    "NaturalTurnExtension",
    "NaturalTurnOwnership",
    "NaturalTurnCapability",
    "NaturalTurnCapabilitySet",
    "default_natural_turn_capability_set",
)
