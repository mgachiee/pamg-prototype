import random
from enum import Enum

from src.core.midi_events import MidiEvent

class MelodyAgent():
    """
    The Melody Agent (MA) is responsible for generating melodic lines that complement the Harmony Agent's chords. 
    It uses a 'drunk walk' algorithm to create melodies that are both coherent and surprising, while also incorporating rhythmic elements like syncopation and accents.
    """
    movement_type = Enum("MovementType", "odd even")
    drunk_modes = Enum("DrunkModes", "drunk drunk-contour")

    def __init__(self, movement: movement_type, loop_size: int, grain: int):
        self.movement = movement
        self.loop_size = loop_size
        self.grain = grain

        self.max_step = 4
        # Numbers representing MIDI note values (C4 = 60, C#4/Db4 = 61, D4 = 62, ..., C5 = 72)
        self.current_pitch = 60  # Start at Middle C (C4)
        self.pitch_range = (48, 72)  # Limit to one octave below and above (C3 to C5)

        self.midi_channel = 0  # Default MIDI channel for melody

    def _build_midi(self, note: int, velocity: int, is_ratchet: bool = False):
        return {
            "note": note,
            "velocity": velocity,
            # "syncopated": is_syncopated,
            "is_ratchet": is_ratchet,
            "ratchet_count": 3,
            "duration": None,  # Duration can be determined by the Clock or left to default
            "channel": self.midi_channel,
        }
    
    def process_tick(self, index: int, current_chord: list):
        """Processes the MA logic for a single clock tick."""
        # beat = index // self.grain
        subdivision = index % self.grain
        events = []

        # =============== Melody Rhythm Generation ===============
        # Generate onsets with a simple syncopation probability
        is_onset = False
        is_syncopated = False

        if subdivision == 0: 
            is_onset = True # Always play on the strong downbeats
        elif random.random() < 0.3: 
            is_onset = True # 30% chance to play on a subdivision (syncopation/offbeat)
            is_syncopated = True

        if not is_onset:
            return events # No note on this tick

        # =============== Velocity Generation ===============
        # Accents on syncopated onsets
        if is_syncopated:
            velocity = random.randint(100, 127) # Strong accent
        else:
            velocity = random.randint(60, 90)   # Normal hit

        # =============== Melody Pitches Generation ('Drunk Walk') ===============
        # Randomly step up or down from the LAST played note. This creates a sense of coherence, 
        # but the random stepping allows for surprising twists and turns.
        step = random.randint(-self.max_step, self.max_step)
        raw_pitch = self.current_pitch + step

        # Keep it within the defined pitch range to avoid out-of-bounds MIDI notes
        raw_pitch = max(self.pitch_range[0], min(self.pitch_range[1], raw_pitch))

        # =============== Harmony Filter ===============
        # The raw pitch might sound terrible. We must "snap" it to the nearest valid 
        # pitch provided by the Harmony Agent's current chord.
        filtered_pitch = min(current_chord, key=lambda chord_note: abs(chord_note - raw_pitch))
        
        # Save this filtered pitch as the starting point for the next 'drunk' step
        self.current_pitch = filtered_pitch

        # =============== MIDI Event Construction ===============
        events.append(self._build_midi(note=filtered_pitch, velocity=velocity));
        
        return events