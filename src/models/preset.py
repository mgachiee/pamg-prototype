"""Preset data model for PAMG parameter snapshots."""

from dataclasses import dataclass
from typing import List

@dataclass
class Preset:
    """
    Defines a preset configuration for all agents and orchestration.

    Each field represents a parameter used by the interpolator or the agents.
    Continuous fields are blended across presets, while discrete fields are
    snapped at phrase boundaries (see `core/preset_interpolator.py`).
    """
    melody_max_step: float
    melody_pitch_low: float
    melody_pitch_high: float
    melody_syncopation: float
    melody_accent: float
    melody_ratchet_probability: float

    # Add more parameters for PA as needed, for example:
    # crash_cymbal_probability, ride_cymbal_probability, etc.
    drum_kick_probability: float
    drum_ghost_kick_probability: float
    drum_snare_probability: float
    drum_hat_open_probability: float
    drum_hat_closed_probability: float
    drum_ratchet_probability: float

    seeded_phrase_length: float

    harmony_tension: float
    harmony_chord_complexity: float
    harmony_chord_change_probability: float
    harmony_add_probability: float
    harmony_sub_probability: float
    harmony_accent_probability: float

    harmony_pitch_low: float
    harmony_pitch_high: float
    harmony_layer_weights: List[float]
    harmony_programs: List[int]
    melody_program: int
    harmony_layer_mode: str