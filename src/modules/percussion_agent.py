"""Percussion agent for groove and fill generation."""

import random
from typing import List, Optional


# ---------------------------------------------------------------------------
# Percussion agent
# ---------------------------------------------------------------------------

from src.core.configs import PERCUSSION_TEMPLATE

class PercussionAgent:
    """
    Generate percussion patterns for the groove layer.

    The agent builds base drum patterns per beat, adds stochastic fills, and
    supports phrase-aware variations triggered by chord changes.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        loop_size: int,
        grain: int,
        meter: Optional[str] = None,
        seed: Optional[int] = 0,
        phrase_length: int = 4,
    ):
        """
        Initialize the percussion agent and pattern state.

        Args:
            loop_size (int): Number of beats per loop.
            grain (int): Subdivision factor per beat.
            meter (Optional[str]): Optional time signature key (e.g. "4/4").
            seed (Optional[int]): RNG seed for reproducibility.
            phrase_length (int): Number of loops per phrase.
        """
        # Loop and grain information (time signature and subdivision) to inform rhythmic decisions
        self.loop_size = loop_size
        self.grain = grain
        self.total_pulses = loop_size * grain
        self.meter = meter
        self.rng = random.Random(seed)

        self.midi_channel = 9  # Standard MIDI channel for percussion

        # Standard General MIDI Drum Map Values (Kick, Snare, Toms, Cymbals - baseline §2.1)
        # Program 48: General MIDI Orchestra Kit
        self.KICK = 36          # Concert Bass Drum (Gran Cassa)
        self.SNARE = 38         # Concert Snare
        self.SNARE_ROLL = 40    # Concert Snare Roll
        self.SIDE_STICK = 37    # Side Stick / Rimshot
        self.TOM_LOW = 45       # Timpani A
        self.TOM_MID = 48       # Timpani c
        self.TOM_HIGH = 50      # Timpani d
        self.CYMBAL = 49        # Crash Cymbal 1 (orchestral cymbal row)
        self.CRASH = 57         # Concert Cymbal 2

        # Baseline parameters (§5.4)
        self.pa_vel_perc = 90.0
        self.pa_acc_beat_p = 0.5
        self.pa_ks_plus_minus = 0.0
        self.pa_toms_plus_minus = 0.0
        self.pa_cymb_plus_minus = 0.0

        # Algorithmic prob/variation attributes
        self.kick_add_prob = 0.0
        self.kick_sub_prob = 0.0
        self.ghost_kick_prob = 0.05
        self.snare_add_prob = 0.0
        self.snare_sub_prob = 0.0
        self.kick_ratchet_prob = 0.0
        self.snare_ratchet_prob = 0.0

        self.cymb_prob_start = 0.10
        self.cymb_on_fill_prob = 0.75
        
        # Templates for tom fills
        self.tom_templates = {
            "basic_fill": [self.TOM_LOW, self.TOM_MID, self.TOM_HIGH],
            "reverse_fill": [self.TOM_HIGH, self.TOM_MID, self.TOM_LOW],
            "random_fill": self._random_tom_template,
        }
        self.tom_fill_prob = 0.35
        self.tom_fill_window = max(1, grain // 2)
        self.tom_leadin_prob = 0.25
        self.tom_roll_prob = 0.15
        self.phrase_length = max(1, phrase_length)
        self.phrase_fill_prob = 0.65
        self._loop_index = 0
        self._phrase_start = True
        self._phrase_end = False
        self._pending_phrase_fill = False
        self._last_chord_pool: Optional[int] = None
        self._accent_beats = set()
        self._moved_list = set()

        self.accent_velocity_range = (100, 127)
        self.normal_velocity_range = (60, 95)
        self.ghost_velocity_range = (35, 60)
        self.tom_fill_velocity_range = (60, 100)
        self.tom_leadin_velocity_range = (45, 70)

        # Precompute sub-fill events for the entire loop
        self.subfills = {}
        self.add_sub_filling()

    # ------------------------------------------------------------------
    # Loop/phrase lifecycle
    # ------------------------------------------------------------------

    def on_loop_start(self, loop_index: int) -> None:
        """
        Update loop counters and regenerate sub-fill plans.

        Args:
            loop_index (int): Index of the current loop.
        """
        self._loop_index = max(0, int(loop_index))
        if self.phrase_length <= 1:
            self._phrase_end = True
            self._phrase_start = True
        else:
            self._phrase_end = (self._loop_index % self.phrase_length) == (self.phrase_length - 1)
            self._phrase_start = (self._loop_index % self.phrase_length) == 0
        self.add_sub_filling()

    # ------------------------------------------------------------------
    # Template and fill selection
    # ------------------------------------------------------------------

    def _get_template_key(self) -> str:
        if self.meter:
            return self.meter
        default_key = f"{self.loop_size}/4"
        if default_key in PERCUSSION_TEMPLATE:
            return default_key
        if self.loop_size == 6 and "6/8" in PERCUSSION_TEMPLATE:
            return "6/8"
        return default_key

    def _random_tom_template(self) -> list:
        return self.rng.choices([self.TOM_LOW, self.TOM_MID, self.TOM_HIGH], k=3)

    def _select_tom_template(self) -> list:
        template_name = self.rng.choice(list(self.tom_templates.keys()))
        template = self.tom_templates[template_name]
        if callable(template):
            return list(template())
        return list(template)

    def _build_tom_fill_plan(self) -> dict:
        # Gate fills by pa_toms_plus_minus (§5.3 / §5.4)
        if self.pa_toms_plus_minus <= 0:
            return {}

        base_prob = max(0.0, min(1.0, self.tom_fill_prob * max(0.0, self.pa_toms_plus_minus)))
        if self._phrase_end:
            base_prob = max(base_prob, max(0.0, min(1.0, self.phrase_fill_prob * max(0.0, self.pa_toms_plus_minus))))
        if self._pending_phrase_fill:
            base_prob = max(base_prob, max(0.0, min(1.0, self.phrase_fill_prob * max(0.0, self.pa_toms_plus_minus))))
            self._pending_phrase_fill = False
        if base_prob <= 0 or self.rng.random() >= base_prob:
            return {}

        fill_window = max(1, min(self.tom_fill_window, self.grain))
        last_beat_start = (self.loop_size - 1) * self.grain
        window_start = self.grain - fill_window

        template_notes = self._select_tom_template()
        if not template_notes:
            return {}
        if len(template_notes) > fill_window:
            template_notes = template_notes[-fill_window:]

        if len(template_notes) == 1:
            positions = [window_start + fill_window - 1]
        else:
            positions = [
                window_start + int(round(i * (fill_window - 1) / (len(template_notes) - 1)))
                for i in range(len(template_notes))
            ]

        events_by_index = {}
        for note, sub in zip(template_notes, positions):
            idx = last_beat_start + sub
            events_by_index.setdefault(idx, []).append(
                self._build_midi(note, is_accent=False, velocity_range=self.tom_fill_velocity_range)
            )

        fill_start_idx = last_beat_start + min(positions)
        if window_start > 0 and self.rng.random() < self.tom_leadin_prob:
            lead_idx = last_beat_start + window_start - 1
            lead_note = self.rng.choice([self.TOM_LOW, self.TOM_MID, self.TOM_HIGH])
            events_by_index.setdefault(lead_idx, []).append(
                self._build_midi(lead_note, is_accent=False, velocity_range=self.tom_leadin_velocity_range)
            )

        cymb_fill_prob = self.cymb_on_fill_prob * max(0.0, self.pa_cymb_plus_minus) if self.pa_cymb_plus_minus > 0 else 0.0
        if events_by_index and self.rng.random() < cymb_fill_prob:
            cymb_note = self.CRASH if self.pa_cymb_plus_minus > 0.5 else self.CYMBAL
            events_by_index.setdefault(fill_start_idx, []).append(self._build_midi(cymb_note, is_accent=False))

        if events_by_index:
            roll_prob = max(0.40, min(0.90, self.tom_roll_prob + max(0.0, self.pa_toms_plus_minus) * 0.5))
            if self.rng.random() < roll_prob:
                roll_count = 6 if self.grain >= 3 else 4
                for event in events_by_index.get(last_beat_start + max(positions), []):
                    if event.get("note") in (self.TOM_LOW, self.TOM_MID, self.TOM_HIGH):
                        event["is_ratchet"] = True
                        event["ratchet_count"] = roll_count
                        event["duration"] = 0.45

        return events_by_index

    def _accent_beat_follower(self, beat: int, subdivision: int) -> tuple:
        # Dynamic beat templates based on current loop size and grain (time signature and subdivision)
        percussion_template = PERCUSSION_TEMPLATE.get(self._get_template_key(), {})

        if not percussion_template:
            fallback_kick = [0]
            fallback_snare = [self.loop_size // 2] if self.loop_size >= 2 else []
            percussion_template = {
                "KICK": fallback_kick,
                "SNARE": fallback_snare,
                "TOM": [],
                "CYMBAL": [0] if self.loop_size > 0 else [],
            }

        kick_beats = percussion_template.get("KICK", [])
        snare_beats = percussion_template.get("SNARE", [])
        tom_beats = percussion_template.get("TOM", [])
        cymbal_beats = percussion_template.get("CYMBAL", [])

        # 4 Baseline rows: Kick, Snare, Toms, Cymbals (§2.1)
        is_kick_beat = (subdivision == 0 and beat in kick_beats)
        is_snare_beat = (subdivision == 0 and beat in snare_beats)
        is_tom_beat = (subdivision == 0 and beat in tom_beats)
        is_cymbal_beat = (subdivision == 0 and beat in cymbal_beats)

        return is_kick_beat, is_snare_beat, is_tom_beat, is_cymbal_beat

    # ------------------------------------------------------------------
    # Accent and chord notifications
    # ------------------------------------------------------------------

    def notify_accents(self, accent_beats: List[int]) -> None:
        """Receive accent beats from the melody agent.

        Args:
            accent_beats (List[int]): Beat indices marked as accents.
        """
        self._accent_beats = {int(beat) for beat in accent_beats}

    def notify_moved_list(self, moved_list: List[int]) -> None:
        """Receive Melody's moved onsets for shared PA accent emphasis."""
        self._moved_list = {int(index) for index in moved_list}

    def notify_chord_change(self, chord_pool: int) -> None:
        """Record chord pool changes to align phrase fills.

        Args:
            chord_pool (int): Current harmony chord pool identifier.
        """
        pool_val = int(chord_pool)
        if pool_val == 1 and self._last_chord_pool is not None and self._last_chord_pool != 1:
            self._pending_phrase_fill = True
        self._last_chord_pool = pool_val
    
    def _add_sub_filling(
        self,
        beat: int,
        subdivision: int,
        scheduled_snares: Optional[set] = None,
    ) -> list:
        """
        Adds sub-fill events based on the current beat and subdivision.
        This includes ghost notes and anticipatory hits.

        Args:
            beat (int): The current beat number in the loop.
            subdivision (int): The current subdivision within the beat.
            scheduled_snares (Optional[set]): Set of tick indices with planned snares.

        Returns:
            list: A list of MIDI events to be added as sub-fills.
        """
        events = []

        # Anticipatory ghost/snare just before a scheduled snare beat
        lookback = max(1, self.grain // 4)
        next_beat_downbeat = (beat + 1) * self.grain
        if scheduled_snares is not None:
            has_upcoming_snare = (
                next_beat_downbeat in scheduled_snares
                or (beat == self.loop_size - 1 and 0 in scheduled_snares)
            )
        else:
            has_upcoming_snare = (beat % 2 == 1)

        if has_upcoming_snare and subdivision >= (self.grain - lookback) and self.rng.random() < 0.25:
            ghost_note = self.SIDE_STICK if self.pa_vel_perc < 60.0 else self.SNARE
            events.append(self._build_midi(ghost_note, is_accent=False, velocity_range=self.ghost_velocity_range))

        return events

    def _build_midi(
        self,
        note: int,
        is_accent: bool,
        is_ratchet: bool = False,
        ratchet_count: int = 3,
        velocity_range: Optional[tuple] = None,
    ):
        if velocity_range is None:
            velocity_range = self.accent_velocity_range if is_accent else self.normal_velocity_range
        velocity = self.rng.randint(velocity_range[0], velocity_range[1])
        return {
            "note": note,
            "velocity": velocity,
            "is_ratchet": is_ratchet,
            "ratchet_count": ratchet_count,
            "duration": None,
            "channel": self.midi_channel,
        }

    # ------------------------------------------------------------------
    # Event generation
    # ------------------------------------------------------------------

    def process_tick(self, index: int) -> list:
        """Generate percussion events for a single clock tick.

        Args:
            index (int): Current tick index in the loop.

        Returns:
            list: Raw percussion event dictionaries.
        """
        return list(self.subfills.get(index, []))

    # ------------------------------------------------------------------
    # Precomputed onset grid and fills
    # ------------------------------------------------------------------

    def _update_velocity_ranges(self) -> None:
        """Refresh velocity ranges without changing the planned rhythm grid."""
        base_vel = int(round(self.pa_vel_perc))
        self.normal_velocity_range = (max(1, base_vel - 15), min(127, base_vel + 10))
        self.accent_velocity_range = (max(1, base_vel), min(127, base_vel + 20))
        self.ghost_velocity_range = (
            max(1, int(round(base_vel * 0.55))),
            max(1, int(round(base_vel * 0.75))),
        )
        self.tom_fill_velocity_range = (
            max(1, int(round(base_vel * 0.75))),
            min(127, int(round(base_vel * 1.15))),
        )
        self.tom_leadin_velocity_range = (
            max(1, int(round(base_vel * 0.60))),
            min(127, int(round(base_vel * 0.90))),
        )

    def _shift_planned_velocities(self, delta: float) -> None:
        """Apply a velocity-only change without rebuilding fills or rolls."""
        for events in self.subfills.values():
            for event in events:
                event["velocity"] = max(1, min(127, int(round(event["velocity"] + delta))))

    def _plan_loop(self) -> dict:
        """
        Precompute the complete onset grid and fill events for the loop.
        Aligned with technical-reference.md §2.1 and §5.1 (Kick, Snare, Toms, Cymbals).
        """
        total_ticks = self.loop_size * self.grain
        planned_events = {idx: [] for idx in range(total_ticks)}

        self._update_velocity_ranges()

        # 1. Base groove generation across the Count Loop index grid
        scheduled_snares = set()
        for idx in range(total_ticks):
            beat = idx // self.grain
            subdivision = idx % self.grain
            is_kick_beat, is_snare_beat, is_tom_beat, is_cymbal_beat = (
                self._accent_beat_follower(beat, subdivision)
            )
            # Accent/Beat Follower (§4.1.1, §5.4 pa_acc_beat_p)
            accent_here = (subdivision == 0) and (
                beat in self._accent_beats or self.rng.random() < self.pa_acc_beat_p
            )

        ks_delta = self.pa_ks_plus_minus
        tom_delta = self.pa_toms_plus_minus
        cymb_delta = self.pa_cymb_plus_minus

        # Layering gating per Technical Reference §5.3:
        # Layering is simply however many of the four onset rows (Kick, Snare, Toms, Cymbals) are active.
        toms_active = tom_delta > -0.7
        cymbals_active = cymb_delta > -0.7
        snare_active = ks_delta > -0.7
        kick_active = ks_delta > -0.95
        snare_note = self.SIDE_STICK if (self.pa_vel_perc < 60.0 or ks_delta < 0) else self.SNARE

        scheduled_snares = set()
        for idx in range(total_ticks):
            beat = idx // self.grain
            subdivision = idx % self.grain
            is_kick_beat, is_snare_beat, is_tom_beat, is_cymbal_beat = (
                self._accent_beat_follower(beat, subdivision)
            )
            # Accent/Beat Follower (§4.1.1, §5.4 pa_acc_beat_p)
            moved_here = idx in self._moved_list
            accent_here = moved_here or (
                subdivision == 0
                and (beat in self._accent_beats or self.rng.random() < self.pa_acc_beat_p)
            )

            # Row 1: Kick
            if kick_active:
                if is_kick_beat:
                    if ks_delta < 0 and beat != 0:
                        # Negative ks_delta reduces kick to downbeat anchor pulse (beat 0)
                        pass
                    elif ks_delta < -0.3 and not (self._phrase_start or (self._loop_index % 2 == 0)):
                        # In deep ambient/subdued states, pulse every 2 measures or on phrase start
                        pass
                    else:
                        kick_sub = max(0.0, -ks_delta * 0.5) if (ks_delta < 0 and beat == 0) else 0.0
                        if self.rng.random() >= kick_sub:
                            is_ratchet = self.rng.random() < self.kick_ratchet_prob
                            planned_events[idx].append(
                                self._build_midi(
                                    self.KICK,
                                    is_accent=(accent_here or beat == 0),
                                    is_ratchet=is_ratchet,
                                )
                            )

            # Row 2: Snare
            if snare_active:
                if is_snare_beat:
                    if ks_delta < 0 and not self._phrase_end:
                        # In calm/negative-delta states, suppress mid-phrase pop backbeats;
                        # only punctuate cadences at phrase ends
                        pass
                    else:
                        snare_sub = max(0.0, -ks_delta) if ks_delta < 0 else 0.0
                        if self.rng.random() >= snare_sub:
                            is_phrase_roll = self._phrase_end and ks_delta > 0.2 and self.pa_vel_perc >= 60.0 and self.rng.random() < 0.60
                            is_ratchet = is_phrase_roll or (self.rng.random() < self.snare_ratchet_prob)
                            chosen_note = self.SNARE_ROLL if (is_phrase_roll and self.rng.random() < 0.40) else snare_note
                            ev = self._build_midi(
                                chosen_note,
                                is_accent=accent_here,
                                is_ratchet=is_ratchet,
                                ratchet_count=6 if is_phrase_roll else 4,
                            )
                            if is_phrase_roll:
                                ev["duration"] = 0.45
                            planned_events[idx].append(ev)
                            scheduled_snares.add(idx)

            # Row 3: Toms (+/- Toms control §5.4)
            if toms_active:
                if is_tom_beat:
                    if tom_delta < 0 and not self._phrase_end:
                        # In calm/negative-delta states, suppress routine beat 3 tom hits;
                        # only prepare phrase boundaries
                        pass
                    else:
                        tom_sub = max(0.0, -tom_delta * 0.7) if tom_delta < 0 else 0.0
                        if self.rng.random() >= tom_sub:
                            planned_events[idx].append(
                                self._build_midi(
                                    self.rng.choice([self.TOM_LOW, self.TOM_MID, self.TOM_HIGH]),
                                    is_accent=True,
                                )
                            )
                elif subdivision != 0 and tom_delta > 0 and self.rng.random() < tom_delta * 0.4:
                    planned_events[idx].append(
                        self._build_midi(
                            self.rng.choice([self.TOM_LOW, self.TOM_MID, self.TOM_HIGH]),
                            is_accent=accent_here,
                        )
                    )

            # Row 4: Cymbals (+/- Cymb control §5.4)
            if cymbals_active:
                if is_cymbal_beat or (beat == 0 and subdivision == 0 and self.rng.random() < self.cymb_prob_start):
                    if cymb_delta < 0 and not self._phrase_start:
                        # In calm/negative-delta states, restrict cymbal color strictly to phrase entrances
                        pass
                    else:
                        cymb_sub = max(0.0, -cymb_delta * 0.7) if cymb_delta < 0 else 0.0
                        if self.rng.random() >= cymb_sub:
                            planned_events[idx].append(
                                self._build_midi(self.CYMBAL, is_accent=accent_here)
                            )
                elif subdivision != 0 and cymb_delta > 0 and self.rng.random() < cymb_delta * 0.3:
                    planned_events[idx].append(
                        self._build_midi(self.CYMBAL, is_accent=False)
                    )

        # 2. Add anticipatory ghost notes and fill plans
        if snare_active and ks_delta >= 0 and self.pa_vel_perc >= 60.0:
            for idx in range(total_ticks):
                beat = idx // self.grain
                subdivision = idx % self.grain
                sub_events = self._add_sub_filling(beat, subdivision, scheduled_snares=scheduled_snares)
                planned_events[idx].extend(sub_events)

        if toms_active:
            tom_fill_plan = self._build_tom_fill_plan()
            for idx in range(total_ticks):
                planned_events[idx].extend(tom_fill_plan.get(idx, []))

        self.subfills = planned_events
        return planned_events

    def add_sub_filling(self) -> dict:
        """
        Precompute onset grid and sub-fill events for the entire loop.
        Returns a dict mapping absolute tick index -> list of events.
        """
        return self._plan_loop()

    def get_lookahead(self, current_index: int, lookahead_steps: int) -> List[bool]:
        """
        Return a boolean list indicating planned percussion onsets for the upcoming ticks.
        """
        results = []
        for step in range(lookahead_steps):
            tick = (current_index + step) % self.total_pulses
            has_hit = bool(self.subfills.get(tick))
            results.append(has_hit)
        return results

    # ------------------------------------------------------------------
    # Parameter updates
    # ------------------------------------------------------------------

    def update_params(self, **kwargs) -> bool:
        """Apply parameter updates for percussion behavior.

        Supported keys include probability fields (kick, snare, hats, fills),
        meter, seed, and integer density settings.

        Returns:
            bool: True if any parameter changed.
        """
        changed = False
        rebuild_pattern = False
        previous_velocity = self.pa_vel_perc

        def clamp_prob(value: float) -> float:
            return max(0.0, min(1.0, float(value)))

        def clamp_int(value: int, minimum: int = 1) -> int:
            return max(minimum, int(value))

        baseline_float_fields = {
            "pa_vel_perc",
            "pa_acc_beat_p",
            "pa_ks_plus_minus",
            "pa_toms_plus_minus",
            "pa_cymb_plus_minus",
        }

        prob_fields = {
            "kick_add_prob",
            "kick_sub_prob",
            "ghost_kick_prob",
            "kick_ratchet_prob",
            "snare_add_prob",
            "snare_sub_prob",
            "snare_ratchet_prob",
            "cymb_prob_start",
            "cymb_on_fill_prob",
            "tom_fill_prob",
            "tom_leadin_prob",
            "tom_roll_prob",
            "phrase_fill_prob",
        }

        int_fields = {
            "tom_fill_window",
            "phrase_length",
        }

        for key, value in kwargs.items():
            if key == "seed_state" and value is not None:
                self.rng.seed(int(value.rhythm_seed))
                changed = True
                rebuild_pattern = True
                continue
            if key == "rhythm_seed" and value is not None:
                self.rng.seed(int(value))
                changed = True
                rebuild_pattern = True
                continue
            if key == "seed" and value is not None:
                self.rng.seed(int(value))
                changed = True
                rebuild_pattern = True
                continue
            if key == "meter":
                self.meter = value
                changed = True
                rebuild_pattern = True
                continue
            if key == "loop_size" and value is not None:
                new_loop = max(1, int(value))
                if new_loop != self.loop_size:
                    self.loop_size = new_loop
                    changed = True
                    rebuild_pattern = True
                continue
            if key == "grain" and value is not None:
                new_grain = max(1, int(value))
                if new_grain != self.grain:
                    self.grain = new_grain
                    changed = True
                    rebuild_pattern = True
                continue

            if key in baseline_float_fields:
                new_value = float(value)
            elif key in prob_fields:
                new_value = clamp_prob(value)
            elif key in int_fields:
                new_value = clamp_int(value)
            else:
                continue

            if getattr(self, key, None) != new_value:
                setattr(self, key, new_value)
                changed = True
                if key != "pa_vel_perc":
                    rebuild_pattern = True

        if changed:
            self.total_pulses = self.loop_size * self.grain
            self.phrase_length = max(1, int(self.phrase_length))
            self._update_velocity_ranges()
            if rebuild_pattern:
                self.add_sub_filling()
            elif self.pa_vel_perc != previous_velocity:
                self._shift_planned_velocities(self.pa_vel_perc - previous_velocity)

        return changed

    # ------------------------------------------------------------------
    # Debug utilities
    # ------------------------------------------------------------------

    def display_grid(self, events: list):
        """
        Utility function to visualize the generated pattern in a grid format.

        Arguments:
            events (list): List of MIDI events for a loop. Each event should
                include a `note` and optional `index` field.
        """
        grid = [[" " for _ in range(self.total_pulses)] for _ in range(4)]  # 4 rows: KICK, SNARE, TOM, CYMBAL (§2.1)
        for event in events:
            note = event["note"]
            idx = event.get("index", 0)
            if note == self.KICK:
                grid[0][idx] = "K"
            elif note == self.SNARE:
                grid[1][idx] = "S"
            elif note in [self.TOM_LOW, self.TOM_MID, self.TOM_HIGH]:
                grid[2][idx] = "T"
            elif note == self.CYMBAL:
                grid[3][idx] = "C"

        print("KICK:   " + "".join(grid[0]))
        print("SNARE:  " + "".join(grid[1]))
        print("TOM:    " + "".join(grid[2]))
        print("CYMBAL: " + "".join(grid[3]))
