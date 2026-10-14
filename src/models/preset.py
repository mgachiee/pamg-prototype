"""Preset data model for PAMG parameter snapshots."""

from dataclasses import dataclass
from typing import List

@dataclass
class Preset:
    """
    Defines a preset configuration for all agents and orchestration.

    Each field represents a parameter defined in the PAMG baseline technical reference:
    - Melody Agent (MA) - §3.5
    - Harmony Agent (HA) - §4.5
    - Percussion Agent (PA) - §5.4
    - Shared cross-agent parameters
    """
    # Melody Agent (MA) - §3.5
    ma_step: float
    ma_range_low: float
    ma_range_high: float
    ma_velocity: float
    ma_tac: float
    ma_plus_minus_notes: float
    ma_mv_even: float
    ma_mv_odd: float
    ma_orch_plus_minus: float
    ma_orch_range_low: float
    ma_orch_range_high: float
    ma_trans: float

    # Harmony Agent (HA) - §4.5
    ha_tension: float
    ha_cpx_prog: float
    ha_plus_minus_notes: float
    ha_acc_beat: float
    ha_vel_ins: float
    ha_voice_ins: float
    ha_range_ins_low: float
    ha_range_ins_high: float
    ha_register_ins: float
    ha_ins_plus_minus: float
    ha_move: float

    # Percussion Agent (PA) - §5.4
    pa_vel_perc: float
    pa_acc_beat_p: float
    pa_ks_plus_minus: float
    pa_toms_plus_minus: float
    pa_cymb_plus_minus: float

    # Shared
    seeded_phrase_length: float
    shape_depth: float
    shape_length: float