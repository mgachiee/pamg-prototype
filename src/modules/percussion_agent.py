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

    def _accent_beat_follower(self, beat: int, subdivision: int):
        # Accent/Beat Follower
        is_kick_beat = (subdivision == 0 and beat % 2 == 0)  # Kick on 1, 3, 5, ...
        is_snare_beat = (subdivision == 0 and beat % 2 == 1)  # Snare on 2, 4, 6, ...
        is_hihat_beat = (subdivision == 0)  # Hi-hat on every beat

        return is_kick_beat, is_snare_beat, is_hihat_beat
    
    def _add_sub_filling(self, beat: int, subdivision: int):
        pass
    
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
        
        # Determine exactly where we are in the loop based on the index
        beat = index // self.grain
        subdivision = index % self.grain

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

        return events

    def add_sub_filling(self):
        pass