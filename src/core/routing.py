"""Routing mode definitions for MIDI output."""

from enum import Enum

class RoutingType(Enum):
    """Enumerates supported MIDI routing strategies."""
    single_port = "single_port"
    split_ports = "split_ports"