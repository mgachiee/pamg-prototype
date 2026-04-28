from dataclasses import dataclass
from typing import Optional

@dataclass
class MidiEvent:
    note: int
    velocity: int
    duration: float
    channel: int
    is_ratchet: bool = False
    ratchet_count: int = 3

def normalize_event(
    hit: dict,
    default_channel: int,
    default_duration: float,
) -> Optional[MidiEvent]:
    """
    Normalizes a raw MIDI event dictionary into a structured MidiEvent dataclass.

    Args:
        hit: A dictionary containing raw MIDI event data.
        default_channel: The default MIDI channel to use if not specified in the hit.
        default_duration: The default duration to use if not specified in the hit.

    Returns:
        A MidiEvent instance with normalized values, or None if the hit is invalid.
    """
    note = hit.get("note")
    if note is None:
        return None

    try:
        note = int(note)
    except (TypeError, ValueError):
        return None

    velocity = hit.get("velocity", 100)
    try:
        velocity = int(velocity)
    except (TypeError, ValueError):
        velocity = 100
    velocity = max(1, min(127, velocity))

    duration = hit.get("duration", default_duration)
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = default_duration
    if duration <= 0:
        duration = default_duration

    channel = hit.get("channel", default_channel)
    if channel is None:
        channel = default_channel
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        channel = default_channel
    channel = max(0, min(15, channel))

    ratchet_count = hit.get("ratchet_count", 3)
    try:
        ratchet_count = int(ratchet_count)
    except (TypeError, ValueError):
        ratchet_count = 3
    if ratchet_count < 2:
        ratchet_count = 2

    return MidiEvent(
        note=note,
        velocity=velocity,
        duration=duration,
        channel=channel,
        is_ratchet=bool(hit.get("is_ratchet", False)),
        ratchet_count=ratchet_count,
    )