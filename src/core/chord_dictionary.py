"""
Chord dictionary and 12-level tension pitch-class construction for PAMG.

Implements the 12-ordered-level tension mechanics and precomputed chord lookup
as specified in docs/technical-reference.md §2.2, §4.1, and §4.2.
"""

from typing import Dict, List, Tuple
from src.models.harmony_types import ChordDefinition, ChordPoolLevel


# Ordered interval patterns (semitones relative to chord root) across 12 levels:
# Levels 1–3: Root triad (root, 5th, 3rd)
# Levels 4–7: Upper tertian extensions (7th, 9th, 11th, 13th)
# Levels 8–10: Borrowed parallel-minor / modal color tones
# Levels 11–12: Chromatic dissonances
CHORD_QUALITY_INTERVALS: Dict[str, Tuple[int, ...]] = {
    # Major (worked example in §4.2): [0, 7, 4, 11, 2, 5, 9, 3, 10, 8, 6, 1]
    "major": (0, 7, 4, 11, 2, 5, 9, 3, 10, 8, 6, 1),
    # Minor: [0, 7, 3, 10, 2, 5, 8, 4, 11, 9, 6, 1]
    "minor": (0, 7, 3, 10, 2, 5, 8, 4, 11, 9, 6, 1),
    # Dominant: [0, 7, 4, 10, 2, 5, 9, 3, 8, 11, 6, 1]
    "dominant": (0, 7, 4, 10, 2, 5, 9, 3, 8, 11, 6, 1),
    # Diminished: [0, 6, 3, 9, 2, 5, 10, 4, 7, 11, 1, 8]
    "diminished": (0, 6, 3, 9, 2, 5, 10, 4, 7, 11, 1, 8),
    # Functional chromatic forms named by the PAMG grammar.
    "neapolitan": (0, 4, 7, 10, 2, 5, 9, 3, 8, 11, 6, 1),
    "italian_aug6": (0, 4, 9, 7, 2, 5, 10, 3, 8, 11, 6, 1),
    "french_aug6": (0, 4, 6, 9, 2, 5, 10, 3, 8, 11, 7, 1),
    "german_aug6": (0, 4, 7, 9, 2, 5, 10, 3, 8, 11, 6, 1),
}


def build_ordered_pitch_classes(root_semitone: int, quality: str) -> Tuple[int, ...]:
    """
    Construct the 12 ordered pitch classes for a given root and chord quality.

    Args:
        root_semitone (int): Chord root in semitones relative to tonic (0..11).
        quality (str): Chord harmonic quality ('major', 'minor', 'dominant', 'diminished').

    Returns:
        Tuple[int, ...]: 12 pitch classes in [0..11].
    """
    intervals = CHORD_QUALITY_INTERVALS.get(quality, CHORD_QUALITY_INTERVALS["major"])
    return tuple((root_semitone + interval) % 12 for interval in intervals)


# ---------------------------------------------------------------------------
# Precomputed Chord Dictionary across the Western tonal grammar (§4.1)
# ---------------------------------------------------------------------------

