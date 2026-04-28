import mido

from src.core.routing import RoutingType

def open_midi_ports(routing_mode: RoutingType, melody_port_name: str, drum_port_name: str, single_port_name: str):
    """
    Opens the required MIDI output ports based on the routing mode.

    Args:
        routing_mode (RoutingType): The routing mode to determine which ports to open.
        melody_port_name (str): The name of the melody MIDI output port.
        drum_port_name (str): The name of the drum MIDI output port.
        single_port_name (str): The name of the single MIDI output port.

    Returns:
        tuple: A tuple containing the opened MIDI output ports.
    """
    available_ports = list_midi_ports()
    print(f"Available MIDI output ports: {available_ports}")

    # Validate and open ports based on routing mode
    if routing_mode == RoutingType.single_port:
        if single_port_name not in available_ports:
            raise ValueError(
                f"Single-port mode requires '{single_port_name}', but it is not available."
            )
        shared_port = mido.open_output(single_port_name)
        return shared_port, shared_port

    if routing_mode == RoutingType.split_ports:
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

def close_midi_ports(*ports):
    """
    Closes the given MIDI output ports.

    Args:
        *ports: A variable number of MIDI output ports to close.
    """
    for port in ports:
        if port is not None:
            port.close()

def list_midi_ports():
    """Lists all available MIDI output ports."""
    return mido.get_output_names()