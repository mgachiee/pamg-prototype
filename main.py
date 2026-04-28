import asyncio

from src.core.configs import ROUTING_MODE, SINGLE_PORT_NAME, MELODY_PORT_NAME, DRUM_PORT_NAME, DEBUG_MIDI
from src.core.clock import run_clock

if __name__ == "__main__":
    # Example usage
    tempo = 120 # Speeds up or slows down the clock (BPM)
    loop_size = 4 # Number of measures in the loop
    grain = 1 # 1 means quarter notes, 2 means eighth notes, etc.

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
            )
        )
    except KeyboardInterrupt:
        print("Clock stopped by user.")