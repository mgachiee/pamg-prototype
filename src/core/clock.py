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
    MELODY_CHANNELS,
    HARMONY_CHANNEL,
    HARMONY_CHANNELS,
    HARMONY_LAYER_WEIGHTS,
    HARMONY_LAYER_MODE,
    CHANNEL_FAMILIES,
    MELODY_RANGE,
    HARMONY_RANGE,
    FAMILY_RANGES,
    MELODY_PROGRAM,
    MELODY_PROGRAMS,
    HARMONY_PROGRAMS,
    PRESET_A,
    PRESET_B,
    PRESET_C,
    PRESET_D,
    MAX_HEALTH,
    MAX_ENEMIES,
    INTERPOLATION_SMOOTHING_TIME,
    AUDIO_CONFIG,
)
from src.core.routing import RoutingType
from src.core.midi_io import open_midi_ports, close_midi_ports
from src.core.players import play_note, play_ratchet, send_cc
from src.core.midi_events import normalize_event
from src.core.scheduler import TaskManager
from src.modules.percussion_agent import PercussionAgent
from src.modules.melody_agent import MelodyAgent
from src.modules.harmony_agent import HarmonyAgent
from src.modules.orchestrator_agent import OrchestratorAgent
from src.core.preset_interpolator import MultiParameterPresetInterpolator, clamp
from src.core.seeded_phrase_generator import SeededPhraseGenerator
from src.core.logger import Logger
from src.core.note_logger import note_logger
from src.models.game_state import GameState
from src.utils.audio import use_highres_timer

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
    Map raw game-state values to normalized XY coordinates (Valence/Arousal).

    Valence (X) is driven by health (high health = positive valence).
    Arousal (Y) is driven by enemy count (high count = high arousal).
    Both axes are clamped to [0, 1] and softened with a power curve.

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

    # Valence (X): 0.0 = Negative, 1.0 = Positive
    x = clamp(health_norm)
    # Arousal (Y): 0.0 = Low, 1.0 = High
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
    base_seed: int = 42,
    max_ticks: Optional[int] = None,
    game_state: Optional[GameState] = None,
    sf2_path: Optional[str] = None,
    audio_driver: Optional[str] = None,
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
    # Validation & State Sync
    # ------------------------------------------------------------------
    if game_state is not None:
        if game_state.tempo > 0:
            tempo = game_state.tempo
        if game_state.loop_size > 0:
            loop_size = game_state.loop_size
        if game_state.grain > 0:
            grain = game_state.grain
        if game_state.base_seed is not None:
            base_seed = game_state.base_seed

    if tempo <= 0:
        raise ValueError(f"tempo must be greater than 0, got {tempo}")
    if loop_size <= 0:
        raise ValueError(f"loop_size must be greater than 0, got {loop_size}")
    if grain <= 0:
        raise ValueError(f"grain must be greater than 0, got {grain}")

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
    initial_phrase_length = max(1, int(round(PRESET_A.seeded_phrase_length)))
    percussion_agent = PercussionAgent(
        loop_size=loop_size,
        grain=grain,
        phrase_length=initial_phrase_length,
    )
    melody_agent = MelodyAgent(
        movement=MelodyAgent.movement_type.odd,
        loop_size=loop_size,
        grain=grain,
        drunk_mode="dcontour",
    )
    harmony_agent = HarmonyAgent(loop_size=loop_size, grain=grain)
    orchestrator_agent = OrchestratorAgent(
        melody_channels=MELODY_CHANNELS,
        harmony_channels=HARMONY_CHANNELS,
        harmony_layer_weights=HARMONY_LAYER_WEIGHTS,
        melody_range=MELODY_RANGE,
        harmony_range=HARMONY_RANGE,
        harmony_programs=HARMONY_PROGRAMS,
        melody_program=MELODY_PROGRAM,
        melody_programs=MELODY_PROGRAMS,
        ha_register_ins=float(PRESET_A.ha_register_ins),
        ma_orch_plus_minus=float(PRESET_A.ma_orch_plus_minus),
        ha_ins_plus_minus=float(PRESET_A.ha_ins_plus_minus),
        audio_config=AUDIO_CONFIG,
        harmony_layer_mode=HARMONY_LAYER_MODE,
    )

    # Apply instrument family range overrides if configured.
    if FAMILY_RANGES:
        orchestrator_agent.update_params(
            family_ranges=FAMILY_RANGES,
            channel_families=CHANNEL_FAMILIES,
        )

    spg = SeededPhraseGenerator(base_seed=base_seed)
    _spg_prev_seed = spg.seed_state  # Track atomic seed state changes.
    last_discrete_params = PRESET_A
    last_chord_pool = harmony_agent.get_chord_pool()

    # Initialize the XY pad preset interpolator.
    # Layout (Valence, Arousal):
    # a (0,0) -> Q3 (-V, -A) -> Sad (Preset A)
    # b (1,0) -> Q4 (+V, -A) -> Calm (Preset B)
    # c (0,1) -> Q2 (-V, +A) -> Angry (Preset C)
    # d (1,1) -> Q1 (+V, +A) -> Excited (Preset D)
    interpolator = MultiParameterPresetInterpolator(
        PRESET_A, 
        PRESET_B, 
        PRESET_C, 
        PRESET_D, 
        smoothing_time=INTERPOLATION_SMOOTHING_TIME
    )
    if game_state is not None:
        if game_state.x is not None and game_state.y is not None:
            init_x, init_y = clamp(game_state.x, 0.0, 1.0), clamp(game_state.y, 0.0, 1.0)
        else:
            init_x, init_y = map_gamevars_to_xy(game_state.health, game_state.enemies)
        interpolator.snap_to(init_x, init_y)

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
    use_highres_timer("enable")

    try:
        # Open MIDI ports according to the routing configuration.
        port_mel, port_perc = open_midi_ports(
            routing_mode=routing_mode,
            melody_port_name=melody_port_name,
            drum_port_name=drum_port_name,
            single_port_name=single_port_name,
            sf2_path=sf2_path,
            audio_driver=audio_driver,
            audio_config=AUDIO_CONFIG,
        )

        if routing_mode == RoutingType.single_port:
            logger.info(f"Routing mode: {routing_mode} -> using shared port '{single_port_name}'")
        else:
            logger.info(f"Routing mode: {routing_mode} -> melody='{melody_port_name}', drums='{drum_port_name}'")

        # Create queues and writer tasks. If single port mode, use one queue.
        if port_mel is port_perc:
            combined = asyncio.Queue()
            mel_queue = combined
            perc_queue = combined
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
                    target_queue = perc_queue if (channel == 9 and perc_queue is not None) else queue
                    message = mido.Message(
                        "program_change",
                        program=int(program),
                        channel=int(channel),
                    )
                    await target_queue.put(message)
            except Exception as e:
                logger.debug(f"Program change send failed: {e}")

        async def _send_cc_changes(
            queue: Optional[asyncio.Queue],
        ) -> None:
            if queue is None:
                return
            try:
                for channel, control, value in (
                    orchestrator_agent.consume_cc_changes()
                ):
                    target_queue = perc_queue if (channel == 9 and perc_queue is not None) else queue
                    message = mido.Message(
                        "control_change",
                        channel=int(channel),
                        control=int(control),
                        value=int(value),
                    )
                    await target_queue.put(message)
            except Exception as e:
                logger.debug(f"CC change send failed: {e}")

        await _send_program_changes(mel_queue)
        await _send_cc_changes(mel_queue)

        # ------------------------------------------------------------------
        # Main clock loop
        # ------------------------------------------------------------------
        tick = 0  # Cumulative pulse index
        step_in_loop = 0  # Current pulse index within the loop [0, total_pulses - 1]
        loop_index = 0  # Current measure / loop counter

        running_loop = asyncio.get_running_loop()
        next_pulse_time = running_loop.time()

        while is_playing:
            # Check for external session reset
            if game_state is not None and game_state.reset_requested:
                tick = 0
                step_in_loop = 0
                loop_index = 0
                game_state.current_step = 0
                game_state.measure = 0
                game_state.step_in_measure = 0
                game_state.reset_requested = False
                next_pulse_time = running_loop.time()
                if game_state.x is not None and game_state.y is not None:
                    rx, ry = clamp(game_state.x, 0.0, 1.0), clamp(game_state.y, 0.0, 1.0)
                else:
                    rx, ry = map_gamevars_to_xy(game_state.health, game_state.enemies)
                interpolator.snap_to(rx, ry)

            # Derive loop indices for this tick.
            local_index = step_in_loop
            beat_index = local_index // grain
            measure_index = beat_index % loop_size
            subdivision = local_index % grain

            # ------------------------------------------------------------------
            # Game-state sampling and interpolation
            # ------------------------------------------------------------------
            if game_state is not None:
                game_state.current_step = tick
                game_state.measure = loop_index
                game_state.step_in_measure = local_index

                # If playback is paused via TCP, wait and reset next_pulse_time
                if game_state.paused:
                    while game_state.paused and game_state.is_alive and not game_state.shutdown_requested:
                        await asyncio.sleep(0.05)
                    next_pulse_time = running_loop.time()

                if not game_state.is_alive or game_state.shutdown_requested:
                    is_playing = False
                    break

                # Live dynamic tempo adjustment
                if game_state.tempo > 0 and game_state.tempo != tempo:
                    tempo = game_state.tempo
                    pulse_duration = 60.0 / (tempo * grain)

                # Loop boundary structural change (loop_size / grain / meter)
                if local_index == 0 and game_state.structure_dirty:
                    if game_state.loop_size > 0:
                        loop_size = game_state.loop_size
                    if game_state.grain > 0:
                        grain = game_state.grain
                    total_pulses = loop_size * grain
                    pulse_duration = 60.0 / (tempo * grain)
                    current_meter = game_state.time_signature
                    melody_agent.update_params(loop_size=loop_size, grain=grain, meter=current_meter)
                    harmony_agent.update_params(loop_size=loop_size, grain=grain, meter=current_meter)
                    percussion_agent.update_params(loop_size=loop_size, grain=grain, meter=current_meter)
                    game_state.structure_dirty = False

                # Live seed update
                if game_state.base_seed != spg.base_seed:
                    spg = SeededPhraseGenerator(base_seed=game_state.base_seed)
                    _spg_prev_seed = spg.seed_state

                # Direct XY Pad coordinate override or fallback to gamevars mapping
                if game_state.x is not None and game_state.y is not None:
                    x, y = clamp(game_state.x, 0.0, 1.0), clamp(game_state.y, 0.0, 1.0)
                else:
                    x, y = map_gamevars_to_xy(game_state.health, game_state.enemies)
            elif game_state_callback is not None:
                try:
                    player_health, enemy_count = game_state_callback()
                except Exception as e:
                    logger.debug(f"Error in game state callback: {e}")
                    player_health, enemy_count = MAX_HEALTH, 0
                x, y = map_gamevars_to_xy(player_health, enemy_count)
            else:
                player_health, enemy_count = MAX_HEALTH, 0
                x, y = map_gamevars_to_xy(player_health, enemy_count)

            # High-precision pacing
            now = running_loop.time()
            sleep_for = next_pulse_time - now
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            elif sleep_for < -0.05:
                logger.warning(f"Warning: Behind schedule by {-sleep_for:.3f} seconds.")
                next_pulse_time = now

            pulse_duration = 60.0 / (tempo * grain)
            next_pulse_time += pulse_duration

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
            # Agent parameter updates
            # ------------------------------------------------------------------
            # Update parameters on the downbeat (subdivision 0) to ensure
            # rhythm and density changes don't happen mid-beat.
            if tick == 0 or phrase_start or (subdivision == 0 and interpolator.smoothing_time > 0):
                melody_agent.update_params(
                    ma_step=max(1, int(round(params.ma_step))),
                    ma_range_low=int(round(params.ma_range_low)),
                    ma_range_high=int(round(params.ma_range_high)),
                    ma_velocity=float(params.ma_velocity),
                    ma_tac=float(params.ma_tac),
                    ma_plus_minus_notes=float(params.ma_plus_minus_notes),
                    ma_mv_even=float(params.ma_mv_even),
                    ma_mv_odd=float(params.ma_mv_odd),
                    ma_trans=int(round(params.ma_trans)),
                    shape_depth=int(round(params.shape_depth)),
                    shape_length=int(round(params.shape_length)),
                )

                orchestrator_agent.update_params(
                    ma_orch_plus_minus=float(params.ma_orch_plus_minus),
                    ha_ins_plus_minus=float(params.ha_ins_plus_minus),
                    ha_register_ins=float(params.ha_register_ins),
                    ma_orch_range_low=int(round(params.ma_orch_range_low)),
                    ma_orch_range_high=int(round(params.ma_orch_range_high)),
                    ha_range_ins_low=int(round(params.ha_range_ins_low)),
                    ha_range_ins_high=int(round(params.ha_range_ins_high)),
                )

                percussion_agent.update_params(
                    pa_vel_perc=float(params.pa_vel_perc),
                    pa_acc_beat_p=float(params.pa_acc_beat_p),
                    pa_ks_plus_minus=float(params.pa_ks_plus_minus),
                    pa_toms_plus_minus=float(params.pa_toms_plus_minus),
                    pa_cymb_plus_minus=float(params.pa_cymb_plus_minus),
                    phrase_length=phrase_length,
                )

                harmony_agent.update_params(
                    tension=float(params.ha_tension),
                    complexity_progression=float(params.ha_cpx_prog),
                    voice_count=max(1, int(round(params.ha_voice_ins))),
                    accent_probability=float(params.ha_acc_beat),
                    add_probability=max(0.0, float(params.ha_plus_minus_notes)) if params.ha_plus_minus_notes > 0 else 0.0,
                    sub_probability=max(0.0, -float(params.ha_plus_minus_notes)) if params.ha_plus_minus_notes < 0 else 0.0,
                    ha_vel_ins=float(params.ha_vel_ins),
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
                await _send_cc_changes(mel_queue)
            elif subdivision == 0:
                await _send_cc_changes(mel_queue)

            # ------------------------------------------------------------------
            # Chord + seed updates
            # ------------------------------------------------------------------
            current_chord = harmony_agent.get_current_chord(
                measure_index=measure_index,
            )

            # On downbeat, update seed and log chord changes.
            if subdivision == 0:
                logger.info(
                    f"Measure {measure_index + 1}/{loop_size} - Chord: {harmony_agent.get_roman_numeral()} "
                    f"{current_chord} (Pool {harmony_agent.get_chord_pool()})",
                )

                new_seed_state = spg.process_chord_change(
                    harmony_agent.get_chord_pool(),
                    phrase_length,
                )
                if new_seed_state != _spg_prev_seed:
                    melody_agent.update_params(
                        seed=new_seed_state.current_seed,
                        rhythm_seed=new_seed_state.rhythm_seed,
                        seed_state=new_seed_state,
                    )
                    percussion_agent.update_params(
                        seed=new_seed_state.current_seed,
                        rhythm_seed=new_seed_state.rhythm_seed,
                        seed_state=new_seed_state,
                    )
                    harmony_agent.update_params(
                        seed=new_seed_state.current_seed,
                        rhythm_seed=new_seed_state.rhythm_seed,
                        seed_state=new_seed_state,
                    )
                    orchestrator_agent.update_params(
                        seed=new_seed_state.current_seed,
                    )
                    _spg_prev_seed = new_seed_state

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
                    current_chord_pcs=harmony_agent.get_chord_pitch_classes(),
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

                note_logger.log_note(
                    measure=loop_index,
                    beat=beat_index,
                    step=subdivision,
                    pulse=tick,
                    agent=hit.get("source", "melody").capitalize(),
                    channel=event.channel,
                    note=event.note,
                    velocity=event.velocity,
                    duration=event.duration,
                    articulation="ratchet" if event.is_ratchet else hit.get("articulation", "normal"),
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

                note_logger.log_note(
                    measure=loop_index,
                    beat=beat_index,
                    step=subdivision,
                    pulse=tick,
                    agent="Percussion",
                    channel=9,
                    note=event.note,
                    velocity=event.velocity,
                    duration=event.duration,
                    articulation="ratchet" if event.is_ratchet else hit.get("articulation", "normal"),
                )

                # Ratcheted drums add extra hits for groove.
                if event.is_ratchet:
                    ratchet_dur = max(event.duration or 0.35, 0.35)
                    task = asyncio.create_task(
                        play_ratchet(
                            perc_queue,
                            event.note,
                            event.velocity,
                            ratchet_dur,
                            subdivisions=event.ratchet_count,
                            channel=event.channel,
                            crescendo=True,
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
            step_in_loop += 1
            if step_in_loop >= total_pulses:
                step_in_loop = 0
                loop_index += 1

            if max_ticks is not None and tick >= max_ticks:
                is_playing = False

    except asyncio.CancelledError:
        logger.info("Clock cancelled by user.")
        raise

    except KeyboardInterrupt:
        logger.info("Clock stopped by user.")

    except (OSError, IOError, ValueError) as e:
        logger.exception(f"MIDI setup/runtime error: {e}")

    except Exception as e:
        logger.exception(f"Clock runtime error: {e}")

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
        finally:
            use_highres_timer("disable")
            note_logger.close()