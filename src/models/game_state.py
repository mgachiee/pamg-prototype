"""
GameState model for external game engine integration over TCP socket.
"""

from dataclasses import dataclass
from typing import Optional

from src.models.time_signature import TimeSignature


@dataclass
class GameState:
    """
    Runtime state container updated in real time via TCP socket.

    Attributes:
        x (Optional[float]): Valence / X position on XY pad [0.0, 1.0].
        y (Optional[float]): Arousal / Y position on XY pad [0.0, 1.0].
        health (float): Fallback game variable used to derive Valence.
        enemies (float): Fallback game variable used to derive Arousal.
        tempo (float): Clock tempo in BPM (> 0).
        loop_size (int): Number of measures / beats per loop (> 0).
        grain (int): Pulses per beat (> 0).
        base_seed (int): Base seed for phrase generation (0 = improv).
        structure_dirty (bool): Flag indicating loop_size/grain changed.
        paused (bool): Whether playback is currently paused.
        is_alive (bool): Lifecycle flag indicating engine is running.
        shutdown_requested (bool): Flag indicating graceful shutdown requested.
        current_step (int): Cumulative tick/step count since start.
        measure (int): Current measure index.
        step_in_measure (int): Current pulse index inside the measure.
        time_signature (str): Active time signature string ('4/4', '3/4', '6/8', '6/4').
    """

    x: Optional[float] = None
    y: Optional[float] = None
    health: float = 100.0
    enemies: float = 0.0
    tempo: float = 120.0
    loop_size: int = 4
    grain: int = 4
    base_seed: int = 42
    structure_dirty: bool = False
    paused: bool = True
    is_alive: bool = True
    shutdown_requested: bool = False
    reset_requested: bool = False
    current_step: int = 0
    measure: int = 0
    step_in_measure: int = 0
    time_signature: str = "4/4"

    def set_valence_arousal(self, valence: float, arousal: float) -> None:
        """
        Set x and y coordinates from affective Valence and Arousal.

        Supports both [-1.0, 1.0] and [0.0, 1.0] formats:
        - If negative values are supplied, maps [-1.0, 1.0] -> [0.0, 1.0] via (val + 1) / 2.
        - Otherwise, clamps directly to [0.0, 1.0].
        """
        v = float(valence)
        a = float(arousal)

        if v < 0.0 or a < 0.0:
            norm_x = (max(-1.0, min(1.0, v)) + 1.0) / 2.0
            norm_y = (max(-1.0, min(1.0, a)) + 1.0) / 2.0
        else:
            norm_x = max(0.0, min(1.0, v))
            norm_y = max(0.0, min(1.0, a))

        self.x = norm_x
        self.y = norm_y

    def set_time_signature(self, sig: str) -> None:
        """
        Set meter from one of the 4 standard time signatures:
        '4/4', '3/4', '6/8', or '6/4'.

        Updates loop_size and grain, and flags structure_dirty if changed.
        """
        sig_str = sig.strip()
        # Accept enum values or strings
        valid_signatures = {
            "4/4": (4, 4),
            "3/4": (3, 4),
            "6/8": (6, 2),
            "6/4": (6, 4),
        }

        if sig_str in valid_signatures:
            new_loop, new_grain = valid_signatures[sig_str]
            self.time_signature = sig_str
            if new_loop != self.loop_size or new_grain != self.grain:
                self.loop_size = new_loop
                self.grain = new_grain
                self.structure_dirty = True
        else:
            raise ValueError(
                f"Unsupported time signature '{sig_str}'. Must be one of: {list(valid_signatures.keys())}"
            )

    def reset(self) -> None:
        """
        Reset runtime state to defaults between client sessions.
        """
        self.x = None
        self.y = None
        self.health = 100.0
        self.enemies = 0.0
        self.paused = True
        self.current_step = 0
        self.measure = 0
        self.step_in_measure = 0
        self.structure_dirty = False
        self.shutdown_requested = False
        self.reset_requested = True