def create_chord_dictionary(
    tonic_semitone: int = 0,
    mode: str = "major",
) -> Dict[str, ChordDefinition]:
    """
    Generate the dictionary of chords indexed by Roman numeral symbol.

    Args:
        tonic_semitone (int): Key center pitch class (0 = C).

    Returns:
        Dict[str, ChordDefinition]: Dictionary of chord definitions.
    """
    normalized_mode = str(mode).strip().lower()
    if normalized_mode not in {"major", "minor"}:
        raise ValueError("Harmony mode must be 'major' or 'minor'")

    # Natural-minor diatonic base: i, ii°, III, iv, v, VI, VII.
    if normalized_mode == "minor":
        diatonic = {
            "I": (0, "minor"),
            "IV": (5, "minor"),
            "V": (7, "minor"),
            "ii": (2, "diminished"),
            "iii": (3, "major"),
            "vi": (8, "major"),
            "vii°": (10, "major"),
        }
    else:
        diatonic = {
            "I": (0, "major"),
            "IV": (5, "major"),
            "V": (7, "major"),
            "ii": (2, "minor"),
            "iii": (4, "minor"),
            "vi": (9, "minor"),
            "vii°": (11, "diminished"),
        }

    # Raw specifications: (Roman, root_offset, quality, pool_level, display_symbol)
    specs = [
        # Pool 1: Primary diatonic (Reseed gate)
        ("I", *diatonic["I"], ChordPoolLevel.POOL_1, "I"),
        ("IV", *diatonic["IV"], ChordPoolLevel.POOL_1, "IV"),
        ("V", *diatonic["V"], ChordPoolLevel.POOL_1, "V"),

        # Pool 2: Full diatonic chords
        ("ii", *diatonic["ii"], ChordPoolLevel.POOL_2, "ii"),
        ("iii", *diatonic["iii"], ChordPoolLevel.POOL_2, "iii"),
        ("vi", *diatonic["vi"], ChordPoolLevel.POOL_2, "vi"),
        ("vii°", *diatonic["vii°"], ChordPoolLevel.POOL_2, "vii°"),

        # Pool 3: Secondary dominants & subdominants (Mod tier 1)
        ("V/V", 2, "dominant", ChordPoolLevel.POOL_3, "V/V"),      # D7 in C
        ("V/ii", 9, "dominant", ChordPoolLevel.POOL_3, "V/ii"),    # A7 in C
        ("V/vi", 4, "dominant", ChordPoolLevel.POOL_3, "V/vi"),    # E7 in C
        ("V/IV", 0, "dominant", ChordPoolLevel.POOL_3, "V/IV"),    # C7 in C
        ("ii/V", 9, "minor", ChordPoolLevel.POOL_3, "ii/V"),       # Am in C
        ("IV/IV", 10, "major", ChordPoolLevel.POOL_3, "IV/IV"),    # Bb in C

        # Pool 4: Chromatic tension-linked modifications (Mod tier 2)
        ("N7", 1, "neapolitan", ChordPoolLevel.POOL_4, "N7"),
        ("It+6", 8, "italian_aug6", ChordPoolLevel.POOL_4, "It+6"),
        ("Fr+6", 8, "french_aug6", ChordPoolLevel.POOL_4, "Fr+6"),
        # German+ is functionally treated as V7/bII by the reference grammar.
        ("Ger+6", 1, "german_aug6", ChordPoolLevel.POOL_4, "V7/bII"),
    ]

    chords = {}
    for roman, root_offset, quality, pool, symbol in specs:
        actual_root = (tonic_semitone + root_offset) % 12
        ordered_pcs = build_ordered_pitch_classes(actual_root, quality)
        chords[roman] = ChordDefinition(
            symbol=symbol,
            roman=roman,
            root_semitone=actual_root,
            quality=quality,
            pool=pool,
            ordered_pitch_classes=ordered_pcs,
        )
    return chords


def get_voiced_pitch_classes(
    chord: ChordDefinition,
    tension_level: int,
    voice_count: int = 3,
) -> List[int]:
    """
    Select active sounding pitch classes from the 12-level table according to
    the voice_ins specification in §4.2:
    
    voiced_pitches(tension_level, voice_count) =
        last N of ordered_pitch_class_list[0 : tension_level]
        where N = voice_count

    Args:
        chord: The active ChordDefinition.
        tension_level: Tension index in [1..12].
        voice_count: Number of voicing voices (voice_ins) in [1..6].

    Returns:
        List[int]: Selected pitch classes in [0..11].
    """
    clamped_tension = max(1, min(12, int(tension_level)))
    clamped_voices = max(1, min(12, int(voice_count)))

    # Prefix unlocked by current tension level
    unlocked = chord.ordered_pitch_classes[:clamped_tension]

    # Select the most-recently-unlocked (right-most) N pitch classes
    voiced = list(unlocked[-clamped_voices:])
    return voiced


def query_pitch_class_set(
    chord_symbol: str,
    tension_level: int,
    tonic_semitone: int = 0,
    mode: str = "major",
) -> List[int]:
    """Query the active tension prefix for a chord symbol.

    This is the explicit runtime form of the documented chord-dictionary
    contract: ``(ChordSymbol, TensionLevel) -> PitchClassSet``.
    """
    dictionary = create_chord_dictionary(tonic_semitone, mode)
    chord = dictionary.get(chord_symbol)
    if chord is None:
        raise KeyError(f"Unknown chord symbol: {chord_symbol}")
    level = max(1, min(12, int(tension_level)))
    return list(chord.ordered_pitch_classes[:level])
