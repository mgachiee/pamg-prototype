"""
Detailed note and event playback logger for PAMG.

Logs every note-on and musical gesture played by each agent and instrument
to a dedicated .log file for inspection, verification, and analysis.
"""

import os
import time
from typing import Optional

# Scientific pitch names
PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# GM Drum names on channel 9
DRUM_NAMES = {
    35: "Acoustic Bass Drum",
    36: "Bass Drum 1 (Kick)",
    37: "Side Stick",
    38: "Acoustic Snare",
    39: "Hand Clap",
    40: "Electric Snare",
    41: "Low Floor Tom",
    42: "Closed Hi-Hat",
    43: "High Floor Tom",
    44: "Pedal Hi-Hat",
    45: "Low Tom",
    46: "Open Hi-Hat",
    47: "Low-Mid Tom",
    48: "Hi-Mid Tom",
    49: "Crash Cymbal 1",
    50: "High Tom",
    51: "Ride Cymbal 1",
    52: "Chinese Cymbal",
    53: "Ride Bell",
    54: "Tambourine",
    55: "Splash Cymbal",
    56: "Cowbell",
    57: "Crash Cymbal 2",
}

# Standard channel instrument mappings in PAMG (matching 8-channel orchestral matrix + drums)
CHANNEL_LABELS = {
    0: "Melody (Strings)",
    1: "Melody (Piano)",
    2: "Melody (Woodwinds)",
    3: "Melody (Brass)",
    4: "Harmony (Strings)",
    5: "Harmony (Piano)",
    6: "Harmony (Woodwinds)",
    7: "Harmony (Brass)",
    9: "Percussion (Drums)",
}


def midi_to_pitch_name(note: int) -> str:
    """Convert MIDI note number (0..127) to scientific pitch name (e.g. 60 -> C4)."""
    if not (0 <= note <= 127):
        return f"?({note})"
    octave = (note // 12) - 1
    name = PITCH_NAMES[note % 12]
    return f"{name}{octave}"


class NoteLogger:
    """Thread-safe and async-safe playback event logger."""

    def __init__(self, log_path: str = "logs/pamg_playback.log"):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path) if os.path.dirname(self.log_path) else ".", exist_ok=True)
        self._file = None
        self._open_log()

    def _open_log(self) -> None:
        try:
            self._file = open(self.log_path, "a", encoding="utf-8", buffering=1)
            self._file.write(
                f"\n{'='*95}\n"
                f"PAMG PLAYBACK LOG SESSION STARTED — {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'='*95}\n"
                f"{'Timestamp':<12} | {'Pos (M:B:S:P)':<16} | {'Agent':<11} | {'Instrument (Ch)':<24} | {'Note':<10} | {'Vel':<4} | {'Dur(s)':<7} | {'Artic':<8}\n"
                f"{'-'*95}\n"
            )
            self._file.flush()
        except Exception as e:
            print(f"[NoteLogger Warning] Could not open log file {self.log_path}: {e}")

    def log_note(
        self,
        measure: int,
        beat: int,
        step: int,
        pulse: int,
        agent: str,
        channel: int,
        note: int,
        velocity: int,
        duration: float,
        articulation: str = "normal",
        instrument_label: Optional[str] = None,
    ) -> None:
        """Log a single played note event."""
        if not self._file:
            return

        now_str = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
        pos_str = f"M:{measure:02d} B:{beat:02d} S:{step:02d} P:{pulse:03d}"

        if channel == 9:
            note_str = f"{note} ({DRUM_NAMES.get(note, 'Perc')[:6]})"
            inst_str = instrument_label or CHANNEL_LABELS.get(9, "Drums (Ch 9)")

            line = (
                f"{now_str:<12} | {pos_str:<16} | {agent:<11} | {inst_str:<24} | "
                f"{note_str:<10} | {velocity:<4} | {duration:<7.3f} | {articulation:<8}\n"
            )
        # else:
        #     note_str = f"{note} ({midi_to_pitch_name(note)})"
        #     inst_str = instrument_label or CHANNEL_LABELS.get(channel, f"Ch {channel}")

        # line = (
        #     f"{now_str:<12} | {pos_str:<16} | {agent:<11} | {inst_str:<24} | "
        #     f"{note_str:<10} | {velocity:<4} | {duration:<7.3f} | {articulation:<8}\n"
        # )
        try:
            self._file.write(line)
            self._file.flush()
        except Exception:
            pass

    def close(self) -> None:
        """Close the log file cleanly."""
        if self._file:
            try:
                self._file.write(f"{'-'*95}\nPAMG PLAYBACK SESSION ENDED — {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                self._file.flush()
                self._file.close()
            except Exception:
                pass
            self._file = None


# Global singleton instance
note_logger = NoteLogger()
