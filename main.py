"""
Entrypoint for running the PAMG clock in headless mode or with the live TCP socket server.
"""

import argparse
import asyncio
import os
import sys
from typing import Tuple

# Guard against windowless executions where sys.stdout/sys.stderr may be None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from src.core.configs import (
    ROUTING_MODE, 
    SINGLE_PORT_NAME, 
    MELODY_PORT_NAME, 
    DRUM_PORT_NAME, 
    DEBUG_MIDI
)
from src.core.clock import run_clock
from src.core.routing import RoutingType
from src.core.tcp_server import start_tcp_server
from src.models.game_state import GameState
from src.utils.audio import get_default_soundfont_path


def demo_game_state() -> Tuple[float, float]:
    """Return a fixed demo game-state tuple for quick testing."""
    return 100.0, 5.0


async def main() -> None:
    is_frozen = getattr(sys, "frozen", False)
    parser = argparse.ArgumentParser(description="PAMG - Progressive-Adaptive Music Generator")
    parser.add_argument(
        "--tcp", 
        action=argparse.BooleanOptionalAction,
        default=is_frozen,
        help="Start the live TCP socket server for game engine integration (default: True when packaged, False otherwise)"
    )
    parser.add_argument("--tcp-host", default="127.0.0.1", help="TCP server host (default: 127.0.0.1)")
    parser.add_argument("--tcp-port", type=int, default=9000, help="TCP server port (default: 9000)")
    parser.add_argument("--tempo", type=int, default=120, help="Initial tempo BPM (default: 120)")
    parser.add_argument("--loop-size", type=int, default=4, help="Measures / loop size (default: 4)")
    parser.add_argument("--grain", type=int, default=4, help="Subdivision grain factor (default: 4)")
    parser.add_argument("--seed", type=int, default=42, help="Base seed (default: 42, 0=improv)")
    parser.add_argument("--routing", default="single_port", choices=["single_port", "split_ports"], help="MIDI routing mode")
    parser.add_argument("--sf2", type=str, default=None, help="Path to .sf2 file to embed FluidSynth directly and bypass MIDI ports")
    parser.add_argument("--audio-driver", type=str, default=None, help="FluidSynth audio driver (wasapi, dsound, pulseaudio, coreaudio)")
    parser.add_argument(
        "--sidecar", 
        action="store_true", 
        default=os.environ.get("PAMG_SIDECAR", "").lower() in ("1", "true", "yes"),
        help="Auto-terminate server process when client disconnects (or set PAMG_SIDECAR=1)"
    )


    args = parser.parse_args()
    routing_mode = RoutingType(args.routing)
    sf2_path = args.sf2 or get_default_soundfont_path()

    if args.tcp:
        state = GameState(
            tempo=args.tempo,
            loop_size=args.loop_size,
            grain=args.grain,
            base_seed=args.seed,
        )
        print(f"Starting PAMG with TCP Server on {args.tcp_host}:{args.tcp_port} (sidecar={args.sidecar})...")
        server = await start_tcp_server(args.tcp_host, args.tcp_port, state, sidecar=args.sidecar)
        async with server:
            clock_task = asyncio.create_task(
                run_clock(
                    tempo=args.tempo,
                    loop_size=args.loop_size,
                    grain=args.grain,
                    is_playing=True,
                    routing_mode=routing_mode,
                    single_port_name=SINGLE_PORT_NAME,
                    melody_port_name=MELODY_PORT_NAME,
                    drum_port_name=DRUM_PORT_NAME,
                    debug_midi=DEBUG_MIDI,
                    base_seed=args.seed,
                    game_state=state,
                    sf2_path=sf2_path,
                    audio_driver=args.audio_driver,
                )
            )
            await clock_task
    else:
        print(f"Starting PAMG Clock in standalone mode ({args.tempo} BPM, loop_size={args.loop_size}, grain={args.grain})...")
        await run_clock(
            tempo=args.tempo,
            loop_size=args.loop_size,
            grain=args.grain,
            is_playing=True,
            routing_mode=routing_mode,
            single_port_name=SINGLE_PORT_NAME,
            melody_port_name=MELODY_PORT_NAME,
            drum_port_name=DRUM_PORT_NAME,
            debug_midi=DEBUG_MIDI,
            base_seed=args.seed,
            game_state_callback=demo_game_state,
            sf2_path=sf2_path,
            audio_driver=args.audio_driver,
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Clock stopped by user.")