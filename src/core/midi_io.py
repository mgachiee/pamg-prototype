"""MIDI port discovery and routing helpers."""

import mido


# ---------------------------------------------------------------------------
# Port management
# ---------------------------------------------------------------------------

from src.core.routing import RoutingType

# ------------------------------------------------------------------
# Open ports
# ------------------------------------------------------------------

def open_midi_ports(
    routing_mode: RoutingType,
    melody_port_name: str,
    drum_port_name: str,
    single_port_name: str,
):
    """
    Open MIDI output ports according to the routing mode.

    Args:
        routing_mode (RoutingType): Selected routing strategy.
        melody_port_name (str): Output port for melody events.
        drum_port_name (str): Output port for percussion events.
        single_port_name (str): Shared port for single-port routing.

    Returns:
        tuple: (melody_port, drum_port) outputs. In single-port mode,
        both references point to the same port.

    Raises:
        ValueError: If required output ports are missing or mode is invalid.
    """
    # Discover available output ports before validating names.
    available_ports = list_midi_ports()
    print(f"Available MIDI output ports: {available_ports}")

    # Validate and open ports based on routing mode
    if routing_mode == RoutingType.single_port:
        # Single-port mode sends both streams through the same output.
        if single_port_name not in available_ports:
            raise ValueError(
                f"Single-port mode requires '{single_port_name}', but it is not available."
            )
        shared_port = mido.open_output(single_port_name)
        return shared_port, shared_port

    if routing_mode == RoutingType.split_ports:
        # Split-port mode validates both melody and drum outputs.
        missing_ports = []
        if melody_port_name not in available_ports:
            missing_ports.append(melody_port_name)
        if drum_port_name not in available_ports:
            missing_ports.append(drum_port_name)
        if missing_ports:
            raise ValueError(
                f"Missing MIDI output ports for split mode: {missing_ports}."
            )

        melody_port = mido.open_output(melody_port_name)
        drum_port = mido.open_output(drum_port_name)
        return melody_port, drum_port

    raise ValueError(
        f"Invalid routing mode '{routing_mode}'. Use 'single_port' or 'split_ports'."
    )

# ------------------------------------------------------------------
# Close ports
# ------------------------------------------------------------------

def close_midi_ports(*ports):
    """
    Close any provided MIDI output ports.

    Args:
        *ports: Variable list of ports to close; None values are ignored.
    """
    for port in ports:
        if port is not None:
            port.close()

# ------------------------------------------------------------------
# Discovery helpers
# ------------------------------------------------------------------

def list_midi_ports():
    """
    Return the available MIDI output port names.

    Returns:
        list: A list of available MIDI output port names.
    """
    return mido.get_output_names()