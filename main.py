# DEPRECATED: This file is now a simple test harness for the async clock runner.
# The main PAMG entrypoint is now the GUI in pamg_gui.py, which imports and uses the core clock and player modules directly.

"""
Entrypoint for running the PAMG clock without the GUI.

This script wires configuration defaults into the async clock runner and
provides a minimal demo game-state callback for quick testing.
"""

import asyncio
from typing import Tuple

from src.core.configs import (
    ROUTING_MODE, 
    SINGLE_PORT_NAME, 
    MELODY_PORT_NAME, 
    DRUM_PORT_NAME, 
    DEBUG_MIDI
)
from src.core.clock import run_clock


# ---------------------------------------------------------------------------
# Demo game-state callback
# ---------------------------------------------------------------------------

def demo_game_state() -> Tuple[float, float]:
    """
    Return a fixed demo game-state tuple for quick testing.

    Returns:
        Tuple[float, float]: Example (health, enemy_count) values.
    """
    return 100.0, 5.0

if __name__ == "__main__":
    # Example usage (routing may still be under active development).
    tempo = 120  # Speeds up or slows down the clock (BPM)
    loop_size = 6  # Number of measures in the loop
    grain = 2  # 1 = quarter notes, 2 = eighth notes, etc.

    try:
        # Run the async clock until interrupted.
        asyncio.run(
            run_clock(
                tempo,
                loop_size,
                grain,
                is_playing=True,
                routing_mode=ROUTING_MODE,
                single_port_name=SINGLE_PORT_NAME,
                melody_port_name=MELODY_PORT_NAME,
                drum_port_name=DRUM_PORT_NAME,
                debug_midi=DEBUG_MIDI,
                game_state_callback=demo_game_state
            )
        )
    except KeyboardInterrupt:
        print("Clock stopped by user.")