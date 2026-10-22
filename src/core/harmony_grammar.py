"""
Harmonic Progression Selector and Chord Pools Manager for PAMG.

Implements the Western tonal transition grammar (Augmented Transition Network)
and tiered Chord Pools Manager as specified in docs/technical-reference.md §4.1 and §4.3.
"""

import random
from typing import Dict, List, Optional, Tuple
from src.models.harmony_types import ChordDefinition, ChordPoolLevel
from src.core.chord_dictionary import create_chord_dictionary


# ---------------------------------------------------------------------------
# Transition Grammar Matrix
# ---------------------------------------------------------------------------
# Maps a Roman numeral to weighted outgoing transitions (next_roman, base_weight).
HARMONIC_TRANSITIONS: Dict[str, List[Tuple[str, float]]] = {
    # Tonic
    "I": [
        ("IV", 0.35),
        ("V", 0.30),
        ("ii", 0.15),
        ("vi", 0.10),
        ("V/V", 0.05),
        ("V/IV", 0.05),
    ],
    # Subdominant
    "IV": [
        ("V", 0.50),
        ("I", 0.25),
        ("ii", 0.15),
        ("vii°", 0.05),
        ("It+6", 0.05),
    ],
    "ii": [
        ("V", 0.60),
        ("vii°", 0.20),
        ("IV", 0.10),
        ("N7", 0.10),
    ],
    # Dominant
    "V": [
        ("I", 0.70),
        ("vi", 0.15),
        ("IV", 0.10),
        ("V/vi", 0.05),
    ],
    "vii°": [
        ("I", 0.80),
        ("V", 0.20),
    ],
    # Mediant / Submediant
    "vi": [
        ("ii", 0.40),
        ("IV", 0.35),
        ("V", 0.15),
        ("V/ii", 0.10),
    ],
    "iii": [
        ("vi", 0.50),
        ("IV", 0.30),
        ("ii", 0.20),
    ],
    # Secondary Dominants / Modifications (Mod tier 1)
    "V/V": [("V", 0.85), ("I", 0.15)],
    "V/ii": [("ii", 0.85), ("IV", 0.15)],
    "V/vi": [("vi", 0.85), ("IV", 0.15)],
    "V/IV": [("IV", 0.90), ("I", 0.10)],
    "ii/V": [("V/V", 0.50), ("V", 0.50)],
    "IV/IV": [("IV", 0.80), ("I", 0.20)],
    # Chromatic modifications (Mod tier 2)
    "N7": [("V", 0.75), ("I", 0.25)],
    "It+6": [("V", 0.90), ("I", 0.10)],
    "Fr+6": [("V", 0.90), ("I", 0.10)],
    "Ger+6": [("V", 0.90), ("I", 0.10)],
}


class HarmonicProgressionSelector:
    """
    Traverses the Roman-numeral chord grammar gated by the Chord Pools Manager.
    """

    def __init__(
        self,
        tonic_semitone: int = 0,
        complexity_progression: float = 0.0,
        mode: str = "major",
        seed: Optional[int] = None,
    ):
        """
        Initialize the progression selector.

        Args:
            tonic_semitone: Key root (0 = C, 2 = D, etc.).
            complexity_progression: Cpx Prog in [0.0..1.0] controlling pool reach.
            seed: Optional RNG seed.
        """
        self.tonic_semitone = tonic_semitone
        self.mode = self._normalize_mode(mode)
        self.complexity_progression = max(0.0, min(1.0, float(complexity_progression)))
        self.rng = random.Random(seed)
        self.dictionary = create_chord_dictionary(self.tonic_semitone, self.mode)

        self.current_roman = "I"
        self._last_pool_level = ChordPoolLevel.POOL_1

    def set_tonic(self, tonic_semitone: int) -> None:
        """Update the tonic root pitch center."""
        self.tonic_semitone = tonic_semitone % 12
        self.dictionary = create_chord_dictionary(self.tonic_semitone, self.mode)

    def set_mode(self, mode: str) -> None:
        """Switch the active major/minor tonal grammar."""
        normalized = self._normalize_mode(mode)
        if normalized != self.mode:
            self.mode = normalized
            self.dictionary = create_chord_dictionary(self.tonic_semitone, self.mode)
            self.current_roman = "I"
            self._last_pool_level = ChordPoolLevel.POOL_1

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode).strip().lower()
        if normalized not in {"major", "minor"}:
            raise ValueError("Harmony mode must be 'major' or 'minor'")
        return normalized

    def set_complexity(self, complexity_progression: float) -> None:
        """Update the Progression Complexity factor (Cpx Prog)."""
        self.complexity_progression = max(0.0, min(1.0, float(complexity_progression)))

    def get_max_reachable_pool(self) -> ChordPoolLevel:
        """
        Map continuous Cpx Prog in [0.0, 1.0] to maximum accessible ChordPoolLevel (1..4).
        """
        if self.complexity_progression < 0.25:
            return ChordPoolLevel.POOL_1
        elif self.complexity_progression < 0.55:
            return ChordPoolLevel.POOL_2
        elif self.complexity_progression < 0.85:
            return ChordPoolLevel.POOL_3
        return ChordPoolLevel.POOL_4

    def get_current_chord(self) -> ChordDefinition:
        """Return the active ChordDefinition."""
        return self.dictionary.get(self.current_roman, self.dictionary["I"])

    def advance_progression(self) -> ChordDefinition:
        """
        Transition to the next harmonic state based on the ATN grammar and reachable pools.

        Returns:
            ChordDefinition: The newly selected chord.
        """
        max_pool = self.get_max_reachable_pool()
        candidates = HARMONIC_TRANSITIONS.get(self.current_roman, [("I", 1.0)])

        # Filter candidates by reachable pool level
        valid_candidates = []
        valid_weights = []
        for target_roman, weight in candidates:
            chord_def = self.dictionary.get(target_roman)
            if chord_def and chord_def.pool <= max_pool:
                valid_candidates.append(target_roman)
                valid_weights.append(weight)

        # Fallback to tonic if no candidates are reachable in current pool
        if not valid_candidates:
            next_roman = "I"
        else:
            next_roman = self.rng.choices(valid_candidates, weights=valid_weights, k=1)[0]

        self.current_roman = next_roman
        selected_chord = self.get_current_chord()
        self._last_pool_level = selected_chord.pool
        return selected_chord

    def is_pool_1(self) -> bool:
        """Check if currently active chord belongs to Chord Pool #1."""
        return self.get_current_chord().pool == ChordPoolLevel.POOL_1
