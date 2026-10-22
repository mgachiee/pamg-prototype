from dataclasses import dataclass
import math

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

    def __post_init__(self) -> None:
        """Enforce the canonical MIDI event contract at the model boundary."""
        self.note = self._integer(self.note, "note")
        self.velocity = self._integer(self.velocity, "velocity")
        self.channel = self._integer(self.channel, "channel")
        self.ratchet_count = self._integer(self.ratchet_count, "ratchet_count")
        if not 0 <= self.note <= 127:
            raise ValueError("note must be in MIDI range 0..127")
        if not 1 <= self.velocity <= 127:
            raise ValueError("velocity must be in MIDI range 1..127")
        if not 0 <= self.channel <= 15:
            raise ValueError("channel must be in MIDI range 0..15")
        try:
            self.duration = float(self.duration)
        except (TypeError, ValueError):
            raise ValueError("duration must be finite and positive") from None
        if not math.isfinite(self.duration) or self.duration <= 0:
            raise ValueError("duration must be finite and positive")
        if self.ratchet_count < 2:
            raise ValueError("ratchet_count must be at least 2")

    @staticmethod
    def _integer(value, field_name: str) -> int:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer") from None
        if not math.isfinite(numeric) or not numeric.is_integer():
            raise ValueError(f"{field_name} must be an integer")
        return int(numeric)
