"""
Harmony data types and chord definitions for PAMG.

Defines the core data structures for the Roman-numeral chord grammar,
chord pool levels, and precomputed chord dictionary structures.
Aligned with docs/technical-reference.md §4.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple


class ChordPoolLevel(IntEnum):
    """
    Chord pool complexity levels as defined in PAMG technical reference §2.3 & §4.1.

    POOL_1: Primary diatonic triads (I, IV, V) - sole gate for Seeded Phrase Generator.
    POOL_2: Full diatonic chords (ii, iii, vi, vii°).
    POOL_3: Secondary dominants and subdominant modifications (V/V, V/ii, etc.).
    POOL_4: Chromatic tension-linked modifications (Neapolitan N7, Italian+, French+, German+).
    """
    POOL_1 = 1
    POOL_2 = 2
    POOL_3 = 3
    POOL_4 = 4


@dataclass(frozen=True)
class ChordDefinition:
    """
    Definition of a harmonic chord in the progression grammar.

    Attributes:
        symbol: Short display identifier (e.g., 'C', 'G7', 'Dm', 'N6').
        roman: Roman numeral representation (e.g., 'I', 'V', 'ii', 'V/V', 'N7').
        root_semitone: Semitone offset from tonic in [0..11] (e.g., C=0, G=7).
        quality: Chord harmonic quality ('major', 'minor', 'dominant', 'diminished').
        pool: Complexity pool level (1..4) governing reachability.
        ordered_pitch_classes: 12-level ordered pitch classes (semitones 0..11).
    """
    symbol: str
    roman: str
    root_semitone: int
    quality: str
    pool: ChordPoolLevel
    ordered_pitch_classes: Tuple[int, ...]
