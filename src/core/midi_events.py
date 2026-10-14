"""
MIDI event normalization utilities.

Defines the canonical `MidiEvent` dataclass and helper functions that coerce
raw event dictionaries into safe, typed values.
"""

import math
from typing import Optional
from src.models.midi_event import MidiEvent

def normalize_event(
    hit: dict,
    default_channel: int,
    default_duration: float,
) -> Optional[MidiEvent]:
    """
    Normalize a raw event dictionary into a `MidiEvent`.

    Args:
        hit (dict): Raw MIDI event data (note, velocity, duration, etc.).
        default_channel (int): Fallback channel when not provided.
        default_duration (float): Fallback duration when not provided.

    Returns:
        Optional[MidiEvent]: Normalized event or None if invalid.
    from typing import Optional
    """

    # ---------------------------------------------------------------------------
    # Data model
    # ---------------------------------------------------------------------------
    # Note is mandatory; drop any event that lacks it.
    note = hit.get("note")
    if note is None:
        return None

    # Coerce note into a valid integer and clamp to valid MIDI range [0, 127].
    try:
        note = int(note)
    except (TypeError, ValueError):
        return None
    note = max(0, min(127, note))

    # Velocity defaults to 100 and is clamped into [1, 127].
    velocity = hit.get("velocity", 100)
    try:
        velocity = int(velocity)
    except (TypeError, ValueError):
        velocity = 100
    velocity = max(1, min(127, velocity))

    # Duration defaults to the caller-provided value and must be positive.
    duration = hit.get("duration", default_duration)
    try:
        duration = float(duration)
        if duration <= 0 or math.isnan(duration):
            duration = default_duration
    except (TypeError, ValueError):
        duration = default_duration

    # Channel defaults to the provided channel and is clamped into [0, 15].
    channel = hit.get("channel", default_channel)
    if channel is None:
        channel = default_channel
    try:
        channel = int(channel)
    except (TypeError, ValueError):
        channel = default_channel
    channel = max(0, min(15, channel))

    # Ratchet count must be at least 2 to create a perceivable roll.
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