import asyncio

from src.core.configs import (
    ROUTING_MODE, 
    SINGLE_PORT_NAME, 
    MELODY_PORT_NAME, 
    DRUM_PORT_NAME, 
    DEBUG_MIDI
)
from src.core.clock import run_clock

# NOTE: 
# Working conceptually, but the actual MIDI output and routing logic is still being developed and may not function as intended yet.
def demo_game_state():
    return 100.0, 5.0 # Example player health and enemy count for testing

if __name__ == "__main__":
    # Example usage
    tempo = 120 # Speeds up or slows down the clock (BPM)
    loop_size = 6 # Number of measures in the loop
    grain = 2 # 1 means quarter notes, 2 means eighth notes, etc.

    try:
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