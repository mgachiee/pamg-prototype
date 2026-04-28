class HarmonyAgent():
    """
    The Harmony Agent is responsible for the musical backdrop. 
    It generates chord progressions, harmonies, and transpositions based on the current state of the music.
    """
    def __init__(self):
        # A simple 4-bar progression in C Major: C -> G -> Am -> F
        self.progression = [
            [60, 64, 67],  # C Major (C4, E4, G4)
            [55, 59, 62, 72],  # G Major (G3, B3, D4, G4)
            [57, 60, 64, 69],  # A Minor (A3, C4, E4, A4)
            [65, 69, 72]   # F Major (F4, A4, C5)
        ]

    def get_current_chord(self, measure_index: int)-> list:
        """
        Determine the current chord based on the measure index and the progression.

        Arguments:
        - measure_index: The index of the current measure in the loop.

        Returns:
        - A list of MIDI note values representing the current chord.
        """
        # Determine the current chord based on the measure index
        chord_index = measure_index % len(self.progression)  # Cycle through the progression
        return self.progression[chord_index]