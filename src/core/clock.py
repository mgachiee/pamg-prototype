import asyncio
import logging
from typing import Optional

from src.core.configs import (
    ROUTING_MODE, 
    SINGLE_PORT_NAME, 
    MELODY_PORT_NAME, 
    DRUM_PORT_NAME, 
    DEBUG_MIDI
)
from src.core.routing import RoutingType
from src.core.midi_io import open_midi_ports, close_midi_ports
from src.core.players import play_note, play_ratchet, play_chord, play_arpeggio
from src.core.midi_events import normalize_event
from src.core.scheduler import TaskManager
from src.modules.percussion_agent import PercussionAgent
from src.modules.melody_agent import MelodyAgent
from src.modules.harmony_agent import HarmonyAgent

logging.basicConfig(
    level=logging.DEBUG if DEBUG_MIDI else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

async def _midi_writer(port, queue: asyncio.Queue):
    """
    Continuously listens to the MIDI message queue and sends messages to the MIDI port in a non-blocking way.

    Args:
        port: The MIDI output port to send messages to.
        queue: An asyncio.Queue that receives MIDI messages to be sent. The writer will exit when it receives a None message.
    """
    while True:
        message = await queue.get()
        if message is None:
            queue.task_done()
            break
        try:
            port.send(message)
        except Exception as e:
            logging.error(f"Error sending MIDI message: {e}")
        finally:
            queue.task_done()

async def run_clock(
    tempo: int,
    loop_size: int,
    grain: int,
    is_playing: bool = True,
    routing_mode: RoutingType = ROUTING_MODE,
    single_port_name: str = SINGLE_PORT_NAME,
    melody_port_name: str = MELODY_PORT_NAME,
    drum_port_name: str = DRUM_PORT_NAME,
    debug_midi: bool = DEBUG_MIDI,
)-> None:
    """
    Builds the real-time grid for the sequencer based on the tempo, loop size, and grain size.

    Args:
        tempo (int): The tempo in beats per minute (BPM).
        loop_size (int): The size of the loop in beats.
        grain (int): The size of each grain in beats. (e.g., 4 for quarter notes, 8 for eighth notes, etc.)
        is_playing (bool): A flag indicating whether the sequencer is currently playing or not.
        routing_mode (RoutingType): The MIDI routing mode (single_port or split_ports).
        single_port_name (str): The name of the MIDI port to use in single-port mode.
        melody_port_name (str): The name of the MIDI port for melody output in split-port mode.
        drum_port_name (str): The name of the MIDI port for drum output in split-port mode.
        debug_midi (bool): If True, logs detailed MIDI event information for debugging purposes.
    """
    # =============== Count Loop ===============
    # Total indeces (pulses) in the loop (0, 1, 2, ..., total_pulses-1)
    total_pulses = loop_size * grain

    # Exact time duration of each pulse in seconds
    pulse_duration = 60 / (tempo * grain)

    logging.info(f"Starting Clock: {tempo} BPM, Loop Size: {loop_size} beats, Grain Size: {grain} beats")
    logging.debug(f"Total Pulses: {total_pulses}, Pulse Duration: {pulse_duration:.2f} seconds")

    # ============== Agent Network ===============
    # Initialize agents with loop and grain information to make informed decisions based on the current position in the loop
    percussion_agent = PercussionAgent(loop_size=loop_size, grain=grain)
    melody_agent = MelodyAgent(movement=MelodyAgent.movement_type.odd, loop_size=loop_size, grain=grain)
    harmony_agent = HarmonyAgent()
    # orchestration_agent = OrchestrationAgent() implement later for dynamic orchestration based on chord voicings, etc.

    # ============== MIDI Port Initialization ===============
    # Initialize MIDI ports for melody and percussion output based on the selected routing mode.
    port_mel = None
    port_perc = None

    # Queues for MIDI messages. If using single port mode, both agents will share the same queue and writer task.
    # Queues decouple the real-time clock loop from the MIDI output, allowing for smoother timing and avoiding blocking calls in the main loop.
    mel_queue: Optional[asyncio.Queue] = None
    perc_queue: Optional[asyncio.Queue] = None
    mel_writer_task = None
    perc_writer_task = None

    # Task manager to keep track of all scheduled note/chord tasks so we can await their completion on shutdown
    scheduled_tasks = TaskManager()

    try:
        # Open MIDI ports according to the routing configuration.
        port_mel, port_perc = open_midi_ports(
            routing_mode=routing_mode,
            melody_port_name=melody_port_name,
            drum_port_name=drum_port_name,
            single_port_name=single_port_name,
        )

        if routing_mode == RoutingType.single_port:
            logging.info(f"Routing mode: {routing_mode} -> using shared port '{single_port_name}'")
        else:
            logging.info(f"Routing mode: {routing_mode} -> melody='{melody_port_name}', drums='{drum_port_name}'")

        # Create queues and writer tasks. If single port mode, use a single queue.
        if port_mel is port_perc:
            combined = asyncio.Queue()
            mel_queue = combined
            mel_writer_task = asyncio.create_task(_midi_writer(port_mel, combined))
        else:
            mel_queue = asyncio.Queue()
            perc_queue = asyncio.Queue()
            mel_writer_task = asyncio.create_task(_midi_writer(port_mel, mel_queue))
            perc_writer_task = asyncio.create_task(_midi_writer(port_perc, perc_queue))

        # ============== Main Clock Loop ===============
        tick = 0 # Used to track the current pulse index in the loop (0 to total_pulses-1)
        loop_start = asyncio.get_running_loop().time()

        while is_playing:
            # Calculate the scheduled time for the current tick
            scheduled_time = loop_start + tick * pulse_duration
            sleep_for = scheduled_time - asyncio.get_running_loop().time()

            # If we're ahead of schedule, sleep until the next tick
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            # If we're behind, log a warning and continue immediately
            elif sleep_for <= 0:
                logging.warning(f"Warning: Behind schedule by {-sleep_for:.3f} seconds.")

            # Current position in the loop is determined by local_index (0 to total_pulses-1), which resets every loop iteration
            local_index = tick % total_pulses # Used for agent processing to make decisions accordingly

            # Current measure index (0 to loop_size-1) and subdivision index (0 to grain-1) within the measure
            measure_index = (tick // total_pulses) % loop_size # Useful for clarity but not currently used by agents except for logging chord changes
            subdivision = local_index % grain # Useful for agents to determine if we're on a downbeat, upbeat, or offbeat subdivision

            # On downbeat, play chord and arpeggio
            if (subdivision == 0):
                current_chord = harmony_agent.get_current_chord(measure_index=measure_index)
                logging.info(f"Measure {measure_index + 1}/{loop_size} - Current Chord: {current_chord}")

                if current_chord:
                    chord_duration = pulse_duration * grain
                    chord_task = asyncio.create_task(
                        play_chord(
                            port_mel,
                            current_chord,
                            velocity=80,
                            duration=chord_duration,
                            channel=1,
                        )
                    )
                    arpeggio_task = asyncio.create_task(
                        play_arpeggio(
                            port_mel,
                            current_chord,
                            velocity=70,
                            total_duration=chord_duration,
                            channel=1,
                        )
                    )
                    scheduled_tasks.schedule_task(chord_task)
                    scheduled_tasks.schedule_task(arpeggio_task)

            # Produce agent events using local_index so agents see the same index pattern
            drum_hits = percussion_agent.process_tick(index=local_index)
            melody_hits = melody_agent.process_tick(index=local_index, current_chord=current_chord)

            # Melody dispatch
            for hit in melody_hits:
                event = normalize_event(hit=hit, default_channel=0, default_duration=pulse_duration * 0.9)
                if event is None:
                    if debug_midi:
                        logging.debug(f"Skipping invalid melody event: {hit}")
                    continue

                if debug_midi:
                    logging.debug(
                        f"Melody -> note={event.note} vel={event.velocity} "
                        f"ch={event.channel} dur={event.duration:.3f}"
                    )

                # Racheted melody acts as Noisemaker to mimic human-like tremolo (fast repeating notes)
                if event.is_ratchet:
                    task = asyncio.create_task(
                        play_ratchet(
                            mel_queue,
                            event.note,
                            event.velocity,
                            event.duration,
                            subdivisions=event.ratchet_count,
                            channel=event.channel,
                        )
                    )
                # Normal note plays as usual
                else:
                    task = asyncio.create_task(
                        play_note(
                            mel_queue,
                            event.note,
                            event.velocity,
                            event.duration,
                            channel=event.channel,
                        )
                    )

                scheduled_tasks.schedule_task(task)

            # Drum dispatch
            for hit in drum_hits:
                event = normalize_event(hit=hit, default_channel=9, default_duration=pulse_duration * 0.9)
                if event is None:
                    if debug_midi:
                        logging.debug(f"Skipping invalid drum event: {hit}")
                    continue

                if debug_midi:
                    logging.debug(
                        f"Drum -> note={event.note} vel={event.velocity} "
                        f"ch={event.channel} dur={event.duration:.3f}"
                    )

                # Ratcheted drums add extra "ghost" hits for more groove and human feel
                if event.is_ratchet:
                    task = asyncio.create_task(
                        play_ratchet(
                            perc_queue,
                            event.note,
                            event.velocity,
                            event.duration,
                            subdivisions=event.ratchet_count,
                            channel=event.channel,
                        )
                    )
                # Normal drum hit plays as usual
                else:
                    task = asyncio.create_task(
                        play_note(
                            perc_queue,
                            event.note,
                            event.velocity,
                            event.duration,
                            channel=event.channel,
                        )
                    )

                scheduled_tasks.schedule_task(task)

            tick += 1

    except (OSError, IOError, ValueError) as e:
        logging.exception(f"MIDI setup/runtime error: {e}")

    finally:
        # Wait for all scheduled note/chord task to finish before shutting down to ensure all MIDI messages are sent properly
        player_tasks = [t for t in scheduled_tasks.get_scheduled_tasks() if t is not None]
        if player_tasks:
            if debug_midi:
                logging.debug(f"Waiting for {len(scheduled_tasks)} note tasks to finish...")
            await asyncio.gather(*player_tasks, return_exceptions=True)

        # Signal the writer to exit
        if mel_queue is not None:
            await mel_queue.put(None)
        if perc_queue is not None and perc_queue is not mel_queue:
            await perc_queue.put(None)

        # Await writer tasks to finish after receiving the shutdown signal
        writer_tasks = []
        if mel_writer_task is not None:
            writer_tasks.append(mel_writer_task)
        if perc_writer_task is not None:
            writer_tasks.append(perc_writer_task)
        if writer_tasks:
            await asyncio.gather(*writer_tasks, return_exceptions=True)

        # Close MIDI ports
        try:
            close_midi_ports(port_mel, port_perc)
        except Exception as e:
            logging.exception(f"Error closing MIDI ports: {e}")