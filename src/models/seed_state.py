"""
Shared SeedState model representing dual pitch and rhythm seeds.
Aligned with PAMG dissertation specification (§7.1, Fig. 7 and S2 §3.2.2).
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class SeedState:
    """
    Explicit SeedState object representing the dual pitch and rhythm seeds
    driven by the Seeded Phrase Generator (§7.1, Fig. 7).
    """

    base_seed: int
    current_seed: int
    rhythm_seed: int

    def __iter__(self):
        """Allow unpacking: pitch_seed, rhythm_seed = seed_state."""
        yield self.current_seed
        yield self.rhythm_seed

    def __int__(self) -> int:
        """Allow casting to int for backwards compatibility returning pitch seed."""
        return int(self.current_seed)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, SeedState):
            return (
                self.base_seed == other.base_seed
                and self.current_seed == other.current_seed
                and self.rhythm_seed == other.rhythm_seed
            )
        if isinstance(other, int):
            return self.current_seed == other
        return False
