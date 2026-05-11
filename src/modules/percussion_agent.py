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

        # Standard General MIDI Drum Map Values
        self.KICK = 36
        self.SNARE = 38
        self.HIHAT_CLOSED = 42
        self.HIHAT_OPEN = 46
        self.TOM_LOW = 45
        self.TOM_MID = 48
        self.TOM_HIGH = 50
        self.CYMBAL = 49
        self.RIDE = 51
        self.RIDE_BELL = 53
        self.CRASH = 49

        # Probabilities for adding variation to the groove
        self.kick_add_prob = 0.10  # Chance to add a syncopated kick
        self.kick_sub_prob = 0.15  # Chance to drop a main kick
        self.ghost_kick_prob = 0.08  # Chance to add a non-accented "ghost" kick on off-beats

        self.snare_add_prob = 0.05  # Chance to add a ghost snare
        self.snare_sub_prob = 0.0   # Chance to drop the snare (keep backbeat steady)

        self.hat_closed_prob = 0.90  # Chance to play closed hi-hat (vs open)
        self.hat_open_prob = 0.10    # Chance to play open hi-hat
        self.hat_density = max(1, grain // 2)  # Default hi-hat density (e.g. eighth notes)
        self.hat_ratchet_prob = 0.03  # Chance to add a hi-hat ratchet

        self.kick_ratchet_prob = 0.0
        self.snare_ratchet_prob = 0.0

        self.crash_prob_start = 0.12  # Chance to start a crash cymbal on the first beat of the loop
        self.crash_on_fill_prob = 0.85    # Chance to add a crash at the start of a tom fill

        self.ride_prob = 0.18 # Per-bar chance to enable a ride-pattern replacement for hi-hats
        self.ride_density = max(1, grain // 2)  # How dense the ride pattern is (e.g. every 2 subdivisions for eighth notes)
        self.ride_bell_prob = 0.06 # Chance to hit the bell of the ride cymbal instead of the bow for added variation
        self._ride_mode = False
        
        # Templates for tom fills that can be triggered on the last beat of the loop, with some randomness for variation
        self.tom_templates = {
            "basic_fill": [self.TOM_LOW, self.TOM_MID, self.TOM_HIGH],
            "reverse_fill": [self.TOM_HIGH, self.TOM_MID, self.TOM_LOW],
            "random_fill": self._random_tom_template,
        }
        self.tom_fill_prob = 0.35  # Chance to add a tom fill on the last beat of the loop
        self.tom_fill_window = max(1, grain // 2)  # How many subdivisions before the end of the loop to start adding tom fills
        self.tom_leadin_prob = 0.25  # Chance to add a lead-in hit before the main fill on the last beat of the loop
        self.tom_roll_prob = 0.15  # Chance to turn a tom fill into a rapid roll (e.g. 6 hits instead of 3)
        self.phrase_length = max(1, phrase_length)
        self.phrase_fill_prob = 0.65
        self._loop_index = 0
        self._phrase_end = False
        self._pending_phrase_fill = False
        self._accent_beats = set()

        self.accent_velocity_range = (100, 127)
        self.normal_velocity_range = (50, 99)
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
        else:
            self._phrase_end = (self._loop_index % self.phrase_length) == (self.phrase_length - 1)
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
        base_prob = max(0.0, min(1.0, self.tom_fill_prob))
        if self._phrase_end:
            base_prob = max(base_prob, max(0.0, min(1.0, self.phrase_fill_prob)))
        if self._pending_phrase_fill:
            base_prob = max(base_prob, max(0.0, min(1.0, self.phrase_fill_prob)))
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

        if events_by_index and self.rng.random() < self.crash_on_fill_prob:
            events_by_index.setdefault(fill_start_idx, []).append(self._build_midi(self.CRASH, is_accent=False))

        if events_by_index and self.rng.random() < self.tom_roll_prob:
            roll_count = 6 if self.grain >= 3 else 3
            for event in events_by_index.get(last_beat_start + max(positions), []):
                if event.get("note") in (self.TOM_LOW, self.TOM_MID, self.TOM_HIGH):
                    event["is_ratchet"] = True
                    event["ratchet_count"] = roll_count

        return events_by_index

    def _accent_beat_follower(self, beat: int, subdivision: int) -> tuple:
        # Dynamic beat templates based on the current loop size and grain (time signature and subdivision)
        percussion_template = PERCUSSION_TEMPLATE.get(self._get_template_key(), {})

        if not percussion_template:
            fallback_kick = [0]
            fallback_snare = [self.loop_size // 2] if self.loop_size >= 2 else []
            fallback_hihat = list(range(self.loop_size))
            percussion_template = {
                "KICK": fallback_kick,
                "SNARE": fallback_snare,
                "HIHAT": fallback_hihat,
                "TOM": [],
                "RIDE": [],
                "CRASH": [],
            }

        kick_beats = percussion_template.get("KICK", [])
        snare_beats = percussion_template.get("SNARE", [])
        hihat_beats = percussion_template.get("HIHAT", [])
        tom_beats = percussion_template.get("TOM", [])
        ride_beats = percussion_template.get("RIDE", [])
        crash_beats = percussion_template.get("CRASH", [])

        # Accent/Beat Follower
        is_kick_beat = (subdivision == 0 and beat in kick_beats)
        is_snare_beat = (subdivision == 0 and beat in snare_beats)
        is_hihat_beat = (beat in hihat_beats)
        is_tom_beat = (subdivision == 0 and beat in tom_beats)
        is_ride_beat = (beat in ride_beats)
        is_crash_beat = (subdivision == 0 and beat in crash_beats)

        return is_kick_beat, is_snare_beat, is_hihat_beat, is_tom_beat, is_ride_beat, is_crash_beat

    # ------------------------------------------------------------------
    # Accent and chord notifications
    # ------------------------------------------------------------------

    def notify_accents(self, accent_beats: List[int]) -> None:
        """Receive accent beats from the melody agent.

        Args:
            accent_beats (List[int]): Beat indices marked as accents.
        """
        self._accent_beats = {int(beat) for beat in accent_beats}

    def notify_chord_change(self, chord_pool: int) -> None:
        """Record chord pool changes to align phrase fills.

        Args:
            chord_pool (int): Current harmony chord pool identifier.
        """
        if int(chord_pool) == 1:
            self._pending_phrase_fill = True
    
    def _add_sub_filling(self, beat: int, subdivision: int) -> list:
        """
        Adds sub-fill events based on the current beat and subdivision. 
        This can include ghost notes, anticipatory hits, and fills.

        Args:
            beat (int): The current beat number in the loop.
            subdivision (int): The current subdivision within the beat.

        Returns:
            list: A list of MIDI events to be added as sub-fills.
        """
        events = []

        # anticipatory ghost/snare just before a snare beat
        lookback = max(1, self.grain // 4)
        if (beat % 2 == 1) and subdivision >= (self.grain - lookback) and self.rng.random() < 0.25:
            events.append(self._build_midi(self.SNARE, is_accent=False, velocity_range=self.ghost_velocity_range))

        # occasional hi-hat ratchet (rapid subdivision)
        if self.rng.random() < self.hat_ratchet_prob:
            events.append(self._build_midi(self.HIHAT_CLOSED, is_accent=False, is_ratchet=True))

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

    def process_tick(self, index: int):
        """Generate percussion events for a single clock tick.

        Args:
            index (int): Current tick index in the loop.

        Returns:
            list: Raw percussion event dictionaries.
        """
        events = []
        
        # =============== Rhythm Generation ===============
        # Determine exactly where we are in the loop based on the index
        beat = index // self.grain
        subdivision = index % self.grain
        
        # =============== Accent/Beat Follower ===============
        # Get the accent/beat follower results
        is_kick_beat, is_snare_beat, is_hihat_beat, is_tom_beat, is_ride_beat, is_crash_beat = self._accent_beat_follower(beat, subdivision)

        # =============== Base Groove Generation ===============
        # Generate the base groove events based on the beat follower results and add/sub filling probabilities
        accent_here = (beat in self._accent_beats) and subdivision == 0

        if is_kick_beat:
            if self.rng.random() >= self.kick_sub_prob: # 85% chance to play the main kick on the downbeat
                is_ratchet = self.rng.random() < self.kick_ratchet_prob
                events.append(
                    self._build_midi(
                        self.KICK,
                        is_accent=True,
                        is_ratchet=is_ratchet,
                    )
                )
        else:
            if subdivision != 0:
                roll = self.rng.random()
                if roll < self.ghost_kick_prob:
                    events.append(
                        self._build_midi(self.KICK, is_accent=False, velocity_range=self.ghost_velocity_range)
                    )
                elif roll < (self.ghost_kick_prob + self.kick_add_prob):
                    events.append(
                        self._build_midi(self.KICK, is_accent=accent_here)
                    )

        if is_snare_beat:
            if self.rng.random() >= self.snare_sub_prob:
                is_ratchet = self.rng.random() < self.snare_ratchet_prob
                events.append(
                    self._build_midi(
                        self.SNARE,
                        is_accent=True,
                        is_ratchet=is_ratchet,
                    )
                )
        else:
            if subdivision != 0 and self.rng.random() < self.snare_add_prob: # 5% chance to add a ghost snare on off-beats
                events.append(
                    self._build_midi(
                        self.SNARE,
                        is_accent=accent_here,
                        velocity_range=self.ghost_velocity_range,
                    )
                )

        if self._ride_mode and is_ride_beat and subdivision % self.ride_density == 0:
            if self.rng.random() < self.ride_bell_prob:
                events.append(self._build_midi(self.RIDE_BELL, is_accent=False))
            else:
                events.append(self._build_midi(self.RIDE, is_accent=False))
        elif is_hihat_beat and subdivision % self.hat_density == 0:
            hat_total = self.hat_open_prob + self.hat_closed_prob
            if hat_total <= 0:
                hat_note = self.HIHAT_CLOSED
            elif self.rng.random() < (self.hat_open_prob / hat_total):
                hat_note = self.HIHAT_OPEN
            else:
                hat_note = self.HIHAT_CLOSED
            events.append(self._build_midi(hat_note, is_accent=False))

        if is_tom_beat:
            events.append(
                self._build_midi(
                    self.rng.choice([self.TOM_LOW, self.TOM_MID, self.TOM_HIGH]),
                    is_accent=True,
                )
            )

        if is_crash_beat or (beat == 0 and subdivision == 0 and self.rng.random() < self.crash_prob_start):
            events.append(self._build_midi(self.CRASH, is_accent=False))

        # =============== Add/Sub Filling ===============
        # Merge in any sub-fill events for this tick
        events.extend(self.subfills.get(index, []))

        return events

    # ------------------------------------------------------------------
    # Precomputed fills
    # ------------------------------------------------------------------

    def add_sub_filling(self):
        """
        Precompute sub-fill events for the entire loop and store them in self.subfills.
        Returns a dict mapping absolute tick index -> list of events.
        """
        total_ticks = self.loop_size * self.grain
        subfills = {}
        self._ride_mode = self.rng.random() < self.ride_prob
        tom_fill_plan = self._build_tom_fill_plan()
        for idx in range(total_ticks):
            beat = idx // self.grain
            subdivision = idx % self.grain
            events = self._add_sub_filling(beat, subdivision)
            events.extend(tom_fill_plan.get(idx, []))
            if events:
                subfills[idx] = events

        self.subfills = subfills
        return subfills

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

        def clamp_prob(value: float) -> float:
            return max(0.0, min(1.0, float(value)))

        def clamp_int(value: int, minimum: int = 1) -> int:
            return max(minimum, int(value))

        prob_fields = {
            "kick_add_prob",
            "kick_sub_prob",
            "ghost_kick_prob",
            "kick_ratchet_prob",
            "snare_add_prob",
            "snare_sub_prob",
            "snare_ratchet_prob",
            "hat_open_prob",
            "hat_closed_prob",
            "hat_ratchet_prob",
            "crash_prob_start",
            "crash_on_fill_prob",
            "ride_prob",
            "ride_bell_prob",
            "tom_fill_prob",
            "tom_leadin_prob",
            "tom_roll_prob",
            "phrase_fill_prob",
        }

        int_fields = {
            "hat_density",
            "ride_density",
            "tom_fill_window",
            "phrase_length",
        }

        for key, value in kwargs.items():
            if key == "seed":
                self.rng.seed(value)
                changed = True
                continue
            if key == "meter":
                self.meter = value
                changed = True
                continue

            if key in prob_fields:
                new_value = clamp_prob(value)
            elif key in int_fields:
                new_value = clamp_int(value)
            else:
                continue

            if getattr(self, key, None) != new_value:
                setattr(self, key, new_value)
                changed = True

        if changed:
            self.phrase_length = max(1, int(self.phrase_length))
            self.add_sub_filling()

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
        grid = [[" " for _ in range(self.total_pulses)] for _ in range(4)]  # 4 rows for KICK, SNARE, HIHAT, TOM
        for event in events:
            note = event["note"]
            idx = event.get("index", 0)  # Assuming we add an 'index' field to track the tick index
            if note == self.KICK:
                grid[0][idx] = "K"
            elif note == self.SNARE:
                grid[1][idx] = "S"
            elif note in [self.HIHAT_CLOSED, self.HIHAT_OPEN]:
                grid[2][idx] = "H"
            elif note in [self.TOM_LOW, self.TOM_MID, self.TOM_HIGH]:
                grid[3][idx] = "T"  # Represent tom fills with 'T'

        print("KICK: " + "".join(grid[0]))
        print("SNARE: " + "".join(grid[1]))
        print("HIHAT: " + "".join(grid[2]))
        print("TOM:  " + "".join(grid[3]))