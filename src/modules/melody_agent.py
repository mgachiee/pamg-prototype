"""Melody agent for stochastic melodic line generation."""

import logging
import random
from enum import Enum
from typing import List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Melody agent
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)


class MelodyAgent:
    """
    Generate a melodic line aligned with the harmony context.

    The agent produces onset patterns, velocity contours, and pitch movement
    using stochastic rules that respond to the Harmony Agent's chord context.
    """
    # Enum namespaces for movement and pitch modes.
    movement_type = Enum("MovementType", "odd even")
    drunk_modes = Enum("DrunkModes", "drunk drunk_contour")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        movement: Union[movement_type, str],
        loop_size: int,
        grain: int,
        max_step: Optional[int] = 4,
        syncopation_probability: Optional[float] = None,
        accent_probability: Optional[float] = None,
        ratchet_probability: Optional[float] = None,
        pitch_range: Optional[Tuple[int, int]] = (48, 72),
        seed: Optional[int] = None,
        drunk_mode: str = "drunk",
        velocity_range: Tuple[int, int] = (60, 110),
        velocity_step: int = 6,
    ) -> None:
        """
        Initialize the melody agent and its random state.

        Args:
            movement (Union[movement_type, str]): Syncopation direction
                preference ("odd" or "even").
            loop_size (int): Number of beats in the loop.
            grain (int): Subdivision factor per beat.
            max_step (Optional[int]): Maximum step size in semitones.
            syncopation_probability (Optional[float]): Chance to add
                off-beat onsets.
            accent_probability (Optional[float]): Chance to accent beats.
            ratchet_probability (Optional[float]): Chance to ratchet hits.
            pitch_range (Optional[Tuple[int, int]]): Allowed MIDI range.
            seed (Optional[int]): RNG seed for reproducible output.
            drunk_mode (str): "drunk" or "drunk_contour".
            velocity_range (Tuple[int, int]): Allowed velocity range.
            velocity_step (int): Max step size for velocity walk.
        """
        self.movement = self._normalize_movement(movement)
        self.loop_size = loop_size
        self.grain = grain
        if max_step is None:
            self.max_step = 4
        else:
            self.max_step = max(1, int(max_step))

        # Numbers representing MIDI note values (C4 = 60, C#4/Db4 = 61,
        # D4 = 62, ..., C5 = 72).
        # Start at Middle C (C4).
        self.current_pitch = 60
        self.pitch_range = self._normalize_pitch_range(pitch_range)

        if syncopation_probability is None:
            self.syncopation_probability = 0.3
        else:
            self.syncopation_probability = float(syncopation_probability)

        if accent_probability is None:
            self.accent_probability = 0.0
        else:
            self.accent_probability = float(accent_probability)

        if ratchet_probability is None:
            self.ratchet_probability = 0.0
        else:
            self.ratchet_probability = float(ratchet_probability)

        self.drunk_mode = self._normalize_drunk_mode(drunk_mode)
        self._contour_direction = 1
        self._contour_steps_remaining = 0
        self._contour_min_steps = 3
        self._contour_max_steps = 7
        self._contour_turn_probability = 0.2

        self.add_probability = 0.15
        self.sub_probability = 0.1
        self.staccato_probability = 0.2
        self.legato_probability = 0.1
        self.shape_depth = 4
        self.shape_length = 4
        self._phrase_transpose = 0
        self._shape_steps_remaining = 0
        self._shape_direction = 1
        self._max_phrase_transpose = 12

        self.velocity_range = self._normalize_velocity_range(velocity_range)
        self._velocity_step = max(1, int(velocity_step))
        self._velocity = float(sum(self.velocity_range) / 2)
        self._accent_boost_range = (6, 14)
        self._syncopation_boost_range = (8, 18)

        self.midi_channel = 0  # Default MIDI channel for melody

        # Local random generator for reproducibility
        if seed is None:
            self._rng = random.Random()
        else:
            self._rng = random.Random(seed)

        self._onset_indices = set()
        self._accent_beats = set()
        self.on_loop_start(0)

    # ------------------------------------------------------------------
    # Event builders and normalization
    # ------------------------------------------------------------------

    def _build_midi(
        self,
        note: int,
        velocity: int,
        is_ratchet: bool = False,
        duration: Optional[float] = None,
    ) -> dict:
        return {
            "note": note,
            "velocity": velocity,
            # "syncopated": is_syncopated,
            "is_ratchet": is_ratchet,
            "ratchet_count": 3,
            "duration": duration,
            "channel": self.midi_channel,
        }

    def _normalize_pitch_range(
        self,
        pitch_range: Optional[Tuple[int, int]],
    ) -> Tuple[int, int]:
        if pitch_range is None:
            pitch_range = (48, 72)
        low = int(pitch_range[0])
        high = int(pitch_range[1])
        if low > high:
            low, high = high, low
        return low, high

    def _normalize_velocity_range(
        self,
        velocity_range: Tuple[int, int],
    ) -> Tuple[int, int]:
        low = max(1, min(127, int(velocity_range[0])))
        high = max(1, min(127, int(velocity_range[1])))
        if low > high:
            low, high = high, low
        return low, high

    def _normalize_drunk_mode(self, mode: Optional[str]) -> str:
        if mode is None:
            return "drunk"
        normalized = str(mode).strip().lower().replace("-", "_")
        if normalized == "drunk_contour":
            return "drunk_contour"
        return "drunk"

    def _normalize_movement(
        self,
        movement: Union[movement_type, str],
    ) -> movement_type:
        if isinstance(movement, MelodyAgent.movement_type):
            return movement

        normalized = str(movement).strip().lower()
        if normalized == "even":
            return MelodyAgent.movement_type.even
        return MelodyAgent.movement_type.odd

    def _clamp_velocity(self, velocity: float) -> int:
        low, high = self.velocity_range
        return max(low, min(high, int(round(velocity))))

    def _advance_velocity(
        self,
        is_syncopated: bool,
        is_accent: bool,
    ) -> int:
        step = self._rng.randint(-self._velocity_step, self._velocity_step)
        if is_syncopated:
            step += self._rng.randint(0, self._velocity_step)
        if is_accent:
            step += self._rng.randint(0, self._velocity_step)

        self._velocity = self._clamp_velocity(self._velocity + step)
        velocity = int(round(self._velocity))

        if is_syncopated:
            boost = self._rng.randint(*self._syncopation_boost_range)
            velocity += boost
        if is_accent:
            boost = self._rng.randint(*self._accent_boost_range)
            velocity += boost

        return self._clamp_velocity(velocity)

    def _next_pitch_step(self) -> int:
        if self.drunk_mode == "drunk_contour":
            return self._next_contour_step()
        return self._rng.randint(-self.max_step, self.max_step)

    def _next_contour_step(self) -> int:
        low, high = self.pitch_range
        if self._contour_steps_remaining <= 0:
            self._contour_direction = self._rng.choice([-1, 1])
            self._contour_steps_remaining = self._rng.randint(
                self._contour_min_steps,
                self._contour_max_steps,
            )

        if self.current_pitch >= high - 1:
            self._contour_direction = -1
        elif self.current_pitch <= low + 1:
            self._contour_direction = 1

        self._contour_steps_remaining -= 1

        step_size = self._rng.randint(1, max(1, self.max_step))
        step = step_size * self._contour_direction
        if self._rng.random() < self._contour_turn_probability:
            step = -max(1, step_size // 2) * self._contour_direction

        return step

    # ------------------------------------------------------------------
    # Pattern generation
    # ------------------------------------------------------------------

    def _preferred_syncopation_subdivisions(self) -> List[int]:
        subdivisions = list(range(1, self.grain))
        if not subdivisions:
            return []

        if self.movement == MelodyAgent.movement_type.odd:
            preferred = [sub for sub in subdivisions if sub % 2 == 1]
        else:
            preferred = [sub for sub in subdivisions if sub % 2 == 0]

        return preferred if preferred else subdivisions

    def _build_onset_pattern(self) -> None:
        base_onsets = [beat * self.grain for beat in range(self.loop_size)]
        onset_indices = set(base_onsets)

        accent_beats = {0}
        syncopation_choices = self._preferred_syncopation_subdivisions()

        for beat in range(self.loop_size):
            if beat != 0 and self._rng.random() < self.accent_probability:
                accent_beats.add(beat)

            if self._rng.random() < self.sub_probability:
                onset_indices.discard(beat * self.grain)

            if self._rng.random() < self.add_probability:
                if syncopation_choices:
                    subdivision = self._rng.choice(syncopation_choices)
                    onset_indices.add(beat * self.grain + subdivision)

            if self._rng.random() < self.syncopation_probability:
                if syncopation_choices:
                    subdivision = self._rng.choice(syncopation_choices)
                    onset_indices.add(beat * self.grain + subdivision)

        self._onset_indices = onset_indices
        self._accent_beats = accent_beats

    # ------------------------------------------------------------------
    # Loop/phrase lifecycle
    # ------------------------------------------------------------------

    def on_loop_start(self, loop_index: int) -> None:
        """Prepare onset and accent patterns for the new loop.

        Args:
            loop_index (int): Index of the current loop (unused).
        """
        _ = loop_index
        self._build_onset_pattern()

    def on_phrase_start(self) -> None:
        """Update the long-term transposition contour at phrase boundaries."""
        if self.shape_length <= 1:
            step = self._rng.randint(-self.shape_depth, self.shape_depth)
            self._phrase_transpose = step
            return

        if self._shape_steps_remaining <= 0:
            self._shape_steps_remaining = max(1, int(self.shape_length))
            self._shape_direction = self._rng.choice([-1, 1])

        step = self._rng.randint(0, max(1, int(self.shape_depth)))
        self._phrase_transpose += step * self._shape_direction
        self._phrase_transpose = max(
            -self._max_phrase_transpose,
            min(self._max_phrase_transpose, self._phrase_transpose),
        )
        self._shape_steps_remaining -= 1

    def get_accent_list(self) -> List[int]:
        """Return a sorted list of accent beats for the current loop.

        Returns:
            List[int]: Beat indices marked as accents.
        """
        return sorted(self._accent_beats)

    def _select_duration(
        self,
        pulse_duration: float,
        subdivision: int,
    ) -> float:
        base = pulse_duration * (
            self.grain if subdivision == 0 else max(1, self.grain // 2)
        )
        roll = self._rng.random()
        if roll < self.staccato_probability:
            duration = base * 0.5
        elif roll > 1.0 - self.legato_probability:
            duration = base * 1.1
        else:
            duration = base * 0.85

        return max(pulse_duration * 0.2, duration)

    # ------------------------------------------------------------------
    # Tick processing
    # ------------------------------------------------------------------

    def process_tick(
        self,
        index: int,
        current_chord: Optional[List[int]],
        pulse_duration: Optional[float] = None,
    ) -> List[dict]:
        """Process a single clock tick and emit melody events.

        Args:
            index (int): Current tick index.
            current_chord (Optional[List[int]]): Harmony chord tones.
            pulse_duration (Optional[float]): Pulse duration in seconds.

        Returns:
            List[dict]: Raw melody event dictionaries.
        """
        beat = index // self.grain
        subdivision = index % self.grain
        events = []

        # =============== Melody Rhythm Generation ===============
        if not self._onset_indices:
            self._build_onset_pattern()

        is_onset = index in self._onset_indices
        is_syncopated = is_onset and subdivision != 0

        if not is_onset:
            # No note on this tick.
            return events

        # =============== Velocity Generation ===============
        is_accent = is_syncopated or (beat in self._accent_beats)
        velocity = self._advance_velocity(
            is_syncopated=is_syncopated,
            is_accent=is_accent,
        )
        is_ratchet = self._rng.random() < self.ratchet_probability

        # =============== Melody Pitches Generation ('Drunk Walk') ===============
        # Randomly step up or down from the LAST played note. This creates
        # a sense of coherence, but the random stepping allows for
        # surprising twists and turns.
        step = self._next_pitch_step()
        raw_pitch = self.current_pitch + step + self._phrase_transpose

        # Keep it within the defined pitch range to avoid out-of-bounds
        # MIDI notes.
        raw_pitch = max(
            self.pitch_range[0],
            min(self.pitch_range[1], raw_pitch),
        )

        # =============== Harmony Filter ===============
        # The raw pitch might sound terrible. We must "snap" it to the
        # nearest valid pitch provided by the Harmony Agent's current chord.
        if current_chord:
            filtered_pitch = min(
                current_chord,
                key=lambda chord_note: abs(chord_note - raw_pitch),
            )
        else:
            filtered_pitch = raw_pitch

        logger.debug(
            "Melody pitch raw=%d filtered=%d range=%s",
            raw_pitch,
            filtered_pitch,
            self.pitch_range,
        )
        
        # Save this filtered pitch as the starting point for the next step.
        self.current_pitch = filtered_pitch

        # =============== MIDI Event Construction ===============
        duration = None
        if pulse_duration is not None:
            duration = self._select_duration(pulse_duration, subdivision)
        events.append(
            self._build_midi(
                note=filtered_pitch,
                velocity=velocity,
                is_ratchet=is_ratchet,
                duration=duration,
            )
        )
        
        return events
    
    # ------------------------------------------------------------------
    # Parameter updates
    # ------------------------------------------------------------------

    def update_params(self, **kwargs) -> bool:
        """Apply parameter updates for melody behavior.

        Supported keys:
            - seed
            - max_step
            - syncopation_probability
            - accent_probability
            - ratchet_probability
            - pitch_range
            - drunk_mode
            - velocity_range
            - velocity_step
            - add_probability
            - sub_probability
            - staccato_probability
            - legato_probability
            - shape_depth
            - shape_length
            - movement

        Returns:
            bool: True if any parameter changed.
        """

        changed = False
        pattern_changed = False

        if "seed" in kwargs:
            self._rng.seed(int(kwargs["seed"]))
            changed = True

        if "max_step" in kwargs:
            new_max = int(kwargs["max_step"])
            if new_max != self.max_step:
                self.max_step = max(1, new_max)
                changed = True

        if "pitch_range" in kwargs:
            pr = kwargs["pitch_range"]
            new_pr = self._normalize_pitch_range(pr)
            if new_pr != self.pitch_range:
                self.pitch_range = new_pr
                changed = True

        if "drunk_mode" in kwargs:
            new_mode = self._normalize_drunk_mode(kwargs["drunk_mode"])
            if new_mode != self.drunk_mode:
                self.drunk_mode = new_mode
                changed = True

        if "syncopation_probability" in kwargs:
            new_sync = float(kwargs["syncopation_probability"])
            if new_sync != self.syncopation_probability:
                self.syncopation_probability = new_sync
                changed = True
                pattern_changed = True

        if "accent_probability" in kwargs:
            new_accent = float(kwargs["accent_probability"])
            if new_accent != self.accent_probability:
                self.accent_probability = new_accent
                changed = True
                pattern_changed = True
        
        if "ratchet_probability" in kwargs:
            new_ratchet = float(kwargs["ratchet_probability"])
            if new_ratchet != self.ratchet_probability:
                self.ratchet_probability = new_ratchet
                changed = True

        if "velocity_range" in kwargs:
            new_range = self._normalize_velocity_range(
                kwargs["velocity_range"]
            )
            if new_range != self.velocity_range:
                self.velocity_range = new_range
                self._velocity = self._clamp_velocity(self._velocity)
                changed = True

        if "velocity_step" in kwargs:
            new_step = max(1, int(kwargs["velocity_step"]))
            if new_step != self._velocity_step:
                self._velocity_step = new_step
                changed = True

        if "add_probability" in kwargs:
            new_val = max(0.0, min(1.0, float(kwargs["add_probability"])))
            if new_val != self.add_probability:
                self.add_probability = new_val
                changed = True
                pattern_changed = True

        if "sub_probability" in kwargs:
            new_val = max(0.0, min(1.0, float(kwargs["sub_probability"])))
            if new_val != self.sub_probability:
                self.sub_probability = new_val
                changed = True
                pattern_changed = True

        if "staccato_probability" in kwargs:
            new_val = max(
                0.0, min(1.0, float(kwargs["staccato_probability"]))
            )
            if new_val != self.staccato_probability:
                self.staccato_probability = new_val
                changed = True

        if "legato_probability" in kwargs:
            new_val = max(0.0, min(1.0, float(kwargs["legato_probability"])))
            if new_val != self.legato_probability:
                self.legato_probability = new_val
                changed = True

        if "shape_depth" in kwargs:
            new_val = max(0, int(kwargs["shape_depth"]))
            if new_val != self.shape_depth:
                self.shape_depth = new_val
                changed = True

        if "shape_length" in kwargs:
            new_val = max(1, int(kwargs["shape_length"]))
            if new_val != self.shape_length:
                self.shape_length = new_val
                changed = True

        if "movement" in kwargs:
            new_val = self._normalize_movement(kwargs["movement"])
            if new_val != self.movement:
                self.movement = new_val
                changed = True
                pattern_changed = True

        if pattern_changed:
            self._build_onset_pattern()

        return changed