import random

from src.core.logger import Logger
from src.models.seed_state import SeedState

logger = Logger()


class SeededPhraseGenerator:
    """
    Manages seed generation for the PAMG Agent Network.

    Provides two modes of operation depending on whether `base_seed` is zero:

    Deterministic mode (base_seed != 0)
    ------------------------------------
    Seeds are derived from a fixed base_seed using a seeded RNG, so the same
    base_seed + phrase_length always produces the same sequence of seeds.
    A new seed is only issued when the Harmony Agent reports Chord Pool == 1,
    ensuring seed changes align with harmonic phrase boundaries. Agents
    receiving the new seed will generate consistent motif variations that fit
    the current chord context. Dual seeds (pitch and rhythm) are produced (§7.1, S2 §3.2.2).

    Improvisation mode (base_seed == 0)
    ------------------------------------
    Seeds are drawn from os-level entropy on every clock tick, producing
    spontaneous, non-repeating musical variations independent of any base seed
    or phrase length. Suitable for live performance contexts.

    Attributes:
        base_seed (int):        The user-supplied base seed. 0 activates
                                improvisation mode.
        current_seed (int):     The most recently issued pitch seed value.
        rhythm_seed (int):      The most recently issued rhythm seed value.
        seed_state (SeedState): Explicit atomic SeedState container.
    """

    def __init__(self, base_seed: int):
        self.base_seed = int(base_seed)
        self.current_seed = self.base_seed
        self.rhythm_seed = self.base_seed
        self.seed_state = SeedState(
            base_seed=self.base_seed,
            current_seed=self.current_seed,
            rhythm_seed=self.rhythm_seed,
        )

        self._improvisation_mode = self.base_seed == 0
        # The documented gate is re-entry into Chord Pool 1, not continued
        # residence in Pool 1.  None means that no pool has been observed yet.
        self._previous_chord_pool = None

        if self._improvisation_mode:
            self._system_rng = random.SystemRandom()
            self._rng = random.Random()
            self._rhythm_rng = random.Random()
        else:
            self._system_rng = None
            self._rng = random.Random(self.base_seed)
            self._rhythm_rng = random.Random(self.base_seed + 10007 if self.base_seed != 0 else 0)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_chord_change(
        self,
        current_chord_pool: int,
        phrase_length: int,
    ) -> SeedState:
        """
        Evaluate whether a new seed should be issued and return the active SeedState.

        Deterministic mode uses the chord-pool transition gate. Improvisation
        mode ignores that gate and changes on every call.
        """
        safe_phrase_length = max(1, int(phrase_length))

        # ------------------------------------------------------------------
        # Branch 1 — Improvisation mode
        # ------------------------------------------------------------------
        if self._improvisation_mode:
            self.current_seed = self._system_rng.randint(1, 2**31 - 1)
            self.rhythm_seed = self._system_rng.randint(1, 2**31 - 1)
            self.seed_state = SeedState(
                base_seed=self.base_seed,
                current_seed=self.current_seed,
                rhythm_seed=self.rhythm_seed,
            )
            logger.info(
                "[Phrase Gen] Improvisation mode: New pitch seed = %d, rhythm seed = %d"
                % (self.current_seed, self.rhythm_seed)
            )
            return self.seed_state

        # ------------------------------------------------------------------
        # Branch 2 — Deterministic mode, Chord Pool == 1
        # ------------------------------------------------------------------
        entered_pool_1 = (
            int(current_chord_pool) == 1
            and self._previous_chord_pool is not None
            and self._previous_chord_pool != 1
        )
        self._previous_chord_pool = int(current_chord_pool)

        if entered_pool_1:
            # §7.1 defines the new value as a seeded random draw bounded by
            # the configured phrase length, then added to the base seed.
            random_offset = self._rng.randrange(safe_phrase_length)
            rhythm_offset = self._rhythm_rng.randrange(safe_phrase_length)
            self.current_seed = self.base_seed + random_offset
            self.rhythm_seed = self.base_seed + rhythm_offset

            self._rng.seed(self.current_seed)
            self._rhythm_rng.seed(self.rhythm_seed)
            self.seed_state = SeedState(
                base_seed=self.base_seed,
                current_seed=self.current_seed,
                rhythm_seed=self.rhythm_seed,
            )
            logger.info(
                "[Phrase Gen] Chord Pool 1: New pitch seed = %d, rhythm seed = %d"
                % (self.current_seed, self.rhythm_seed)
            )
            return self.seed_state

        # ------------------------------------------------------------------
        # Branch 3 — Deterministic mode, Chord Pool != 1
        # ------------------------------------------------------------------
        logger.info(
            "[Phrase Gen] Chord Pool %d: Using existing pitch seed = %d, rhythm seed = %d"
            % (current_chord_pool, self.current_seed, self.rhythm_seed)
        )
        return self.seed_state
