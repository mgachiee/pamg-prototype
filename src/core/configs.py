"""
Global configuration defaults for PAMG.

Defines routing settings, orchestration defaults, rhythm templates, and the
four corner presets used by the XY pad interpolator.
"""

from src.core.routing import RoutingType
from src.core.preset_interpolator import Preset

ROUTING_MODE = RoutingType.split_ports  # Options: RoutingType.single_port, RoutingType.split_ports
SINGLE_PORT_NAME = "Melody 1"
MELODY_PORT_NAME = "Melody 1"
DRUM_PORT_NAME = "Drums 2"
DEBUG_MIDI = False

# Orchestration channels (0-based MIDI channels matching REAPER Tracks 1-8).
MELODY_CHANNELS = [0, 1, 2, 3]   # Strings, Piano, Woodwinds, Brass
HARMONY_CHANNEL = 5              # Default Piano
HARMONY_CHANNELS = [4, 5, 6, 7]  # Strings, Piano, Woodwinds, Brass
HARMONY_LAYER_WEIGHTS = [1.0, 1.0, 0.8, 0.8]
HARMONY_LAYER_MODE = "probabilistic"

# Mapping of channels to instrument families.
# Used by OrchestratorAgent to look up ranges in FAMILY_RANGES.
CHANNEL_FAMILIES = {
    0: "strings",    # Melody Strings
    1: "keys",       # Melody Piano
    2: "woodwinds",  # Melody Woodwinds
    3: "brass",      # Melody Brass
    4: "strings",    # Harmony Strings
    5: "keys",       # Harmony Piano
    6: "woodwinds",  # Harmony Woodwinds
    7: "brass",      # Harmony Brass
}

# Orchestration ranges (MIDI note bounds).
MELODY_RANGE = (48, 84)
HARMONY_RANGE = (40, 76)

# Instrument families and their typical ranges.
# Used by OrchestratorAgent to override global ranges for specific channels.
FAMILY_RANGES = {
    "strings": (48, 96),
    "brass": (36, 84),
    "woodwinds": (60, 96),
    "keys": (21, 108),
    "bass": (24, 48),
}

# Orchestration programs (MIDI program numbers 0-127).
# Baseline models 4 orchestral families (§6.2): Strings, Piano, Woodwinds, Brass
MELODY_PROGRAM = 48  # String Ensemble 1 (Strings)
MELODY_PROGRAMS = [48, 0, 73, 61]   # Strings, Piano, Woodwinds (Flute), Brass (Brass Section)
HARMONY_PROGRAMS = [48, 0, 73, 61]  # Strings, Piano, Woodwinds (Flute), Brass (Brass Section)
PERCUSSION_PROGRAM = 48             # General MIDI Orchestra Kit (Bank 128, Program 48)

# Percussion Template (Cinematic / Orchestral: Kick, Snare, Toms, Cymbals)
PERCUSSION_TEMPLATE = {
    # X/Y - X for loop size (time signature), Y for grain (subdivision)
    "4/4": {
        "KICK": [0],       # Downbeat structural anchor; syncopations follow melody accents
        "SNARE": [2],      # Half-time orchestral cadence punctuation (replaces 2 & 4 pop backbeat)
        "TOM": [3],        # Timpani/tom preparation roll into phrase downbeat
        "CYMBAL": [0],     # Phrase entrance / downbeat cymbal accent
    },
    "3/4": {
        "KICK": [0],
        "SNARE": [2],
        "TOM": [2],
        "CYMBAL": [0],
    },
    "5/4": {
        "KICK": [0],
        "SNARE": [3],
        "TOM": [4],
        "CYMBAL": [0],
    },
    "7/4": {
        "KICK": [0, 4],
        "SNARE": [3, 6],
        "TOM": [6],
        "CYMBAL": [0],
    },
    "6/8": {
        "KICK": [0],
        "SNARE": [3],
        "TOM": [5],
        "CYMBAL": [0],
    },
    "6/4": {
        "KICK": [0],
        "SNARE": [3],
        "TOM": [5],
        "CYMBAL": [0],
    },
}

