"""Melody agent for stochastic melodic line generation."""

import logging
import random
from enum import Enum
from typing import Iterable, List, Optional, Tuple, Union


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
        self.total_pulses = self.loop_size * self.grain
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
        self.non_repeat = True  # Baseline GUI Non-Repeat toggle (§3.3)
        self.ma_tac = 0.0
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
        self._base_velocity = float(sum(self.velocity_range) / 2)
        self._velocity = self._base_velocity
        self._accent_boost_range = (6, 14)
        self._syncopation_boost_range = (8, 18)

        self.midi_channel = 0  # Default MIDI channel for melody

        # Local random generators for reproducibility: separate pitch and rhythm RNGs (§7.1, S2 §3.2.2)
        if seed is None:
            self._pitch_rng = random.Random()
            self._rhythm_rng = random.Random()
        else:
            self._pitch_rng = random.Random(seed)
            self._rhythm_rng = random.Random(seed)
        self._rng = self._pitch_rng  # Backwards compatibility alias

        self._onset_indices = set()
        self._moved_list = set()
        self._accent_beats = set()
        self._contour_pitches = {}
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
        if normalized in ("dcontour", "drunk_contour"):
            return "dcontour"
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

        # Mean-reversion pull towards target base velocity (§2.2, §3.4)
        pull = (self._base_velocity - self._velocity) * 0.35
        self._velocity = self._clamp_velocity(self._velocity + pull + step)
        velocity = int(round(self._velocity))

        # Scale transient boost proportionally to current dynamic level
        dynamic_scale = max(0.3, min(1.2, self._base_velocity / 80.0))
        if is_syncopated:
            raw_boost = self._rng.randint(*self._syncopation_boost_range)
            velocity += int(round(raw_boost * dynamic_scale))
        elif is_accent:
            raw_boost = self._rng.randint(*self._accent_boost_range)
            velocity += int(round(raw_boost * dynamic_scale))

        return self._clamp_velocity(velocity)

    def _next_pitch_step(self, index: Optional[int] = None) -> int:
        if self.drunk_mode == "dcontour":
            return self._next_contour_step(index)
        low, high = self.pitch_range
        step = self._pitch_rng.randint(-self.max_step, self.max_step)
        if low <= self.current_pitch <= high:
            next_p = self.current_pitch + step
            if next_p > high:
                next_p = high - (next_p - high)
            elif next_p < low:
                next_p = low + (low - next_p)
            next_p = max(low, min(high, next_p))
            return next_p - self.current_pitch
        return step

    def _next_contour_step(self, index: Optional[int] = None) -> int:
        """
        Contour step generator (§2.3.1, §3.3).
        Interpolates pitch between Moved List onsets.
        """
        if index is not None and index in self._contour_pitches:
            return self._contour_pitches[index] - self.current_pitch
        return self._pitch_rng.randint(-self.max_step, self.max_step)

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
        moved_list = set()

        accent_beats = {0}
        syncopation_choices = self._preferred_syncopation_subdivisions()

        for beat in range(self.loop_size):
            if beat != 0 and self._rhythm_rng.random() < self.accent_probability:
                accent_beats.add(beat)

            if self._rhythm_rng.random() < self.sub_probability:
                onset_indices.discard(beat * self.grain)

            if self._rhythm_rng.random() < self.add_probability:
                if syncopation_choices:
                    subdivision = self._rhythm_rng.choice(syncopation_choices)
                    idx = beat * self.grain + subdivision
                    onset_indices.add(idx)
                    moved_list.add(idx)

            if self._rhythm_rng.random() < self.syncopation_probability:
                if syncopation_choices:
                    subdivision = self._rhythm_rng.choice(syncopation_choices)
                    idx = beat * self.grain + subdivision
                    onset_indices.add(idx)
                    moved_list.add(idx)

        self._onset_indices = onset_indices
        self._moved_list = moved_list
        self._accent_beats = accent_beats
        self._build_contour_pitches()

    def _build_contour_pitches(self) -> None:
        """
        Build pitch contour for dcontour mode (§2.3.1, §3.3).
        Generates pitch values at Moved List nodes via drunk walk,
        and explicitly interpolates between them for intermediate onsets.
        """
        self._contour_pitches = {}
        if not self._onset_indices:
            return

        sorted_onsets = sorted(self._onset_indices)
        # Anchor nodes: loop boundaries plus all Moved List onsets
        nodes = sorted(list(self._moved_list | {sorted_onsets[0], sorted_onsets[-1]}))

        node_pitches = {}
        low, high = self.pitch_range
        current = max(low, min(high, self.current_pitch))
        for node in nodes:
            step = self._pitch_rng.randint(-self.max_step, self.max_step)
            current += step
            if current > high:
                current = high - (current - high)
            elif current < low:
                current = low + (low - current)
            current = max(low, min(high, current))
            node_pitches[node] = current

        # Interpolate between nodes for all onsets
        for idx in sorted_onsets:
            if idx in node_pitches:
                self._contour_pitches[idx] = node_pitches[idx]
            else:
                left = max([n for n in nodes if n <= idx], default=nodes[0])
                right = min([n for n in nodes if n >= idx], default=nodes[-1])
                if right == left:
                    self._contour_pitches[idx] = node_pitches[left]
                else:
                    t = (idx - left) / (right - left)
                    p = node_pitches[left] + t * (node_pitches[right] - node_pitches[left])
                    self._contour_pitches[idx] = max(low, min(high, int(round(p))))

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
            self._shape_steps_remaining = max(0.25, float(self.shape_length))
            self._shape_direction = self._rng.choice([-1, 1])

        step = self._rng.randint(0, max(1, int(self.shape_depth)))
        self._phrase_transpose += step * self._shape_direction
        self._phrase_transpose = max(
            -self._max_phrase_transpose,
            min(self._max_phrase_transpose, self._phrase_transpose),
        )
        self._shape_steps_remaining -= 1

    def get_lookahead(self, current_index: int, lookahead_steps: int) -> List[bool]:
        """
        Query upcoming melodic onsets within a future window.

        Args:
            current_index (int): Starting index for the query.
            lookahead_steps (int): Number of steps to look ahead.

        Returns:
            List[bool]: Boolean list indicating whether each step has an onset.
        """
        onsets = []
        for i in range(lookahead_steps):
            idx = (current_index + i) % self.total_pulses
            onsets.append(idx in self._onset_indices)
        return onsets

    def get_accent_list(self) -> List[int]:
        """Return a sorted list of accent beats for the current loop.

        Returns:
            List[int]: Beat indices marked as accents.
        """
        return sorted(self._accent_beats)

    def get_moved_list(self) -> List[int]:
        """Return the current loop's syncopation-moved onset indexes."""
        return sorted(self._moved_list)

    def _select_duration(
        self,
        pulse_duration: float,
        subdivision: int,
        onset_index: Optional[int] = None,
    ) -> float:
        """
        Compute note duration based on inter-onset distance classification (§3.2).
        STACCATO if gap to next onset <= threshold else LEGATO.
        """
        base = pulse_duration * (
            self.grain if subdivision == 0 else max(1, self.grain // 2)
        )
        if onset_index is not None and self._onset_indices:
            sorted_onsets = sorted(self._onset_indices)
            try:
                curr_pos = sorted_onsets.index(onset_index)
                if curr_pos < len(sorted_onsets) - 1:
                    gap = sorted_onsets[curr_pos + 1] - onset_index
                else:
                    gap = (self.loop_size * self.grain) - onset_index + sorted_onsets[0]
            except ValueError:
                gap = self.grain

            threshold = max(1, self.grain // 2)
            if gap <= threshold:
                duration = base * 0.5   # STACCATO
            else:
                duration = base * 1.05  # LEGATO
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
        current_chord_pcs: Optional[Iterable[int]] = None,
    ) -> List[dict]:
        """Process a single clock tick and emit melody events.

        Args:
            index (int): Current tick index.
            current_chord (Optional[List[int]]): Harmony chord tones.
            pulse_duration (Optional[float]): Pulse duration in seconds.
            current_chord_pcs (Optional[Iterable[int]]): Active chord pitch classes (0..11).

        Returns:
            List[dict]: Raw melody event dictionaries.
        """
        beat = index // self.grain
        subdivision = index % self.grain
        events = []

        # Tacet is a documented GUI control for silencing the Melody Agent.
        # Keep the control at the agent boundary so orchestration cannot revive
        # a muted melody stream.
        if getattr(self, "ma_tac", 0.0) >= 0.5:
            return events

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

        # =============== Melody Pitches Generation ('Drunk Walk' / 'dcontour') ===============
        step = self._next_pitch_step(index)
        raw_pitch = self.current_pitch + step + self._phrase_transpose

        # =============== Harmony Filter (§2.3.3) ===============
        # Note: Local pitch range clamping is intentionally removed before
        # the Harmony Filter. Pitch in harmony feeds OrchestratorAgent directly,
        # which is solely responsible for instrument range clamping (§6.1, §5.3).
        chord_pcs = set()
        if current_chord_pcs:
            chord_pcs = set(pc % 12 for pc in current_chord_pcs)
        elif current_chord:
            chord_pcs = set(note % 12 for note in current_chord)

        if chord_pcs:
            octave_center = (raw_pitch // 12) * 12
            candidates = []
            for oct_offset in (-12, 0, 12):
                for pc in chord_pcs:
                    candidates.append(octave_center + oct_offset + pc)
            sorted_candidates = sorted(candidates, key=lambda c: abs(c - raw_pitch))
            if getattr(self, "non_repeat", True) and len(sorted_candidates) > 1 and sorted_candidates[0] == self.current_pitch:
                filtered_pitch = sorted_candidates[1]
            else:
                filtered_pitch = sorted_candidates[0]
        else:
            filtered_pitch = raw_pitch

        logger.debug(
            "Melody pitch raw=%d filtered=%d range=%s",
            raw_pitch,
            filtered_pitch,
            self.pitch_range,
        )
        
        # Save this filtered pitch bounded by pitch_range as starting point for next step.
        low, high = self.pitch_range
        self.current_pitch = max(low, min(high, filtered_pitch))

        # =============== MIDI Event Construction ===============
        duration = None
        if pulse_duration is not None:
            duration = self._select_duration(pulse_duration, subdivision, onset_index=index)
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

        if "seed_state" in kwargs and kwargs["seed_state"] is not None:
            ss = kwargs["seed_state"]
            self._pitch_rng.seed(int(ss.current_seed))
            self._rhythm_rng.seed(int(ss.rhythm_seed))
            changed = True
        else:
            if "seed" in kwargs and kwargs["seed"] is not None:
                self._pitch_rng.seed(int(kwargs["seed"]))
                changed = True
            if "rhythm_seed" in kwargs and kwargs["rhythm_seed"] is not None:
                self._rhythm_rng.seed(int(kwargs["rhythm_seed"]))
                changed = True

        if "ma_step" in kwargs:
            new_max = int(kwargs["ma_step"])
            if new_max != self.max_step:
                self.max_step = max(1, new_max)
                changed = True

        if "ma_tac" in kwargs:
            new_tac = max(0.0, min(1.0, float(kwargs["ma_tac"])))
            if new_tac != getattr(self, "ma_tac", 0.0):
                self.ma_tac = new_tac
                changed = True

        if "ma_range_low" in kwargs and "ma_range_high" in kwargs:
            new_pr = (int(kwargs["ma_range_low"]), int(kwargs["ma_range_high"]))
            new_pr = self._normalize_pitch_range(new_pr)
            if new_pr != self.pitch_range:
                self.pitch_range = new_pr
                changed = True

        if "ma_velocity" in kwargs:
            new_vel = float(kwargs["ma_velocity"])
            if new_vel != self._base_velocity:
                self._base_velocity = new_vel
                self.velocity_range = (
                    max(15, int(self._base_velocity - 14)),
                    min(127, int(self._base_velocity + 16)),
                )
                self._velocity = self._clamp_velocity(new_vel)
                changed = True

        if "ma_trans" in kwargs:
            new_trans = int(kwargs["ma_trans"])
            if new_trans != self._phrase_transpose:
                self._phrase_transpose = new_trans
                changed = True

        if "ma_plus_minus_notes" in kwargs:
            delta = float(kwargs["ma_plus_minus_notes"])
            self.add_probability = max(0.0, min(1.0, 0.15 + delta * 0.3)) if delta > 0 else 0.15
            self.sub_probability = max(0.0, min(1.0, 0.10 - delta * 0.3)) if delta < 0 else 0.10
            changed = True
            pattern_changed = True

        if "ma_mv_even" in kwargs or "ma_mv_odd" in kwargs:
            even_w = float(kwargs.get("ma_mv_even", 0.5))
            odd_w = float(kwargs.get("ma_mv_odd", 0.5))
            self.movement = MelodyAgent.movement_type.even if even_w >= odd_w else MelodyAgent.movement_type.odd
            changed = True
            pattern_changed = True

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
            new_val = max(0.25, min(8.0, float(kwargs["shape_length"])))
            if new_val != self.shape_length:
                self.shape_length = new_val
                changed = True

        if "movement" in kwargs:
            new_val = self._normalize_movement(kwargs["movement"])
            if new_val != self.movement:
                self.movement = new_val
                changed = True
                pattern_changed = True

        if "loop_size" in kwargs:
            new_loop = max(1, int(kwargs["loop_size"]))
            if new_loop != self.loop_size:
                self.loop_size = new_loop
                self.total_pulses = self.loop_size * self.grain
                changed = True
                pattern_changed = True

        if "grain" in kwargs:
            new_grain = max(1, int(kwargs["grain"]))
            if new_grain != self.grain:
                self.grain = new_grain
                self.total_pulses = self.loop_size * self.grain
                changed = True
                pattern_changed = True

        if "meter" in kwargs and hasattr(self, "meter"):
            self.meter = kwargs["meter"]
            changed = True

        if pattern_changed:
            self._build_onset_pattern()

        return changed
