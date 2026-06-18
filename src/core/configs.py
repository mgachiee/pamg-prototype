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

# Orchestration channels (0-based MIDI channels).
MELODY_CHANNELS = [0, 1]
HARMONY_CHANNEL = 2
HARMONY_CHANNELS = [2, 3, 4]
HARMONY_LAYER_WEIGHTS = [1.0, 0.8, 0.6]
HARMONY_LAYER_MODE = "probabilistic"

# Mapping of channels to instrument families.
# Used by OrchestratorAgent to look up ranges in FAMILY_RANGES.
CHANNEL_FAMILIES = {
    0: "strings",    # Melody 1
    1: "woodwinds",  # Melody 2 (Doubling)
    2: "keys",       # Harmony 1
    3: "brass",      # Harmony 2
    4: "bass",       # Harmony 3
}

# Orchestration ranges (MIDI note bounds).
MELODY_RANGE = (48, 84)
HARMONY_RANGE = (40, 76)

# Instrument families and their typical ranges.
# Used by OrchestratorAgent to override global ranges for specific channels.
FAMILY_RANGES = {
    "strings": (55, 96),
    "brass": (48, 84),
    "woodwinds": (60, 96),
    "keys": (21, 108),
    "bass": (24, 48),
}

# Orchestration programs (MIDI program numbers 0-127).
MELODY_PROGRAM = 0
HARMONY_PROGRAMS = [0, 48, 19] # Piano, Strings, Organ (matching 3 harmony channels)

# Percussion Template
PERCUSSION_TEMPLATE = {
    # X/Y - X for loop size (time signature), Y for grain (subdivision)
    "4/4": {
        "KICK": [0, 2],  # Kick on beats 1 and 3
        "SNARE": [1, 3],  # Snare on beats 2 and 4
        "HIHAT": [0, 1, 2, 3], # Hi-hat on every beat
        "TOM": [3], # Tom on the last beat of the loop (can be used for fills)
        "RIDE": [0, 1, 2, 3], # Often replaces the hi-hat during choruses or more open sections
        "CRASH": [0] # Accenting the downbeat of a new loop or section
    },
    "3/4": {
        "KICK": [0],
        "SNARE": [1, 2],
        "HIHAT": [0, 1, 2],
        "TOM": [2],
        "RIDE": [0, 1, 2],
        "CRASH": [0]
    },
    "5/4": {
        "KICK": [0, 3],
        "SNARE": [2, 4],
        "HIHAT": [0, 1, 2, 3, 4],
        "TOM": [4],
        "RIDE": [0, 1, 2, 3, 4],
        "CRASH": [0]
    },
    "7/4": {
        "KICK": [0, 2, 4],
        "SNARE": [1, 3, 5],
        "HIHAT": [0, 1, 2, 3, 4, 5, 6],
        "TOM": [6],
        "RIDE": [0, 1, 2, 3, 4, 5, 6],
        "CRASH": [0]
    },
    "6/8": {
        "KICK": [0, 3],
        "SNARE": [3],
        "HIHAT": [0, 1, 2, 3, 4, 5],
        "TOM": [4, 5],
        "RIDE": [0, 1, 2, 3, 4, 5],
        "CRASH": [0]
    }
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
}

# Game-state mapping defaults (used to normalize player/enemy values to [0..1])
MAX_HEALTH = 100.0
MAX_ENEMIES = 20.0

# Temporal smoothing (slew rate) for parameter transitions in seconds.
# Higher values make transitions more gradual and musical.
INTERPOLATION_SMOOTHING_TIME = 3.0

# Default presets (corners of the XY pad)
# A: (0,0) Quadrant 3 (Sad / -Valence, -Arousal)
# Health is low, few enemies - music should be subdued, minor key, with a sense of struggle.
PRESET_A = Preset(
    melody_max_step=2.0,
    melody_pitch_low=36.0,
    melody_pitch_high=55.0,
    melody_syncopation=0.10,
    melody_accent=0.35,
    melody_ratchet_probability=0.00,
    drum_kick_probability=0.35,
    drum_ghost_kick_probability=0.15,
    drum_snare_probability=0.25,
    drum_hat_open_probability=0.05,
    drum_hat_closed_probability=0.95,
    drum_ratchet_probability=0.01,
    seeded_phrase_length=8.0,
    harmony_tension=0.85,
    harmony_chord_complexity=0.45,
    harmony_chord_change_probability=0.02,
    harmony_add_probability=0.02,
    harmony_sub_probability=0.45,
    harmony_accent_probability=0.15,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
    scale_mode="aeolian",
)

# B: (1,0) Quadrant 4 (Calm / +Valence, -Arousal)
# Health is high, few enemies - music should be calm, consonant, with a sense of resilience.
PRESET_B = Preset(
    melody_max_step=3.0,
    melody_pitch_low=55.0,
    melody_pitch_high=72.0,
    melody_syncopation=0.05,
    melody_accent=0.20,
    melody_ratchet_probability=0.01,
    drum_kick_probability=0.12,
    drum_ghost_kick_probability=0.05,
    drum_snare_probability=0.05,
    drum_hat_open_probability=0.02,
    drum_hat_closed_probability=0.98,
    drum_ratchet_probability=0.00,
    seeded_phrase_length=6.0,
    harmony_tension=0.0,
    harmony_chord_complexity=0.15,
    harmony_chord_change_probability=0.05,
    harmony_add_probability=0.05,
    harmony_sub_probability=0.15,
    harmony_accent_probability=0.10,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
    scale_mode="major",
)

# C: (0,1) Quadrant 2 (Angry / -Valence, +Arousal)
# Health is low, many enemies - music should be aggressive, tense, and dissonant.
PRESET_C = Preset(
    melody_max_step=8.0,
    melody_pitch_low=40.0,
    melody_pitch_high=76.0,
    melody_syncopation=0.60,
    melody_accent=1.00,
    melody_ratchet_probability=0.25,
    drum_kick_probability=1.00,
    drum_ghost_kick_probability=0.25,
    drum_snare_probability=1.00,
    drum_hat_open_probability=0.45,
    drum_hat_closed_probability=0.55,
    drum_ratchet_probability=0.30,
    seeded_phrase_length=2.0,
    harmony_tension=1.0,
    harmony_chord_complexity=0.95,
    harmony_chord_change_probability=0.75,
    harmony_add_probability=0.50,
    harmony_sub_probability=0.02,
    harmony_accent_probability=0.85,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
    scale_mode="locrian",
)

# D: (1,1) Quadrant 1 (Excited / +Valence, +Arousal)
# Health is high, many enemies - music should be energetic, bright, and uplifting.
PRESET_D = Preset(
    melody_max_step=6.0,
    melody_pitch_low=60.0,
    melody_pitch_high=84.0,
    melody_syncopation=0.45,
    melody_accent=0.85,
    melody_ratchet_probability=0.08,
    drum_kick_probability=0.95,
    drum_ghost_kick_probability=0.10,
    drum_snare_probability=0.90,
    drum_hat_open_probability=0.25,
    drum_hat_closed_probability=0.75,
    drum_ratchet_probability=0.10,
    seeded_phrase_length=4.0,
    harmony_tension=0.25,
    harmony_chord_complexity=0.35,
    harmony_chord_change_probability=0.15,
    harmony_add_probability=0.20,
    harmony_sub_probability=0.05,
    harmony_accent_probability=0.40,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
    scale_mode="lydian",
)

DEFAULT_PRESETS = (PRESET_A, PRESET_B, PRESET_C, PRESET_D)