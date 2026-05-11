from dataclasses import dataclass

@dataclass
class MidiEvent:
    """
    Normalized MIDI event representation.

    Attributes:
        note (int): MIDI pitch number (0-127).
        velocity (int): MIDI velocity (1-127).
        duration (float): Note duration in seconds.
        channel (int): MIDI channel (0-15).
        is_ratchet (bool): True when this event expands into sub-hits.
        ratchet_count (int): Sub-hit count when `is_ratchet` is True.
    """
    note: int
    velocity: int
    duration: float
    channel: int
    is_ratchet: bool = False
    ratchet_count: int = 3