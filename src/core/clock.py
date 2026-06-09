"""
Real-time clock loop and agent orchestration.

This module owns the authoritative timing grid, drives parameter updates,
and dispatches MIDI events for all PAMG agents.
"""

import asyncio
import mido
from typing import Callable, Optional, Tuple

from src.core.configs import (
    ROUTING_MODE, 
    SINGLE_PORT_NAME, 
    MELODY_PORT_NAME, 
    DRUM_PORT_NAME, 
    DEBUG_MIDI,
    MELODY_CHANNEL,
    HARMONY_CHANNELS,
    HARMONY_LAYER_WEIGHTS,
    HARMONY_LAYER_MODE,
    MELODY_RANGE,
    HARMONY_RANGE,
    MELODY_PROGRAM,
    HARMONY_PROGRAMS,
    PRESET_A,
    PRESET_B,
    PRESET_C,
    PRESET_D,
    MAX_HEALTH,
    MAX_ENEMIES
)
from src.core.routing import RoutingType
from src.core.midi_io import open_midi_ports, close_midi_ports
from src.core.players import play_note, play_ratchet
from src.core.midi_events import normalize_event
from src.core.scheduler import TaskManager
from src.modules.percussion_agent import PercussionAgent
from src.modules.melody_agent import MelodyAgent
from src.modules.harmony_agent import HarmonyAgent
from src.modules.orchestrator_agent import OrchestratorAgent
from src.core.preset_interpolator import MultiParameterPresetInterpolator, clamp
from src.core.seeded_phrase_generator import SeededPhraseGenerator
from src.core.logger import Logger

logger = Logger()


# ---------------------------------------------------------------------------
# MIDI writer task
# ---------------------------------------------------------------------------

# ------------------------------------------------------------------
# Queue drain loop
# ------------------------------------------------------------------

async def _midi_writer(port, queue: asyncio.Queue) -> None:
    """
    Drain a MIDI queue and send messages to a port.

    Args:
        port: MIDI output port for the messages.
        queue (asyncio.Queue): Queue receiving `mido.Message` instances.
            A `None` sentinel stops the writer.
    """
    while True:
        message = await queue.get()
        if message is None:
            queue.task_done()
            break
        try:
            port.send(message)
        except Exception as e:
            logger.error(f"Error sending MIDI message: {e}")
        finally:
            queue.task_done()


# ---------------------------------------------------------------------------
# Game-state mapping
# ---------------------------------------------------------------------------

def map_gamevars_to_xy(
    player_health: float,
    enemy_count: float,
    max_health: float = MAX_HEALTH,
    max_enemies: float = MAX_ENEMIES,
) -> Tuple[float, float]:
    """
    Map raw game-state values to normalized XY coordinates.

    Health is inverted so low health drives higher X (more tension), while
    enemy count pushes Y upward. Both axes are clamped to [0, 1] and
    softened with a power curve for smoother control near zero.

    Args:
        player_health (float): Raw health value (0..max_health).
        enemy_count (float): Raw enemy count (0..max_enemies).
        max_health (float): Upper bound used for normalization.
        max_enemies (float): Upper bound used for normalization.

    Returns:
        Tuple[float, float]: Normalized (x, y) in [0, 1].
    """
    health_norm = clamp(player_health / max_health)
    enemy_norm = clamp(enemy_count / max_enemies)

    x = clamp(1.0 - health_norm)
    y = clamp(enemy_norm)

    x = x ** 1.5
    y = y ** 1.5

    return x, y

