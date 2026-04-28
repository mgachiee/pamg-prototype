import mido

from src.core.routing import RoutingType

def open_midi_ports(routing_mode: RoutingType, melody_port_name: str, drum_port_name: str, single_port_name: str):
    available_ports = list_midi_ports()
    print(f"Available MIDI output ports: {available_ports}")

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
    for port in ports:
        if port is not None:
            port.close()

def list_midi_ports():
    return mido.get_output_names()