"""Harmony agent for chord selection and harmonic event generation."""

import random
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Harmony agent
# ---------------------------------------------------------------------------

from src.core.configs import HARMONY_TEMPLATE


class HarmonyAgent:
    """
    Generate chord progressions and harmonic MIDI events.

    The agent tracks a chord progression, applies tension-driven variation,
    and emits harmony events aligned to the global clock grid.
    """
    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        loop_size: int = 4,
        grain: int = 1,
        seed: Optional[int] = None,
        meter: Optional[str] = None,
        key_root: int = 60,
        scale_mode: str = "major",
    ):
        """
        Initialize the harmony agent and seed its progression state.

        Args:
            loop_size (int): Number of beats in the loop.
            grain (int): Subdivision factor per beat.
            seed (Optional[int]): RNG seed for reproducible output.
            meter (Optional[str]): Optional time signature key (e.g. "4/4").
            key_root (int): MIDI pitch for the tonic root.
            scale_mode (str): "major" or "minor" scale selection.
        """
        self.loop_size = max(1, int(loop_size))
        self.grain = max(1, int(grain))
        self.meter = meter
        self.key_root = int(key_root)
        self.scale_mode = scale_mode
        self._rng = random.Random(seed)
        self.chord_change_probability = 0.0
        self.chord_complexity = 0.0
        self.tension = 0.0
        self.harmony_add_probability = 0.0
        self.harmony_sub_probability = 0.0
        self.harmony_accent_probability = 0.0
        self._degree_progression: List[int] = []
        self._degree_index = 0
        self._scale_degrees = self._build_scale()
        self.chord_dictionary: Dict[int, List[int]] = {}
        self.borrowed_chord_dictionary: Dict[int, List[int]] = {}
        self._refresh_chord_dictionary()
        self._select_progression()
        self._current_chord: List[int] = self._build_chord_from_degree(
            self._degree_progression[self._degree_index]
        )
        self._last_measure_index: Optional[int] = None
        self._arpeggio_notes: List[int] = []
        self._arpeggio_step = 0
        self._accent_velocity_range = (90, 115)
        self._normal_velocity_range = (70, 95)
        self._accent_beats = set()
        self._post_filter: Optional[List[int]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_chord(self, measure_index: int) -> List[int]:
        """
        Return the chord for the current measure.

        Args:
            measure_index (int): Current measure index within the loop.

        Returns:
            List[int]: MIDI note numbers for the active chord.
        """
        # Determine the current chord based on the measure index
        # Ensure a progression is available before indexing it.
        if not self._degree_progression:
            self._select_progression()

        reset_arp = False

        if self._last_measure_index is None:
            self._degree_index = measure_index % len(self._degree_progression)
            self._last_measure_index = measure_index
            reset_arp = True
        elif measure_index != self._last_measure_index:
            if self._should_refresh_progression(measure_index):
                self._select_progression()
                self._degree_index = 0
            else:
                self._degree_index = (
                    self._degree_index + 1
                ) % len(self._degree_progression)
                if self._should_change_chord() and len(self._degree_progression) > 1:
                    self._degree_index = self._select_next_degree_index()
            self._last_measure_index = measure_index
            reset_arp = True

        # Build chord tones for the selected degree.
        degree = self._degree_progression[self._degree_index]
        self._current_chord = self._build_chord_from_degree(degree)
        if reset_arp:
            self._reset_arpeggiator()
        return list(self._current_chord)

    def notify_accents(self, accent_beats: List[int]) -> None:
        """
        Receive the melody accent beats to align harmony accents.

        Args:
            accent_beats (List[int]): Beat indices flagged as accents.
        """
        self._accent_beats = {int(beat) for beat in accent_beats}

    def set_post_filter(self, pitch_subset: Optional[List[int]]) -> None:
        """
        Apply or clear a pitch subset filter for the current chord.

        Args:
            pitch_subset (Optional[List[int]]): Allowed pitches or None to
                clear the filter.
        """
        if pitch_subset is None:
            self._post_filter = None
        else:
            self._post_filter = [int(pitch) for pitch in pitch_subset]

    def get_chord_pool(self) -> int:
        """
        Return the current chord pool identifier.

        Pool 1 is reserved for the first chord in the progression and is
        used by the seeded phrase generator.
        """
        if not self._degree_progression:
            return 1
        return 1 if self._degree_index == 0 else 2

    def process_tick(self, index: int, pulse_duration: float) -> List[dict]:
        """
        Generate harmony events for a single clock tick.

        Args:
            index (int): Current tick index in the loop.
            pulse_duration (float): Duration of a single pulse in seconds.

        Returns:
            List[dict]: Raw harmony event dictionaries.
        """
        beat = index // self.grain
        subdivision = index % self.grain

        events: List[dict] = []
        active_chord = self._get_active_chord()
        if not active_chord:
            return events

        is_chord_beat, is_accent_beat = self._accent_beat_follower(beat)

        if subdivision == 0:
            if is_chord_beat and self._rng.random() >= self.harmony_sub_probability:
                duration = pulse_duration * self.grain
                events.extend(
                    self._build_chord_events(
                        active_chord,
                        duration,
                        is_accent=is_accent_beat,
                    )
                )
            elif (not is_chord_beat) and self._rng.random() < self.harmony_add_probability:
                events.extend(
                    self._build_chord_events(active_chord, pulse_duration)
                )
        else:
            if self._should_arpeggiate() and self._arpeggio_notes:
                arp_event = self._build_arpeggio_event(pulse_duration)
                if arp_event:
                    events.append(arp_event)
            elif self._rng.random() < self._add_fill_prob():
                events.extend(
                    self._build_chord_events(active_chord, pulse_duration)
                )

        return events

    def update_params(self, **kwargs) -> bool:
        """
        Apply parameter updates for harmony behavior.

        Supported keys:
            - seed
            - chord_change_probability
            - chord_complexity
            - tension
            - harmony_add_probability
            - harmony_sub_probability
            - harmony_accent_probability
            - meter
            - key_root
            - scale_mode

        Returns:
            bool: True if any parameter changed.
        """
        changed = False

        if "seed" in kwargs:
            self._rng.seed(int(kwargs["seed"]))
            changed = True

        if "chord_change_probability" in kwargs:
            new_val = float(kwargs["chord_change_probability"])
            if new_val != self.chord_change_probability:
                self.chord_change_probability = new_val
                changed = True

        if "chord_complexity" in kwargs:
            new_val = float(kwargs["chord_complexity"])
            if new_val != self.chord_complexity:
                self.chord_complexity = new_val
                changed = True

        if "tension" in kwargs:
            new_val = float(kwargs["tension"])
            if new_val != self.tension:
                self.tension = new_val
                changed = True

        if "harmony_add_probability" in kwargs:
            new_val = float(kwargs["harmony_add_probability"])
            if new_val != self.harmony_add_probability:
                self.harmony_add_probability = self._clamp_prob(new_val)
                changed = True

        if "harmony_sub_probability" in kwargs:
            new_val = float(kwargs["harmony_sub_probability"])
            if new_val != self.harmony_sub_probability:
                self.harmony_sub_probability = self._clamp_prob(new_val)
                changed = True

        if "harmony_accent_probability" in kwargs:
            new_val = float(kwargs["harmony_accent_probability"])
            if new_val != self.harmony_accent_probability:
                self.harmony_accent_probability = self._clamp_prob(new_val)
                changed = True

        if "meter" in kwargs:
            new_val = kwargs["meter"]
            if new_val != self.meter:
                self.meter = new_val
                changed = True

        if "key_root" in kwargs:
            new_val = int(kwargs["key_root"])
            if new_val != self.key_root:
                self.key_root = new_val
                self._scale_degrees = self._build_scale()
                self._refresh_chord_dictionary()
                self._select_progression()
                changed = True

        if "scale_mode" in kwargs:
            new_val = str(kwargs["scale_mode"])
            if new_val != self.scale_mode:
                self.scale_mode = new_val
                self._scale_degrees = self._build_scale()
                self._refresh_chord_dictionary()
                self._select_progression()
                changed = True

        return changed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _should_change_chord(self) -> bool:
        if self.chord_change_probability >= 1.0:
            return True
        if self.chord_change_probability <= 0.0:
            return False
        return self._rng.random() < self.chord_change_probability

    def _should_refresh_progression(self, measure_index: int) -> bool:
        if measure_index != 0:
            return False
        return self._should_change_chord()

    def _select_next_degree_index(self) -> int:
        if not self._degree_progression:
            return 0
        if len(self._degree_progression) <= 1:
            return 0
        if self.chord_complexity < 0.5:
            return (self._degree_index + 1) % len(self._degree_progression)

        step_options = [1, 2, -1]
        for _ in range(4):
            step = self._rng.choice(step_options)
            candidate = (
                self._degree_index + step
            ) % len(self._degree_progression)
            if candidate != self._degree_index:
                return candidate
        return (self._degree_index + 1) % len(self._degree_progression)

    def _build_chord_from_degree(self, degree: int) -> List[int]:
        base_triad = self.chord_dictionary.get(degree)
        if base_triad is None:
            base_triad = self._build_triad_from_degree(degree)

        chord = list(base_triad)
        if not chord:
            return []

        if self._should_borrow_chord(degree):
            borrowed = self.borrowed_chord_dictionary.get(degree)
            if borrowed:
                chord = list(borrowed)

        root = chord[0]
        third = chord[1] if len(chord) > 1 else root + 4
        is_minor = (third - root) % 12 == 3

        if self.tension >= 0.7 and self._rng.random() < 0.25:
            chord = self._apply_suspension(chord, degree)

        if self.chord_complexity >= 0.5:
            seventh = root + (10 if is_minor else 11)
            chord.append(seventh)
        if self.chord_complexity >= 0.8:
            chord.append(root + 14)

        if self.chord_complexity >= 0.6 and self._rng.random() < 0.3:
            chord = self._apply_inversion(chord)

        return sorted(set(chord))

    def _reset_arpeggiator(self) -> None:
        self._arpeggio_notes = list(self._get_active_chord())
        self._arpeggio_step = 0

    def _should_arpeggiate(self) -> bool:
        return self.chord_complexity >= 0.7 or self.tension >= 0.7

    def _build_velocity(self, is_accent: bool) -> int:
        if is_accent or (self._rng.random() < self.harmony_accent_probability):
            low, high = self._accent_velocity_range
        else:
            low, high = self._normal_velocity_range
        return self._rng.randint(low, high)

    def _build_chord_events(
        self,
        chord: List[int],
        duration: float,
        is_accent: bool = False,
    ) -> List[dict]:
        velocity = self._build_velocity(is_accent=is_accent)
        return [
            {
                "note": note,
                "velocity": velocity,
                "duration": duration,
                "source": "harmony",
            }
            for note in chord
        ]

    def _build_arpeggio_event(self, duration: float) -> dict:
        if not self._arpeggio_notes:
            return {}

        note = self._arpeggio_notes[self._arpeggio_step % len(self._arpeggio_notes)]
        self._arpeggio_step += 1
        return {
            "note": note,
            "velocity": self._build_velocity(is_accent=False),
            "duration": duration,
            "source": "harmony",
        }

    def _get_template_key(self) -> str:
        if self.meter:
            return self.meter
        default_key = f"{self.loop_size}/4"
        if default_key in HARMONY_TEMPLATE:
            return default_key
        if self.loop_size == 6 and "6/8" in HARMONY_TEMPLATE:
            return "6/8"
        return default_key

    def _accent_beat_follower(self, beat: int) -> tuple:
        template = HARMONY_TEMPLATE.get(self._get_template_key(), {})
        chord_beats = template.get("CHORD", [])
        accent_beats = template.get("ACCENT", [])
        is_chord_beat = beat in chord_beats
        is_accent_beat = beat in accent_beats or beat in self._accent_beats
        return is_chord_beat, is_accent_beat

    def _get_active_chord(self) -> List[int]:
        if not self._current_chord:
            return []

        if not self._post_filter:
            return list(self._current_chord)

        filtered = [
            note for note in self._current_chord if note in self._post_filter
        ]
        return filtered if filtered else list(self._current_chord)

    def _build_scale(self) -> List[int]:
        return self._build_scale_for_mode(self.scale_mode)

    def _build_scale_for_mode(self, mode: str) -> List[int]:
        if mode == "minor":
            steps = [0, 2, 3, 5, 7, 8, 10]
        else:
            steps = [0, 2, 4, 5, 7, 9, 11]

        return [self.key_root + step for step in steps]

    def _build_triad_from_degree(self, degree: int) -> List[int]:
        if not self._scale_degrees:
            return []

        degree_index = (degree - 1) % len(self._scale_degrees)
        root = self._scale_degrees[degree_index]

        third_index = (degree_index + 2) % len(self._scale_degrees)
        fifth_index = (degree_index + 4) % len(self._scale_degrees)

        third = self._scale_degrees[third_index]
        fifth = self._scale_degrees[fifth_index]

        if third_index <= degree_index:
            third += 12
        if fifth_index <= degree_index:
            fifth += 12

        return [root, third, fifth]

    def _scale_note_for_degree_index(
        self,
        degree_index: int,
        base_note: int,
    ) -> int:
        if not self._scale_degrees:
            return base_note

        note = self._scale_degrees[degree_index % len(self._scale_degrees)]
        while note <= base_note:
            note += 12
        return note

    def _apply_suspension(self, chord: List[int], degree: int) -> List[int]:
        if len(chord) < 2:
            return chord

        degree_index = (degree - 1) % len(self._scale_degrees)
        sus_offset = self._rng.choice([1, 3])
        sus_note = self._scale_note_for_degree_index(
            degree_index + sus_offset,
            chord[0],
        )
        chord[1] = sus_note
        return chord

    def _apply_inversion(self, chord: List[int]) -> List[int]:
        if len(chord) < 3:
            return chord

        inversion = self._rng.choice([1, 2])
        for _ in range(inversion):
            chord.append(chord.pop(0) + 12)
        return chord

    def _refresh_chord_dictionary(self) -> None:
        self.chord_dictionary = {
            degree: self._build_triad_from_degree(degree)
            for degree in range(1, len(self._scale_degrees) + 1)
        }

        parallel_mode = "minor" if self.scale_mode == "major" else "major"
        parallel_scale = self._build_scale_for_mode(parallel_mode)
        self.borrowed_chord_dictionary = {
            degree: self._build_triad_from_scale(parallel_scale, degree)
            for degree in range(1, len(parallel_scale) + 1)
        }

    def _normalize_progression_length(self, progression: List[int]) -> List[int]:
        if not progression:
            return [1]
        if self.loop_size <= 0:
            return list(progression)
        if len(progression) == self.loop_size:
            return list(progression)
        if len(progression) < self.loop_size:
            repeated: List[int] = []
            while len(repeated) < self.loop_size:
                repeated.extend(progression)
            return repeated[: self.loop_size]
        return list(progression[: self.loop_size])

    def _select_progression(self) -> None:
        rules = self._progression_rules()
        eligible = [rule for rule in rules if self.tension >= rule[0]]
        if not eligible:
            eligible = rules[:1]

        _, progressions = eligible[-1]
        chosen = self._choose_weighted_progression(progressions)
        self._degree_progression = self._normalize_progression_length(chosen)
        self._degree_index = 0

    def _progression_rules(self) -> List[tuple]:
        if self.scale_mode == "minor":
            return [
                (
                    0.0,
                    [
                        ([1, 4, 5, 1], 3.0),
                        ([1, 6, 3, 7], 2.0),
                        ([1, 6, 7, 1], 1.5),
                        ([1, 4, 1, 5], 1.0),
                    ],
                ),
                (
                    0.4,
                    [
                        ([6, 4, 1, 5], 2.5),
                        ([2, 5, 1, 6], 2.0),
                        ([1, 4, 7, 3], 1.5),
                        ([6, 2, 5, 1], 1.0),
                    ],
                ),
                (
                    0.7,
                    [
                        ([1, 7, 3, 6], 2.5),
                        ([6, 2, 5, 1], 2.0),
                        ([1, 5, 6, 4], 1.5),
                        ([2, 7, 1, 6], 1.0),
                    ],
                ),
            ]

        return [
            (
                0.0,
                [
                    ([1, 4, 5, 1], 3.0),
                    ([1, 6, 4, 5], 2.0),
                    ([1, 5, 6, 4], 1.5),
                    ([1, 4, 1, 5], 1.0),
                ],
            ),
            (
                0.4,
                [
                    ([2, 5, 1, 6], 2.5),
                    ([1, 3, 6, 4], 2.0),
                    ([1, 4, 2, 5], 1.5),
                    ([6, 2, 5, 1], 1.0),
                ],
            ),
            (
                0.7,
                [
                    ([1, 7, 3, 6], 2.5),
                    ([6, 2, 5, 1], 2.0),
                    ([1, 3, 4, 5], 1.5),
                    ([2, 5, 6, 4], 1.0),
                ],
            ),
        ]

    def _choose_weighted_progression(
        self,
        weighted_progressions: List[tuple],
    ) -> List[int]:
        if not weighted_progressions:
            return [1]

        total = sum(weight for _, weight in weighted_progressions)
        if total <= 0:
            return list(weighted_progressions[0][0])

        roll = self._rng.random() * total
        cumulative = 0.0
        for progression, weight in weighted_progressions:
            cumulative += weight
            if roll <= cumulative:
                return list(progression)

        return list(weighted_progressions[-1][0])

    def _build_triad_from_scale(
        self,
        scale: List[int],
        degree: int,
    ) -> List[int]:
        if not scale:
            return []

        degree_index = (degree - 1) % len(scale)
        root = scale[degree_index]

        third_index = (degree_index + 2) % len(scale)
        fifth_index = (degree_index + 4) % len(scale)

        third = scale[third_index]
        fifth = scale[fifth_index]

        if third_index <= degree_index:
            third += 12
        if fifth_index <= degree_index:
            fifth += 12

        return [root, third, fifth]

    def _should_borrow_chord(self, degree: int) -> bool:
        if self.tension < 0.45:
            return False

        borrowable = {2, 4, 6, 7}
        if degree not in borrowable:
            return False

        probability = min(0.6, 0.15 + (self.tension * 0.6))
        return self._rng.random() < probability

    def _clamp_prob(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _add_fill_prob(self) -> float:
        return max(0.0, min(0.5, 0.1 + 0.4 * self.chord_complexity))

    def _sub_fill_prob(self) -> float:
        return max(0.0, min(0.4, 0.2 - 0.1 * self.chord_complexity))