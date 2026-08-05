"""Central source and public contract version metadata.

The source version identifies the current development target. Individual API
and schema constants preserve the accepted v4/v5 compatibility values until a
separate exact contract explicitly changes those public contracts.
"""

from __future__ import annotations

FRAMEWORK_SOURCE_VERSION = "6.0.0.dev0"
LATEST_PUBLISHED_RELEASE = "5.5.0"

TEXT_CHAT_API_VERSION = "4.0"
VOICE_OUTPUT_BOUNDARY_VERSION = "v5.lazy_provider_adapter"
VOICE_INPUT_API_VERSION = "5.2.0"
REALTIME_API_VERSION = "5.2.0"
MOTION_API_VERSION = "5.5.0"
CAPABILITIES_SCHEMA_VERSION = "v5.1.capabilities"
REALTIME_CAPABILITIES_SCHEMA_VERSION = "v6.realtime_capabilities"

__all__ = [
    "CAPABILITIES_SCHEMA_VERSION",
    "FRAMEWORK_SOURCE_VERSION",
    "LATEST_PUBLISHED_RELEASE",
    "MOTION_API_VERSION",
    "REALTIME_CAPABILITIES_SCHEMA_VERSION",
    "REALTIME_API_VERSION",
    "TEXT_CHAT_API_VERSION",
    "VOICE_INPUT_API_VERSION",
    "VOICE_OUTPUT_BOUNDARY_VERSION",
]
