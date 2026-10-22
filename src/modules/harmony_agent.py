"""Harmony agent for chord selection, 12-level tension modeling, and harmonic event generation."""

import logging
import random
from typing import Dict, List, Optional, Tuple

from src.core.configs import HARMONY_TEMPLATE
from src.core.chord_dictionary import get_voiced_pitch_classes, query_pitch_class_set
from src.core.harmony_grammar import HarmonicProgressionSelector
from src.models.harmony_types import ChordDefinition, ChordPoolLevel

logger = logging.getLogger(__name__)


class HarmonyAgent:
    """
    Generate chord progressions, 12-level tension voicings, and harmonic MIDI events.

    The agent traverses a Western-tonal Roman-numeral transition grammar gated by
    a 4-tier Chord Pools Manager, constructs voicings via an ordered 12-level tension
    dictionary, and emits chord blocks, arpeggios, and bass lines.
    Aligned with docs/technical-reference.md §4.
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
        voice_count: int = 3,
        tension: float = 1.0,
        mode: str = "major",
        chord_complexity: float = 0.0,
        harmony_range: Tuple[int, int] = (48, 72),
        bass_range: Tuple[int, int] = (36, 48),
        velocity: float = 64.0,
    ):
        """
        Initialize the harmony agent and its progression engine.

        Args:
            loop_size (int): Number of beats in the loop.
            grain (int): Subdivision factor per beat.
            seed (Optional[int]): RNG seed for reproducible output.
            meter (Optional[str]): Optional time signature key (e.g. "4/4").
            key_root (int): MIDI pitch for the tonic root (default 60 = C4).
            voice_count (int): Number of sounding voices (voice_ins, default 3).
            harmony_range (Tuple[int, int]): Pitch bounds for harmony chords.
            bass_range (Tuple[int, int]): Pitch bounds for bass line.
            velocity (float): Base velocity for chord onsets (ha_vel_ins, default 64.0).
        """
        self.loop_size = max(1, int(loop_size))
        self.grain = max(1, int(grain))
        self.meter = meter
        self.key_root = int(key_root)
        self.voice_count = max(1, min(6, int(voice_count)))
        self.harmony_range = harmony_range
        self.bass_range = bass_range
        self._rng = random.Random(seed)

        # Reference parameters
        self.chord_change_probability = 1.0
        self.chord_complexity = float(chord_complexity)  # Cpx Prog (0.0..1.0)
        self.tension = float(tension)                     # Tension index (1..12)
        self.mode = self._normalize_mode(mode)
        self.harmony_add_probability = 0.0
        self.harmony_sub_probability = 0.0
        self.harmony_accent_probability = 0.0

        # Progression grammar engine
        self._progression_selector = HarmonicProgressionSelector(
            tonic_semitone=self.key_root % 12,
            complexity_progression=self.chord_complexity,
            mode=self.mode,
            seed=seed,
        )

        self._post_filter: Optional[List[int]] = None
        self._accent_beats = set()
        self._moved_list = set()
        self._arpeggio_step = 0
        self.harmony_move = 0.0
        self.velocity = float(velocity)
        self._normal_velocity_range = (58, 70)
        self._accent_velocity_range = (70, 80)
        self._update_velocity_ranges()
        self.midi_channel = 2
        self._last_measure_index: Optional[int] = None
        self._arpeggio_segment_enabled = False

        self._current_chord_def: ChordDefinition = self._progression_selector.get_current_chord()
        self._current_chord: List[int] = self._voice_chord(self._current_chord_def)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_current_chord(self, measure_index: int) -> List[int]:
        """
        Return the voiced MIDI notes for the active measure's chord.

        Args:
            measure_index (int): Current measure index within the loop.

        Returns:
            List[int]: Voiced MIDI note numbers.
        """
        if self._last_measure_index is None:
            self._last_measure_index = measure_index
        elif measure_index != self._last_measure_index:
            # Advance chord on measure boundary according to change probability
            if self._should_change_chord():
                self._current_chord_def = self._progression_selector.advance_progression()
                self._current_chord = self._voice_chord(self._current_chord_def)
                self._reset_arpeggiator()
            self._last_measure_index = measure_index

        return list(self._current_chord)

    def get_chord_pool(self) -> int:
        """
        Return the current chord pool identifier (1..4).
        Pool 1 is the sole gate for the Seeded Phrase Generator.
        """
        return int(self._current_chord_def.pool)

    def get_roman_numeral(self) -> str:
        """Return the mode-appropriate Roman numeral display label."""
        roman = self._current_chord_def.roman
        if self.mode != "minor":
            return roman
        return {
            "I": "i",
            "IV": "iv",
            "V": "v",
            "ii": "ii°",
            "iii": "III",
            "vi": "VI",
            "vii°": "VII",
        }.get(roman, roman)

    def get_chord_pitch_classes(self) -> List[int]:
        """
        Return the unlocked pitch classes (0..11) for the current chord
        according to the 12-level tension table (§4.2).
        """
        raw_tension = max(1, min(12, int(round(self.tension))))
        pitch_classes = query_pitch_class_set(
            self._current_chord_def.roman,
            raw_tension,
            tonic_semitone=self.key_root % 12,
            mode=self.mode,
        )
        if self._post_filter is not None:
            allowed = {p % 12 for p in self._post_filter}
            pitch_classes = [pc for pc in pitch_classes if pc in allowed]
        return pitch_classes

    def on_phrase_start(self) -> None:
        """Open the documented phrase-level arpeggiation segment."""
        self._arpeggio_segment_enabled = True

    def notify_accents(self, accent_beats: List[int]) -> None:
        """Receive melody accent beats to emphasize harmony onsets."""
        self._accent_beats = {int(beat) for beat in accent_beats}

    def notify_moved_list(self, moved_list: List[int]) -> None:
        """Receive Melody's moved onsets for shared accent-following."""
        self._moved_list = {int(index) for index in moved_list}

    def set_post_filter(self, pitch_subset: Optional[List[int]]) -> None:
        """Fast-cut post filter to rapidly restrict active pitches."""
        if pitch_subset is None:
            self._post_filter = None
        else:
            self._post_filter = [int(p) for p in pitch_subset]
        self._current_chord = self._voice_chord(self._current_chord_def)

    # ------------------------------------------------------------------
    # Voicing and 12-Level Tension Query
    # ------------------------------------------------------------------

    def _voice_chord(self, chord_def: ChordDefinition) -> List[int]:
        """
        Voicing mechanic taking the right-most N active pitch classes per §4.2,
        plus an independent Bass Selector note.
        """
        raw_tension = max(1, min(12, int(round(self.tension))))
        voiced_pcs = get_voiced_pitch_classes(
            chord_def,
            tension_level=raw_tension,
            voice_count=self.voice_count,
        )

        # Apply post filter if present
        if self._post_filter is not None:
            allowed = set(p % 12 for p in self._post_filter)
            filtered = [pc for pc in voiced_pcs if pc in allowed]
            voiced_pcs = filtered

        if self._post_filter is not None and not voiced_pcs:
            return []

        # 1. Place voiced harmony notes in the harmony register (MIDI 48..72)
        notes = []
        low_bound, high_bound = self.harmony_range
        for pc in voiced_pcs:
            # Find octave that places pc within [low_bound, high_bound]
            for oct_base in (48, 60, 72):
                candidate = oct_base + pc
                if low_bound <= candidate <= high_bound:
                    notes.append(candidate)
                    break
            else:
                notes.append(max(low_bound, min(high_bound, 60 + pc)))

        # 2. Bass Selector (§4.3): add root bass note in bass register (MIDI 36..48)
        bass_low, bass_high = self.bass_range
        root_pc = chord_def.root_semitone
        bass_note = 36 + root_pc
        if bass_note < bass_low:
            bass_note += 12
        elif bass_note > bass_high:
            bass_note -= 12
        notes.insert(0, bass_note)

        return sorted(set(notes))

    # ------------------------------------------------------------------
    # Tick Processing & Event Generation
    # ------------------------------------------------------------------

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
        active_chord = self._current_chord
        if not active_chord:
            return events

        is_chord_beat, is_accent_beat = self._accent_beat_follower(beat)

        # Rhythm & Articulation classification (§3.1, §3.2)
        if subdivision == 0:
            if is_chord_beat and self._rng.random() >= self.harmony_sub_probability:
                duration, articulation = self._select_duration(
                    pulse_duration, subdivision, onset_index=index
                )
                events.extend(
                    self._build_chord_events(
                        active_chord,
                        duration,
                        is_accent=is_accent_beat,
                        articulation=articulation,
                    )
                )
            elif (not is_chord_beat) and self._rng.random() < self.harmony_add_probability:
                duration, articulation = self._select_duration(
                    pulse_duration, subdivision, onset_index=index
                )
                events.extend(
                    self._build_chord_events(
                        active_chord,
                        duration,
                        articulation=articulation,
                    )
                )
        else:
            # Intermediate tension plays broken arpeggio; extreme tension plays block chords
            if self._should_arpeggiate():
                arp_event = self._build_arpeggio_event(pulse_duration)
                if arp_event:
                    events.append(arp_event)
            elif self._rng.random() < self._add_fill_prob():
                duration, articulation = self._select_duration(
                    pulse_duration, subdivision, onset_index=index
                )
                events.extend(
                    self._build_chord_events(
                        active_chord,
                        duration,
                        articulation=articulation,
                    )
                )

        return events

    # ------------------------------------------------------------------
    # Event Builders & Arpeggiator
    # ------------------------------------------------------------------

    def _select_duration(
        self,
        pulse_duration: float,
        subdivision: int,
        onset_index: Optional[int] = None,
    ) -> Tuple[float, str]:
        """
        Compute note duration and articulation classification based on inter-onset distance (§3.2, §4 3.1.3).
        STACCATO if gap to next onset <= threshold else LEGATO.
        """
        base = pulse_duration * (
            self.grain if subdivision == 0 else max(1, self.grain // 2)
        )
        threshold = max(1, self.grain // 2)

        if onset_index is not None:
            template_key = self.meter or f"{self.loop_size}/4"
            template = HARMONY_TEMPLATE.get(template_key, HARMONY_TEMPLATE.get("4/4", {}))
            chord_beats = template.get("CHORD", [0, max(0, self.loop_size // 2)])
            future_onsets = [b * self.grain for b in chord_beats if b * self.grain > onset_index]
            if self.harmony_move > 0:
                future_onsets.extend(index for index in self._moved_list if index > onset_index)
            if future_onsets:
                gap = future_onsets[0] - onset_index
            else:
                gap = (self.loop_size * self.grain) - onset_index + (chord_beats[0] * self.grain if chord_beats else 0)
        else:
            gap = self.grain

        if gap <= threshold:
            articulation = "staccato"
            duration = base * 0.5
        else:
            articulation = "legato"
            duration = base * 1.05

        return max(pulse_duration * 0.2, duration), articulation

    def _should_arpeggiate(self) -> bool:
        """
        Chord Builder vs. Arpeggiator selection rule (§4.3):
        Low tension (levels 1-3) voices sustained block chords (sanctuary/calm);
        intermediate tension (levels 4-10) voices flowing broken arpeggios;
        extreme tension (levels 11-12) switches back to full block chords.
        """
        tension_val = float(self.tension)
        return self._arpeggio_segment_enabled and 3.0 < tension_val <= 10.5

    def _build_arpeggio_event(self, pulse_duration: float) -> Optional[dict]:
        """Voice a single broken arpeggio note across active chord tones."""
        # Use upper chord tones (exclude bass note) for the arpeggiated figure
        upper_notes = [n for n in self._current_chord if n > self.bass_range[1]]
        if not upper_notes:
            upper_notes = self._current_chord
        if not upper_notes:
            return None

        note = upper_notes[self._arpeggio_step % len(upper_notes)]
        self._arpeggio_step += 1
        velocity = self._rng.randint(*self._normal_velocity_range)

        return {
            "note": note,
            "velocity": velocity,
            "duration": max(pulse_duration * 0.5, pulse_duration * 1.05),
            "articulation": "legato",
            "channel": self.midi_channel,
            "source": "harmony",
            "is_arpeggio": True,
            # OA uses this only for the documented 1/32 solo-Piano rule.
            "arpeggio_rate_denominator": 4 * self.grain,
        }

    def _build_chord_events(
        self,
        notes: List[int],
        duration: float,
        is_accent: bool = False,
        articulation: str = "legato",
    ) -> List[dict]:
        """Emit block chord notes across active sounding pitches."""
        vel_range = self._accent_velocity_range if is_accent else self._normal_velocity_range
        events = []
        for note in notes:
            velocity = self._rng.randint(*vel_range)
            events.append({
                "note": note,
                "velocity": velocity,
                "duration": duration,
                "articulation": articulation,
                "channel": self.midi_channel,
                "source": "harmony",
            })
        return events

    def _reset_arpeggiator(self) -> None:
        self._arpeggio_step = 0

    def _update_velocity_ranges(self) -> None:
        """Derive normal and accent velocity ranges from base velocity (§3.2, §4.4, §4.5)."""
        base = int(round(self.velocity))
        self._normal_velocity_range = (max(1, base - 6), min(127, base + 6))
        self._accent_velocity_range = (max(1, base + 6), min(127, base + 16))

    def _accent_beat_follower(self, beat: int) -> Tuple[bool, bool]:
        template_key = self.meter or f"{self.loop_size}/4"
        template = HARMONY_TEMPLATE.get(template_key, HARMONY_TEMPLATE.get("4/4", {}))
        chord_beats = template.get("CHORD", [0, max(0, self.loop_size // 2)])
        accent_beats = template.get("ACCENT", [0])

        is_chord_beat = beat in chord_beats
        is_accent_beat = beat in accent_beats or beat in self._accent_beats
        return is_chord_beat, is_accent_beat

    def _should_change_chord(self) -> bool:
        if self.chord_change_probability >= 1.0:
            return True
        if self.chord_change_probability <= 0.0:
            return False
        return self._rng.random() < self.chord_change_probability

    def _add_fill_prob(self) -> float:
        return self.harmony_add_probability * 0.5

    # ------------------------------------------------------------------
    # Parameter Updates
    # ------------------------------------------------------------------

    def update_params(self, **kwargs) -> bool:
        """Apply parameter updates for harmony behavior."""
        changed = False

        if "mode" in kwargs or "ha_mode" in kwargs:
            new_mode = self._normalize_mode(kwargs.get("ha_mode", kwargs.get("mode")))
            if new_mode != self.mode:
                self.mode = new_mode
                self._progression_selector.set_mode(new_mode)
                self._current_chord_def = self._progression_selector.get_current_chord()
                self._current_chord = self._voice_chord(self._current_chord_def)
                changed = True

        if "seed_state" in kwargs and kwargs["seed_state"] is not None:
            ss = kwargs["seed_state"]
            seed_val = int(ss.current_seed)
            self._rng.seed(seed_val)
            self._progression_selector.rng.seed(seed_val)
            changed = True
        elif "seed" in kwargs and kwargs["seed"] is not None:
            seed_val = int(kwargs["seed"])
            self._rng.seed(seed_val)
            self._progression_selector.rng.seed(seed_val)
            changed = True

        if "chord_change_probability" in kwargs:
            new_val = float(kwargs["chord_change_probability"])
            if new_val != self.chord_change_probability:
                self.chord_change_probability = new_val
                changed = True

        chord_cpx = kwargs.get("chord_complexity", kwargs.get("complexity_progression"))
        if chord_cpx is not None:
            new_val = float(chord_cpx)
            if new_val != self.chord_complexity:
                self.chord_complexity = new_val
                self._progression_selector.set_complexity(new_val)
                changed = True

        if "tension" in kwargs:
            new_val = float(kwargs["tension"])
            if new_val != self.tension:
                self.tension = new_val
                self._current_chord = self._voice_chord(self._current_chord_def)
                changed = True

        if "voice_count" in kwargs:
            new_val = max(1, min(6, int(kwargs["voice_count"])))
            if new_val != self.voice_count:
                self.voice_count = new_val
                self._current_chord = self._voice_chord(self._current_chord_def)
                changed = True

        add_prob = kwargs.get("harmony_add_probability", kwargs.get("add_probability"))
        if add_prob is not None:
            new_val = max(0.0, min(1.0, float(add_prob)))
            if new_val != self.harmony_add_probability:
                self.harmony_add_probability = new_val
                changed = True

        sub_prob = kwargs.get("harmony_sub_probability", kwargs.get("sub_probability"))
        if sub_prob is not None:
            new_val = max(0.0, min(1.0, float(sub_prob)))
            if new_val != self.harmony_sub_probability:
                self.harmony_sub_probability = new_val
                changed = True

        acc_prob = kwargs.get("harmony_accent_probability", kwargs.get("accent_probability"))
        if acc_prob is not None:
            new_val = max(0.0, min(1.0, float(acc_prob)))
            if new_val != self.harmony_accent_probability:
                self.harmony_accent_probability = new_val
                changed = True

        if "move" in kwargs or "ha_move" in kwargs:
            new_val = max(0.0, min(1.0, float(kwargs.get("ha_move", kwargs.get("move")))))
            if new_val != self.harmony_move:
                self.harmony_move = new_val
                changed = True

        if "key_root" in kwargs:
            new_val = int(kwargs["key_root"])
            if new_val != self.key_root:
                self.key_root = new_val
                self._progression_selector.set_tonic(new_val % 12)
                self._current_chord_def = self._progression_selector.get_current_chord()
                self._current_chord = self._voice_chord(self._current_chord_def)
                changed = True

        if "loop_size" in kwargs:
            new_loop = max(1, int(kwargs["loop_size"]))
            if new_loop != self.loop_size:
                self.loop_size = new_loop
                changed = True

        if "grain" in kwargs:
            new_grain = max(1, int(kwargs["grain"]))
            if new_grain != self.grain:
                self.grain = new_grain
                changed = True

        if "meter" in kwargs and kwargs["meter"] != self.meter:
            self.meter = kwargs["meter"]
            changed = True

        vel = kwargs.get("ha_vel_ins", kwargs.get("velocity"))
        if vel is not None:
            new_val = max(1.0, min(127.0, float(vel)))
            if new_val != self.velocity:
                self.velocity = new_val
                self._update_velocity_ranges()
                changed = True

        return changed

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode).strip().lower()
        if normalized not in {"major", "minor"}:
            raise ValueError("Harmony mode must be 'major' or 'minor'")
        return normalized