# Harmony rhythm templates
HARMONY_TEMPLATE = {
    "4/4": {
        "CHORD": [0, 2],
        "ACCENT": [0],
    },
    "3/4": {
        "CHORD": [0, 2],
        "ACCENT": [0],
    },
    "5/4": {
        "CHORD": [0, 2, 4],
        "ACCENT": [0, 3],
    },
    "7/4": {
        "CHORD": [0, 3, 5],
        "ACCENT": [0, 4],
    },
    "6/8": {
        "CHORD": [0, 3],
        "ACCENT": [0],
    },
    "6/4": {
        "CHORD": [0, 3],
        "ACCENT": [0],
    },
}

# Game-state mapping defaults (used to normalize player/enemy values to [0..1])
MAX_HEALTH = 100.0
MAX_ENEMIES = 20.0

# Temporal smoothing (slew rate) for parameter transitions in seconds (§7.2, implementation-audit.md §4.3).
INTERPOLATION_SMOOTHING_TIME = 0.25

# Default presets (corners of the XY pad)
# A: Corner (0,0) - Low activity / subdued / somber (-V, -A)
PRESET_A = Preset(
    ma_step=2.0,
    ma_range_low=48.0,
    ma_range_high=67.0,
    ma_velocity=45.0,
    ma_tac=0.0,
    ma_plus_minus_notes=-0.4,
    ma_mv_even=0.1,
    ma_mv_odd=0.0,
    ma_orch_plus_minus=0.0,
    ma_orch_range_low=48.0,
    ma_orch_range_high=67.0,
    ma_trans=0.0,
    ha_tension=1.0,
    ha_cpx_prog=0.05,
    ha_plus_minus_notes=-0.5,
    ha_acc_beat=0.1,
    ha_vel_ins=42.0,
    ha_voice_ins=2.0,
    ha_range_ins_low=float(HARMONY_RANGE[0]),
    ha_range_ins_high=float(HARMONY_RANGE[1]),
    ha_register_ins=1.0,
    ha_ins_plus_minus=0.0,
    ha_move=0.0,
    pa_vel_perc=35.0,
    pa_acc_beat_p=0.15,
    pa_ks_plus_minus=-0.5,
    pa_toms_plus_minus=-0.5,
    pa_cymb_plus_minus=-0.6,
    seeded_phrase_length=8.0,
    shape_depth=2.0,
    shape_length=8.0,
)

# B: Corner (1,0) - Calm / open / sanctuary (+V, -A)
PRESET_B = Preset(
    ma_step=3.0,
    ma_range_low=60.0,
    ma_range_high=79.0,
    ma_velocity=60.0,
    ma_tac=0.0,
    ma_plus_minus_notes=0.0,
    ma_mv_even=0.2,
    ma_mv_odd=0.1,
    ma_orch_plus_minus=0.2,
    ma_orch_range_low=60.0,
    ma_orch_range_high=79.0,
    ma_trans=0.0,
    ha_tension=3.0,
    ha_cpx_prog=0.1,
    ha_plus_minus_notes=0.0,
    ha_acc_beat=0.3,
    ha_vel_ins=58.0,
    ha_voice_ins=2.0,
    ha_range_ins_low=float(HARMONY_RANGE[0]),
    ha_range_ins_high=float(HARMONY_RANGE[1]),
    ha_register_ins=1.0,
    ha_ins_plus_minus=0.2,
    ha_move=0.1,
    pa_vel_perc=48.0,
    pa_acc_beat_p=0.25,
    pa_ks_plus_minus=-0.2,
    pa_toms_plus_minus=-0.3,
    pa_cymb_plus_minus=-0.4,
    seeded_phrase_length=6.0,
    shape_depth=3.0,
    shape_length=6.0,
)

# C: Corner (0,1) - Tense / driving / danger combat (-V, +A)
PRESET_C = Preset(
    ma_step=8.0,
    ma_range_low=52.0,
    ma_range_high=80.0,
    ma_velocity=105.0,
    ma_tac=0.0,
    ma_plus_minus_notes=0.5,
    ma_mv_even=0.3,
    ma_mv_odd=0.6,
    ma_orch_plus_minus=0.8,
    ma_orch_range_low=52.0,
    ma_orch_range_high=80.0,
    ma_trans=2.0,
    ha_tension=10.0,
    ha_cpx_prog=0.8,
    ha_plus_minus_notes=0.4,
    ha_acc_beat=0.8,
    ha_vel_ins=105.0,
    ha_voice_ins=4.0,
    ha_range_ins_low=float(HARMONY_RANGE[0]),
    ha_range_ins_high=float(HARMONY_RANGE[1]),
    ha_register_ins=3.0,
    ha_ins_plus_minus=0.8,
    ha_move=0.5,
    pa_vel_perc=115.0,
    pa_acc_beat_p=0.9,
    pa_ks_plus_minus=0.7,
    pa_toms_plus_minus=0.6,
    pa_cymb_plus_minus=0.7,
    seeded_phrase_length=2.0,
    shape_depth=7.0,
    shape_length=2.0,
)

