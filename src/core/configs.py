from src.core.routing import RoutingType
from src.core.preset_interpolator import Preset

ROUTING_MODE = RoutingType.split_ports  # Options: RoutingType.single_port, RoutingType.split_ports
SINGLE_PORT_NAME = "Melody 1"
MELODY_PORT_NAME = "Melody 1"
DRUM_PORT_NAME = "Drums 2"
DEBUG_MIDI = False

# Orchestration channels (0-based MIDI channels).
MELODY_CHANNEL = 1
HARMONY_CHANNEL = 2
HARMONY_CHANNELS = [HARMONY_CHANNEL]
HARMONY_LAYER_WEIGHTS = [1.0]
HARMONY_LAYER_MODE = "probabilistic"

# Orchestration ranges (MIDI note bounds).
MELODY_RANGE = (48, 84)
HARMONY_RANGE = (40, 76)

# Orchestration programs (MIDI program numbers 0-127).
MELODY_PROGRAM = 0
HARMONY_PROGRAMS = [MELODY_PROGRAM]

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

# Default presets (corners of the XY pad)
# A: Exploration (calm)
PRESET_A = Preset(
    melody_max_step=2.0,
    melody_pitch_low=48.0,
    melody_pitch_high=72.0,
    melody_syncopation=0.12,
    melody_accent=0.65,
    melody_ratchet_probability=0.01,
    drum_kick_probability=0.85,
    drum_ghost_kick_probability=0.04,
    drum_snare_probability=1.0,
    drum_hat_open_probability=0.05,
    drum_hat_closed_probability=0.95,
    drum_ratchet_probability=0.01,
    seeded_phrase_length=4.0,
    harmony_tension=0.1,
    harmony_chord_complexity=0.2,
    harmony_chord_change_probability=0.05,
    harmony_add_probability=0.05,
    harmony_sub_probability=0.10,
    harmony_accent_probability=0.20,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
)

# B: Combat (active/aggressive)
PRESET_B = Preset(
    melody_max_step=6.0,
    melody_pitch_low=50.0,
    melody_pitch_high=80.0,
    melody_syncopation=0.35,
    melody_accent=0.95,
    melody_ratchet_probability=0.15,
    drum_kick_probability=0.98,
    drum_ghost_kick_probability=0.12,
    drum_snare_probability=1.0,
    drum_hat_open_probability=0.22,
    drum_hat_closed_probability=0.78,
    drum_ratchet_probability=0.12,
    seeded_phrase_length=2.0,
    harmony_tension=0.9,
    harmony_chord_complexity=0.8,
    harmony_chord_change_probability=0.6,
    harmony_add_probability=0.35,
    harmony_sub_probability=0.05,
    harmony_accent_probability=0.70,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
)

# C: Tension (sparse/tense)
PRESET_C = Preset(
    melody_max_step=4.0,
    melody_pitch_low=45.0,
    melody_pitch_high=72.0,
    melody_syncopation=0.22,
    melody_accent=0.75,
    melody_ratchet_probability=0.06,
    drum_kick_probability=0.90,
    drum_ghost_kick_probability=0.08,
    drum_snare_probability=0.95,
    drum_hat_open_probability=0.15,
    drum_hat_closed_probability=0.85,
    drum_ratchet_probability=0.05,
    seeded_phrase_length=6.0,
    harmony_tension=0.6,
    harmony_chord_complexity=0.5,
    harmony_chord_change_probability=0.2,
    harmony_add_probability=0.10,
    harmony_sub_probability=0.25,
    harmony_accent_probability=0.30,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
)

# D: Chaotic / high-energy
PRESET_D = Preset(
    melody_max_step=8.0,
    melody_pitch_low=40.0,
    melody_pitch_high=84.0,
    melody_syncopation=0.50,
    melody_accent=1.00,
    melody_ratchet_probability=0.30,
    drum_kick_probability=1.00,
    drum_ghost_kick_probability=0.20,
    drum_snare_probability=1.00,
    drum_hat_open_probability=0.35,
    drum_hat_closed_probability=0.65,
    drum_ratchet_probability=0.25,
    seeded_phrase_length=1.0,
    harmony_tension=1.0,
    harmony_chord_complexity=1.0,
    harmony_chord_change_probability=0.95,
    harmony_add_probability=0.50,
    harmony_sub_probability=0.05,
    harmony_accent_probability=0.90,
    harmony_pitch_low=float(HARMONY_RANGE[0]),
    harmony_pitch_high=float(HARMONY_RANGE[1]),
    harmony_layer_weights=list(HARMONY_LAYER_WEIGHTS),
    harmony_programs=list(HARMONY_PROGRAMS),
    melody_program=int(MELODY_PROGRAM),
    harmony_layer_mode=HARMONY_LAYER_MODE,
)

DEFAULT_PRESETS = (PRESET_A, PRESET_B, PRESET_C, PRESET_D)