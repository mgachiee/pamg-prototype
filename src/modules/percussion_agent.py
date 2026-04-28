import random

class PercussionAgent:
    """
    The Percussion Agent (PA) is responsible for generating rhythmic patterns that drive the groove of the music.
    It uses a combination of beat generation, accent/beat following, and sub-filling techniques to create dynamic and evolving drum patterns.
    """

    def __init__(self, loop_size: int, grain: int):
        self.loop_size = loop_size
        self.grain = grain
        self.midi_channel = 9  # MIDI channel 10 in 1-based numbering

        # Standard General MIDI Drum Map Values
        self.KICK = 36
        self.SNARE = 38
        self.HIHAT_CLOSED = 42
        self.HIHAT_OPEN = 46
        self.TOM_LOW = 45
        self.TOM_MID = 48
        self.TOM_HIGH = 50

        # Precompute sub-fill events for the entire loop
        self.subfills = {}
        self.add_sub_filling()

    def _accent_beat_follower(self, beat: int, subdivision: int) -> tuple:
        # Accent/Beat Follower
        is_kick_beat = (subdivision == 0 and beat % 2 == 0)  # Kick on 1, 3, 5, ...
        is_snare_beat = (subdivision == 0 and beat % 2 == 1)  # Snare on 2, 4, 6, ...
        is_hihat_beat = (subdivision == 0)  # Hi-hat on every beat

        return is_kick_beat, is_snare_beat, is_hihat_beat
    
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

        # small chance for ghost kick on off-beats
        if subdivision != 0 and random.random() < 0.06:
            events.append(self._build_midi(self.KICK, is_accent=False))

        # anticipatory ghost/snare just before a snare beat
        lookback = max(1, self.grain // 4)
        if (beat % 2 == 1) and subdivision >= (self.grain - lookback) and random.random() < 0.25:
            events.append(self._build_midi(self.SNARE, is_accent=False))

        # occasional hi-hat ratchet (rapid subdivision)
        if random.random() < 0.03:
            events.append(self._build_midi(self.HIHAT_CLOSED, is_accent=False, is_ratchet=True))

        # tom fill on the last beat of the loop (spread over the final subdivisions)
        if beat == (self.loop_size - 1):
            fill_window = max(1, self.grain // 2)
            if subdivision >= (self.grain - fill_window) and random.random() < 0.35:
                tom = random.choice([self.TOM_LOW, self.TOM_MID, self.TOM_HIGH])
                events.append(self._build_midi(tom, is_accent=False))

        return events


    def _build_midi(self, note: int, is_accent: bool, is_ratchet: bool = False):
        velocity = random.randint(100, 127) if is_accent else random.randint(50, 99)
        return {
            "note": note,
            "velocity": velocity,
            "is_ratchet": is_ratchet,
            "ratchet_count": 3,
            "duration": None,
            "channel": self.midi_channel,
        }

    def process_tick(self, index: int):
        events = []
        
        # =============== Rhythm Generation ===============
        # Determine exactly where we are in the loop based on the index
        beat = index // self.grain
        subdivision = index % self.grain
        
        # =============== Accent/Beat Follower ===============
        # Get the accent/beat follower results
        is_kick_beat, is_snare_beat, is_hihat_beat = self._accent_beat_follower(beat, subdivision)

        # Beat Generation: Determine which instruments to play based on the current beat and subdivision
        if is_kick_beat:
            if random.random() > 0.05: # 95% chance to play the kick
                events.append(self._build_midi(self.KICK, is_accent=True))
        else:
            if random.random() < 0.08: # 8% chance to add a non-accented "ghost" kick on off-beats
                events.append(self._build_midi(self.KICK, is_accent=False))

        if is_snare_beat:
            events.append(self._build_midi(self.SNARE, is_accent=True))

        if is_hihat_beat:
            if random.random() > 0.1: # 90% chance to play the hi-hat
                events.append(self._build_midi(self.HIHAT_CLOSED, is_accent=False))
            else:
                events.append(self._build_midi(self.HIHAT_OPEN, is_accent=False))

        # =============== Add/Sub Filling ===============
        # Merge in any sub-fill events for this tick
        events.extend(self.subfills.get(index, []))

        return events

    def add_sub_filling(self):
        """
        Precompute sub-fill events for the entire loop and store them in self.subfills.
        Returns a dict mapping absolute tick index -> list of events.
        """
        total_ticks = self.loop_size * self.grain
        subfills = {}
        for idx in range(total_ticks):
            beat = idx // self.grain
            subdivision = idx % self.grain
            events = self._add_sub_filling(beat, subdivision)
            if events:
                subfills[idx] = events

        self.subfills = subfills
        return subfills