# ---------------------------------------------------------------------------
# Main clock loop
# ---------------------------------------------------------------------------

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
    game_state_callback: Optional[Callable[[], Tuple[float, float]]] = None,
    state_broadcast_callback: Optional[Callable[[dict], None]] = None,
    base_seed: int = 42,
    max_ticks: Optional[int] = None,
) -> None:
    """
    Run the real-time clock loop and drive all PAMG agents.

    The loop computes a deterministic pulse grid from tempo, loop size, and
    grain. Each pulse updates interpolated parameters, triggers phrase-level
    changes, gathers agent events, and dispatches MIDI output.

    Args:
        tempo (int): Tempo in beats per minute (BPM).
        loop_size (int): Loop length in beats.
        grain (int): Subdivision factor (1 = quarter notes, 2 = eighths).
        is_playing (bool): Whether the clock loop should run.
        routing_mode (RoutingType): MIDI routing strategy.
        single_port_name (str): Port name for single-port routing.
        melody_port_name (str): Port name for melody output.
        drum_port_name (str): Port name for percussion output.
        debug_midi (bool): Enable verbose MIDI logging when True.
        game_state_callback (
            Optional[Callable[[], Tuple[float, float]]]
        ):
            Optional callback returning (health, enemies).
        base_seed (int): Base seed for motif generation (0 = improv).
        max_ticks (Optional[int]): Optional tick limit for tests or demos.

    Raises:
        OSError: If required MIDI ports are unavailable.
        ValueError: If routing settings are invalid.
    """
    # ------------------------------------------------------------------
    # Timing grid
    # ------------------------------------------------------------------
    # Total pulses in the loop (0..total_pulses-1)
    total_pulses = loop_size * grain

    # Exact time duration of each pulse in seconds.
    pulse_duration = 60 / (tempo * grain)

    logger.info(f"Starting Clock: {tempo} BPM, Loop Size: {loop_size} beats, Grain Size: {grain} beats")
    logger.debug(f"Total Pulses: {total_pulses}, Pulse Duration: {pulse_duration:.2f} seconds")

    # ------------------------------------------------------------------
    # Agent network
    # ------------------------------------------------------------------
    # Initialize agents with loop and grain information.
    percussion_agent = PercussionAgent(loop_size=loop_size, grain=grain)
    melody_agent = MelodyAgent(
        movement=MelodyAgent.movement_type.odd,
        loop_size=loop_size,
        grain=grain,
    )
    harmony_agent = HarmonyAgent(loop_size=loop_size, grain=grain)
    orchestrator_agent = OrchestratorAgent(
        melody_channel=MELODY_CHANNEL,
        harmony_channels=HARMONY_CHANNELS,
        harmony_layer_weights=HARMONY_LAYER_WEIGHTS,
        melody_range=MELODY_RANGE,
        harmony_range=HARMONY_RANGE,
        harmony_programs=HARMONY_PROGRAMS,
        melody_program=MELODY_PROGRAM,
        harmony_layer_mode=HARMONY_LAYER_MODE,
    )

    spg = SeededPhraseGenerator(base_seed=base_seed)
    _spg_prev_seed = spg.current_seed  # Track seed changes.
    last_discrete_params = PRESET_A
    last_chord_pool = harmony_agent.get_chord_pool()

    # Initialize the XY pad preset interpolator.
    interpolator = MultiParameterPresetInterpolator(PRESET_A, PRESET_B, PRESET_C, PRESET_D, smoothing_time=0.12)

    # ------------------------------------------------------------------
    # MIDI port initialization
    # ------------------------------------------------------------------
    # Initialize MIDI ports for melody and percussion output.
    port_mel = None
    port_perc = None

    # Queues decouple the clock loop from MIDI output.
    mel_queue: Optional[asyncio.Queue] = None
    perc_queue: Optional[asyncio.Queue] = None
    mel_writer_task = None
    perc_writer_task = None

    # Track scheduled note/chord tasks for shutdown.
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
            logger.info(f"Routing mode: {routing_mode} -> using shared port '{single_port_name}'")
        else:
            logger.info(f"Routing mode: {routing_mode} -> melody='{melody_port_name}', drums='{drum_port_name}'")

        # Create queues and writer tasks. If single port mode, use one queue.
        if port_mel is port_perc:
            combined = asyncio.Queue()
            mel_queue = combined
            mel_writer_task = asyncio.create_task(_midi_writer(port_mel, combined))
        else:
            mel_queue = asyncio.Queue()
            perc_queue = asyncio.Queue()
            mel_writer_task = asyncio.create_task(_midi_writer(port_mel, mel_queue))
            perc_writer_task = asyncio.create_task(_midi_writer(port_perc, perc_queue))

        async def _send_program_changes(
            queue: Optional[asyncio.Queue],
        ) -> None:
            if queue is None:
                return
            try:
                for channel, program in (
                    orchestrator_agent.consume_program_changes()
                ):
                    message = mido.Message(
                        "program_change",
                        program=int(program),
                        channel=int(channel),
                    )
                    await queue.put(message)
            except Exception as e:
                logger.debug(f"Program change send failed: {e}")

        await _send_program_changes(mel_queue)

        # ------------------------------------------------------------------
        # Main clock loop
        # ------------------------------------------------------------------
        tick = 0  # Current pulse index in the loop.
        loop_start = asyncio.get_running_loop().time()

        while is_playing:
            # Calculate the scheduled time for the current tick.
            scheduled_time = loop_start + tick * pulse_duration
            sleep_for = scheduled_time - asyncio.get_running_loop().time()

            # If we're ahead of schedule, sleep until the next tick.
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            # If we're behind, log a warning and continue immediately.
            elif sleep_for <= 0:
                logger.warning(f"Warning: Behind schedule by {-sleep_for:.3f} seconds.")

            # Derive loop indices for this tick.
            local_index = tick % total_pulses
            loop_index = tick // total_pulses
            beat_index = local_index // grain
            measure_index = beat_index % loop_size
            subdivision = local_index % grain

            # ------------------------------------------------------------------
            # Game-state sampling and interpolation
            # ------------------------------------------------------------------
            # Map game state to XY and interpolate parameters.
            if game_state_callback is not None:
                try:
                    player_health, enemy_count = game_state_callback()
                except Exception as e:
                    logger.debug(f"Error in game state callback: {e}")
                    player_health, enemy_count = MAX_HEALTH, 0
            else:
                player_health, enemy_count = MAX_HEALTH, 0

            x, y = map_gamevars_to_xy(player_health, enemy_count)

            params = interpolator.update(x, y, pulse_duration)

            # Determine phrase boundary to snap discrete parameters.
            phrase_length = max(
                1,
                int(round(params.seeded_phrase_length)),
            )
            phrase_start = subdivision == 0 and (measure_index % phrase_length) == 0

            quantized_params = interpolator.get_quantized_state(
                phrase_start=phrase_start,
            )
            if quantized_params is not None:
                last_discrete_params = quantized_params

            # ------------------------------------------------------------------
            # State broadcasting
            # ------------------------------------------------------------------
            if state_broadcast_callback is not None:
                state_broadcast_callback({
                    "health": round(player_health, 2),
                    "enemies": round(enemy_count, 2),
                    "xy": {"x": round(x, 3), "y": round(y, 3)},
                    "melody_pitch": [
                        int(round(params.melody_pitch_low)),
                        int(round(params.melody_pitch_high)),
                    ],
                    "melody_syncopation": round(params.melody_syncopation, 3),
                    "drum_kick_prob": round(params.drum_kick_probability, 3),
                    "harmony_tension": round(params.harmony_tension, 3),
                    "phrase_length": phrase_length,
                })

            # ------------------------------------------------------------------
            # Agent parameter updates
            # ------------------------------------------------------------------
            # Only update agents if parameters have changed significantly,
            # or at phrase boundaries to ensure consistency.
            if tick == 0 or phrase_start or interpolator.smoothing_time > 0:
                melody_agent.update_params(
                    max_step=max(1, int(round(params.melody_max_step))),
                    pitch_range=(
                        int(round(params.melody_pitch_low)),
                        int(round(params.melody_pitch_high)),
                    ),
                    syncopation_probability=float(params.melody_syncopation),
                    accent_probability=float(params.melody_accent),
                    ratchet_probability=float(params.melody_ratchet_probability),
                )

                orchestrator_agent.update_params(
                    melody_range=(
                        int(round(params.melody_pitch_low)),
                        int(round(params.melody_pitch_high)),
                    ),
                    harmony_range=(
                        int(round(params.harmony_pitch_low)),
                        int(round(params.harmony_pitch_high)),
                    ),
                    harmony_layer_weights=[
                        float(weight)
                        for weight in params.harmony_layer_weights
                    ],
                    harmony_programs=last_discrete_params.harmony_programs,
                    melody_program=last_discrete_params.melody_program,
                    harmony_layer_mode=last_discrete_params.harmony_layer_mode,
                )

                percussion_agent.update_params(
                    kick_sub_prob=1.0 - float(params.drum_kick_probability),
                    ghost_kick_prob=float(params.drum_ghost_kick_probability),
                    snare_sub_prob=1.0 - float(params.drum_snare_probability),
                    hat_open_prob=float(params.drum_hat_open_probability),
                    hat_closed_prob=float(params.drum_hat_closed_probability),
                    hat_ratchet_prob=float(params.drum_ratchet_probability),
                )

                harmony_agent.update_params(
                    tension=float(params.harmony_tension),
                    chord_complexity=float(params.harmony_chord_complexity),
                    chord_change_probability=float(params.harmony_chord_change_probability),
                    harmony_add_probability=float(params.harmony_add_probability),
                    harmony_sub_probability=float(params.harmony_sub_probability),
                    harmony_accent_probability=float(params.harmony_accent_probability),
                )

            # ------------------------------------------------------------------
            # Phrase and loop boundary hooks
            # ------------------------------------------------------------------
            if phrase_start:
                melody_agent.on_phrase_start()
                orchestrator_agent.on_phrase_start()

            if local_index == 0:
                melody_agent.on_loop_start(loop_index)
                percussion_agent.on_loop_start(loop_index)
                accent_list = melody_agent.get_accent_list()
                harmony_agent.notify_accents(accent_list)
                percussion_agent.notify_accents(accent_list)

            if phrase_start:
                await _send_program_changes(mel_queue)

            # ------------------------------------------------------------------
            # Chord + seed updates
            # ------------------------------------------------------------------
            current_chord = harmony_agent.get_current_chord(
                measure_index=measure_index,
            )

            # On downbeat, update seed and log chord changes.
            if subdivision == 0:
                logger.info(
                    f"Measure {measure_index + 1}/{loop_size} - Current Chord: {current_chord}",
                )

                new_seed = spg.process_chord_change(
                    harmony_agent.get_chord_pool(),
                    phrase_length,
                )
                if new_seed != _spg_prev_seed:
                    melody_agent.update_params(seed=new_seed)
                    percussion_agent.update_params(seed=new_seed)
                    harmony_agent.update_params(seed=new_seed)
                    _spg_prev_seed = new_seed

            # Handle chord pool transitions for percussion fills.
            current_chord_pool = harmony_agent.get_chord_pool()
            if current_chord_pool != last_chord_pool:
                percussion_agent.notify_chord_change(current_chord_pool)
                last_chord_pool = current_chord_pool

            # ------------------------------------------------------------------
            # Event generation
            # ------------------------------------------------------------------
            try:
                drum_hits = percussion_agent.process_tick(index=local_index)
            except Exception as e:
                logger.debug(f"Percussion tick error: {e}")
                drum_hits = []

            try:
                harmony_hits = harmony_agent.process_tick(
                    index=local_index,
                    pulse_duration=pulse_duration,
                )
            except Exception as e:
                logger.debug(f"Harmony tick error: {e}")
                harmony_hits = []

            try:
                melody_hits = melody_agent.process_tick(
                    index=local_index,
                    current_chord=current_chord,
                    pulse_duration=pulse_duration,
                )
            except Exception as e:
                logger.debug(f"Melody tick error: {e}")
                melody_hits = []

            try:
                orchestrated_hits = orchestrator_agent.process_tick(
                    melody_hits,
                    harmony_hits,
                )
            except Exception as e:
                logger.debug(f"Orchestration tick error: {e}")
                orchestrated_hits = []

            # ------------------------------------------------------------------
            # MIDI dispatch
            # ------------------------------------------------------------------
            # Main stream dispatch (melody + harmony)
            for hit in orchestrated_hits:
                event = normalize_event(
                    hit=hit,
                    default_channel=0,
                    default_duration=pulse_duration * 0.9,
                )
                if event is None:
                    if debug_midi:
                        logger.debug(f"Skipping invalid main event: {hit}")
                    continue

                if debug_midi:
                    source = hit.get("source", "melody")
                    logger.debug(
                        f"Main ({source}) -> note={event.note} vel={event.velocity} "
                        f"ch={event.channel} dur={event.duration:.3f}"
                    )

                # Ratcheted melody creates a tremolo-like effect.
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
                        logger.debug(f"Skipping invalid drum event: {hit}")
                    continue

                if debug_midi:
                    logger.debug(
                        f"Drum -> note={event.note} vel={event.velocity} "
                        f"ch={event.channel} dur={event.duration:.3f}"
                    )

                # Ratcheted drums add extra hits for groove.
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
            if max_ticks is not None and tick >= max_ticks:
                is_playing = False

    except asyncio.CancelledError:
        logger.info("Clock cancelled by user.")
        raise

    except KeyboardInterrupt:
        logger.info("Clock stopped by user.")

    except (OSError, IOError, ValueError) as e:
        logger.exception(f"MIDI setup/runtime error: {e}")

    finally:
        # ------------------------------------------------------------------
        # Shutdown and cleanup
        # ------------------------------------------------------------------
        # Wait for scheduled note/chord tasks to finish.
        player_tasks = [t for t in scheduled_tasks.get_scheduled_tasks() if t is not None]
        if player_tasks:
            if debug_midi:
                logger.debug(f"Waiting for {len(scheduled_tasks)} note tasks to finish...")
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

        except KeyboardInterrupt:
            logger.info("MIDI port closure interrupted by user.")
        except Exception as e:
            logger.exception(f"Error closing MIDI ports: {e}")