# D: Corner (1,1) - Energetic / full / heroic triumphant (+V, +A)
PRESET_D = Preset(
    ma_step=5.0,
    ma_range_low=60.0,
    ma_range_high=84.0,
    ma_velocity=100.0,
    ma_tac=0.0,
    ma_plus_minus_notes=0.3,
    ma_mv_even=0.4,
    ma_mv_odd=0.3,
    ma_orch_plus_minus=1.0,
    ma_orch_range_low=60.0,
    ma_orch_range_high=84.0,
    ma_trans=0.0,
    ha_tension=5.0,
    ha_cpx_prog=0.6,
    ha_plus_minus_notes=0.3,
    ha_acc_beat=0.6,
    ha_vel_ins=100.0,
    ha_voice_ins=4.0,
    ha_range_ins_low=float(HARMONY_RANGE[0]),
    ha_range_ins_high=float(HARMONY_RANGE[1]),
    ha_register_ins=4.0,
    ha_ins_plus_minus=1.0,
    ha_move=0.3,
    pa_vel_perc=100.0,
    pa_acc_beat_p=0.8,
    pa_ks_plus_minus=0.5,
    pa_toms_plus_minus=0.4,
    pa_cymb_plus_minus=0.5,
    seeded_phrase_length=4.0,
    shape_depth=5.0,
    shape_length=4.0,
)

DEFAULT_PRESETS = (PRESET_A, PRESET_B, PRESET_C, PRESET_D)


# ---------------------------------------------------------------------------
# Audio DSP, Reverb, and Dynamic Staging Configuration
# ---------------------------------------------------------------------------

AUDIO_CONFIG = {
    # FluidSynth Freeverb DSP parameters (Concert Hall)
    "reverb_enabled": True,
    "reverb_room_size": 0.80,    # 0.0 to 1.0 (Concert hall size, ~2.2s decay)
    "reverb_damping": 0.35,      # 0.0 to 1.0 (High-frequency absorption / warmth)
    "reverb_width": 1.0,         # Stereo spread
    "reverb_level": 0.75,        # Wet return mix

    # Master gain headroom (avoids digital clipping when 8 tracks + drums play tutti)
    "master_gain": 0.65,

    # Per-channel reverb send depth (MIDI CC 91: 0..127)
    "channel_reverb_sends": {
        0: 85,  # Melody Strings (Deep orchestral wash)
        1: 55,  # Melody Piano (Front stage clarity)
        2: 70,  # Melody Woodwinds / Flute (Airy bloom)
        3: 75,  # Melody Brass (Resonant projection)
        4: 85,  # Harmony Strings (Lush sustained bed)
        5: 55,  # Harmony Piano (Clean arpeggios with hall halo)
        6: 70,  # Harmony Woodwinds
        7: 75,  # Harmony Brass
        9: 25,  # Percussion (Tight kick/snare transients)
    },

    # Per-channel volume balance (MIDI CC 7: 0..127) — Lead melody soloist pocket
    "channel_volumes": {
        0: 110, # Melody Strings (Lead)
        1: 105, # Melody Piano (Lead)
        2: 110, # Melody Woodwinds (Lead)
        3: 105, # Melody Brass (Lead)
        4: 95,  # Harmony Strings (Accompaniment bed)
        5: 95,  # Harmony Piano (Accompaniment bed)
        6: 90,  # Harmony Woodwinds
        7: 95,  # Harmony Brass
        9: 100, # Percussion
    },

    # Dynamic velocity calibration
    "velocity_floor": 15,         # Allows subtle pianissimo drum taps and ghost notes
    "velocity_ceiling": 120,      # Prevents harsh digital clipping
    "velocity_curve": "soft_knee", # 'linear', 'soft_knee', 'compressed'
}
