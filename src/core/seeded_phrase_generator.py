import random

from src.core.logger import Logger

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
    ensuring seed changes align with harmonic phrase boundaries.  Agents
    receiving the new seed will generate consistent motif variations that fit
    the current chord context.

    Improvisation mode (base_seed == 0)
    ------------------------------------
    Seeds are drawn from os-level entropy on every chord change, producing
    spontaneous, non-repeating musical variations independent of any base seed
    or phrase length.  Suitable for live performance contexts.

    Attributes:
        base_seed (int):     The user-supplied base seed.  0 activates
                             improvisation mode.
        current_seed (int):  The most recently issued seed value.  Shared
                             with agents via `process_chord_change()`.
    """

    def __init__(self, base_seed: int):
        """
        Initialise the generator and select the operating mode.

        The constructor branches into two distinct RNG configurations:

        Deterministic mode (base_seed != 0):
            A single `random.Random` instance is seeded with `base_seed`.
            All subsequent random offsets are derived from this RNG, making
            the seed sequence reproducible for the same base_seed.
            `_system_rng` is set to None as it is not needed.

        Improvisation mode (base_seed == 0):
            Two RNG instances are created:
            • `_system_rng` (random.SystemRandom) — draws from OS entropy;
              used to generate unpredictable seed values each chord change.
            • `_rng` (random.Random, unseeded) — kept for structural
              consistency and potential future intra-session use; not
              currently used for offset generation in improvisation mode.

        Args:
            base_seed (int): Starting seed for deterministic generation, or
                             0 to activate improvisation (non-deterministic)
                             mode.
        """
        self.base_seed = base_seed
        self.current_seed = base_seed

        # Derive operating mode once at construction so every subsequent call
        # to process_chord_change() is a simple boolean branch.
        self._improvisation_mode = self.base_seed == 0

        if self._improvisation_mode:
            # Improvisation mode — use OS entropy for unpredictable seeds.
            # SystemRandom is not seedable and cannot be replayed; this is
            # intentional for free, non-repeating musical behaviour.
            self._system_rng = random.SystemRandom()

            # Unseeded Random kept for structural parity; not used for offsets
            # in this mode but available for any future intra-session needs.
            self._rng = random.Random()
        else:
            # Deterministic mode — seed the RNG with base_seed so the offset
            # sequence is fully reproducible given the same base_seed.
            self._system_rng = None
            self._rng = random.Random(self.base_seed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_chord_change(
        self,
        current_chord_pool: int,
        phrase_length: int,
    ) -> int:
        """
        Evaluate whether a new seed should be issued and return the active seed.

        This is the primary entry point for the scheduler or Harmony Agent
        callback.  It implements the seed-update decision gate from
        Duarte's PAMG fig. 7:

            ┌─────────────────────────────────┐
            │        process_chord_change     │
            └──────────────┬──────────────────┘
                           │
                  improvisation mode?
                  ┌────Yes─┴────No──────────────┐
                  ▼                             ▼
          new OS-entropy seed        Chord Pool == 1 ?
          (ignore base_seed)         ┌───Yes───┴────No──┐
                                     ▼                  ▼
                             compute new seed    return current_seed
                             (base + offset)     (no change)

        Deterministic mode — Chord Pool == 1:
            A random offset is drawn from `_rng` (seeded, reproducible) and
            scaled by `phrase_length`.  The new seed is:

                new_seed = base_seed + (rng.randint(1, 1000) * phrase_length)

            The internal RNG is then re-seeded with `new_seed` so subsequent
            calls within the same session build naturally on the previous state
            rather than restarting from base_seed.

        Deterministic mode — Chord Pool != 1:
            The existing `current_seed` is returned unchanged.  This keeps all
            agents locked to the same seed for the duration of the phrase,
            preserving musical cohesion across chord changes within a pool.

        Improvisation mode:
            A fresh OS-entropy integer in [1, 2³¹ − 1] is generated on every
            call regardless of `current_chord_pool` or `phrase_length`.

        Args:
            current_chord_pool (int): The Harmony Agent's current chord pool
                identifier.  Pool 1 is the "home" group that gates seed
                updates in deterministic mode.
            phrase_length (int): Length of the musical phrase in measures.
                Scales the random offset so longer phrases produce more
                widely spaced seed values.  Clamped to ≥ 1 to prevent
                zero-offset degeneration.

        Returns:
            int: The seed value agents should use for the current phrase.
                 Either a newly computed seed or the unchanged `current_seed`.
        """

        # Guard against non-positive phrase lengths (e.g., if the interpolator
        # or config yields 0).  A phrase_length of 0 would collapse all offsets
        # to 0, causing every Pool-1 change to return base_seed unchanged.
        safe_phrase_length = max(1, int(phrase_length))

        # ------------------------------------------------------------------
        # Branch 1 — Improvisation mode
        # ------------------------------------------------------------------
        if self._improvisation_mode:
            # Generate a fresh OS-entropy seed on every chord change.
            # The upper bound (2³¹ − 1) ensures compatibility with systems
            # that treat seeds as signed 32-bit integers.
            self.current_seed = self._system_rng.randint(1, 2**31 - 1)
            logger.info(
                "[Phrase Gen] Improvisation mode: New seed = %d (random offset)"
                % self.current_seed
            )
            return self.current_seed

        # ------------------------------------------------------------------
        # Branch 2 — Deterministic mode, Chord Pool == 1
        # ------------------------------------------------------------------
        if current_chord_pool == 1:
            # Scale the random offset by phrase_length so musically longer
            # phrases produce a larger seed "jump," increasing variation
            # proportionally to phrase complexity.
            random_offset = self._rng.randint(1, 1000) * safe_phrase_length
            self.current_seed = self.base_seed + random_offset

            # Re-seed the internal RNG with the new seed so the next Pool-1
            # event derives its offset from a different, but reproducible,
            # point in the pseudo-random sequence.
            self._rng.seed(self.current_seed)
            logger.info(
                "[Phrase Gen] Chord Pool 1: New seed = %d (offset %d)"
                % (self.current_seed, random_offset)
            )
            return self.current_seed

        # ------------------------------------------------------------------
        # Branch 3 — Deterministic mode, Chord Pool != 1
        # ------------------------------------------------------------------
        # Agents continue using the seed issued at the start of this phrase.
        # No update is applied, preserving inter-agent consistency for the
        # remainder of the harmonic phrase.
        logger.info(
            "[Phrase Gen] Chord Pool %d: Using existing seed = %d"
            % (current_chord_pool, self.current_seed)
        )
        return self.current_seed