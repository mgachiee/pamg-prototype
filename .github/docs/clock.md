# Clock and Count Loop

**Module:** `src/core/clock.py`  
**Architecture stage:** Module 1 - Clock and Count Loop  
**Reference:** [PAMG Technical Reference §2](../../docs/technical-reference.md#2-clock-and-count-loop-stage-1)

---

## Overview

The clock is the single authoritative time source for PAMG. It builds the count-loop grid, samples live game-state telemetry (via TCP socket or callback), drives the preset interpolator, orchestrates parameter transitions, and dispatches real-time MIDI events. 

The clock also coordinates phrase boundaries so discrete parameters, shared seeds, acoustic CC staging snapshots, and program changes transition only at musically coherent points.

---

## Architecture Context

```
Game State (TCP Socket / Game Client)
    │
    ▼
map_gamevars_to_xy() -> (x, y)
    │
    ▼
Preset Interpolator -> parameter vectors
    │
    ▼
Clock pulses (count loop: 0 .. loop_size * grain - 1)
    │
    ├─► Melody Agent ──────────────┐
    │                              ▼
    ├─► Harmony Agent ─────────────► Orchestration Agent ──► 8 Orchestral Ch (0-7)
    │                                │
    ├─► Percussion Agent (Direct) ─────────────────────────► Ch 9 Orchestra Kit (48)
    │
    └─► Seeded Phrase Generator (Chord Pool 1 Reseed Gate)
```

---

## Responsibilities

- Build the deterministic timing grid from `tempo`, `loop_size`, and `grain`.
- Sample game-state values (affective valence/arousal, direct XY coordinates, time signatures, tempo) and apply slew-rate interpolation.
- Quantize structural and discrete parameter changes at phrase boundaries.
- Update agent parameters and trigger loop/phrase lifecycle hooks (`on_loop_start`, `on_phrase_start`).
- Update shared seeds on chord pool changes (Chord Pool 1 transition gate).
- Dispatch orchestral MIDI events to output queues (Channels 0–7 for Melody/Harmony, Channel 9 for Percussion).
- **Drum Ratchet Duration Protection**: Enforces minimum roll durations ($\ge 0.35$s–0.45s) for smooth exponential crescendo execution without clock pulse truncation.
- **Acoustic Staging & Program Changes**: Dispatches queued program changes (`consume_program_changes()`) and CC acoustic staging messages (`consume_cc_changes()` for CC64, CC7, CC10, CC91, CC11).
- **Asynchronous Task Lifecycle (`TaskManager`)**: Tracks scheduled note-offs and ratchet timers to prevent dangling async tasks and ensure note-off safety during cancellation.

---

## Task Management (`TaskManager`)

The clock utilizes a `TaskManager` (from `src.core.scheduler`) to manage asynchronous playback coroutines:
* **Registration**: Every scheduled event with a duration (Note On with future Note Off, or multi-stroke ratchet bursts) is registered with the `TaskManager`.
* **Automatic Cleanup**: Done-callbacks automatically discard completed tasks from the active tracking set.
* **Idempotent Cancellation**: During shutdown or pause, `cancel_all_tasks()` cancels pending tasks and issues immediate MIDI `note_off` messages across all channels to avoid hanging notes.

---

## Inputs & Configuration

- `tempo` (BPM), `loop_size` (beats), `grain` (subdivisions per beat): validated strictly `> 0`.
- `game_state`: live `GameState` instance updated via TCP socket for real-time game engine streaming.
- `game_state_callback`: optional fallback callable returning `(health, enemies)`.
- `routing_mode`: MIDI routing strategy (`SINGLE_PORT` or `MULTI_PORT`).
- `sf2_path`: optional path to a SoundFont file (`FluidR3_GM_GS.sf2`) for direct embedded FluidSynth rendering.
- `audio_driver`: optional audio driver override (`wasapi`, `dsound`, `pulseaudio`, `coreaudio`).
- `base_seed`: shared seed base (0 = improvisation mode).

---

## Outputs

- Real-time MIDI events streamed to configured output ports:
  - **Melody & Harmony (Channels 0–7)**: 4 instrument families (Strings, Piano, Woodwinds, Brass).
  - **Percussion (Channel 9)**: General MIDI Orchestra Kit (Program 48).
- Program change pairs dispatched on initialization and phrase boundaries.
- Continuous MIDI CC 11 expression messages dispatched on harmony layer fading.
- Acoustic staging CCs: CC64 (Piano sustain), CC7 (Volume), CC10 (Pan), CC91 (Reverb).

---

## Main Loop Execution Phases

1. **Parameter Validation & State Sync**: Validates tempo/meter values and synchronizes initial state from `game_state`.
2. **Timing Grid Construction**: Computes `total_pulses = loop_size * grain` and `pulse_duration = 60.0 / (tempo * grain)`.
3. **Agent Network Initialization**: Instantiates all agents, SeedState broadcast, and seeded phrase generators.
4. **MIDI & Staging Setup**: Opens ports, starts writer tasks, queues initial program changes (including Ch 9 Orchestra Kit), and applies initial CC staging.
5. **Per-Tick Processing**:
   - Computes tick, beat, and loop offsets.
   - Samples live `game_state` (instantaneous tempo shifts, loop-boundary meter updates, affective XY coordinates).
   - Updates interpolated parameter vectors via `PresetInterpolator`.
   - Dispatches continuous parameters on downbeats and phrase boundaries:
     - `HarmonyAgent`: `ha_vel_ins` (dynamic velocity scaling §3.2, §4.4), `tension`, `complexity_progression`, `voice_count`, `accent_probability`, and calibrated `add_probability` / `sub_probability`.
     - `MelodyAgent`: `ma_velocity` (bounded mean-reverting drunk walk §2.2), `ma_step`, `ma_range_low`/`high`, `ma_mv_even`/`odd`, `ma_trans`, `shape_depth`/`length`.
     - `PercussionAgent`: `pa_vel_perc`, `pa_acc_beat_p`, `pa_ks_plus_minus`, `pa_toms_plus_minus`, `pa_cymb_plus_minus`, `phrase_length`.
     - `OrchestratorAgent`: `ma_orch_plus_minus`, `ha_register_ins`, `ha_ins_plus_minus`, `melody_range`, `harmony_range`.
   - Dispatches melody and harmony events through OrchestratorAgent across Channels 0–7.
   - Dispatches percussion events to Channel 9, applying ratchet duration protection for crescendo rolls (`ratchet_dur = max(event.duration or 0.35, 0.35)`).
   - Polls and sends queued CC expression and acoustic balance changes.
6. **Graceful Shutdown**: Cancels scheduled tasks, sends all-notes-off, stops MIDI queue writers, and closes ports idempotently.

---

## Public API

### `run_clock(...) -> None`
Main coroutine driving the entire PAMG real-time generative network.

### `map_gamevars_to_xy(player_health, enemy_count, max_health, max_enemies) -> Tuple[float, float]`
Utility mapping raw health and enemy game variables to Russell's circumplex $(x, y)$ coordinates.

---

## Dependencies

| Import | Role |
|---|---|
| `src.core.preset_interpolator` | 2D bilinear interpolation and slew rate smoothing |
| `src.core.seeded_phrase_generator` | Dual seed (`SeedState`) phrase motif generation |
| `src.models.game_state` | Real-time TCP game state container |
| `src.modules.*` | Melody, Harmony, Percussion, Orchestration agents |
| `src.core.midi_io` | Port opening, embedded FluidSynth subprocess, and cleanup |
| `src.core.players` | Note, exponential ratchet crescendo, and CC playback |
| `src.core.scheduler` | Asynchronous task tracking |
| `src.utils.audio` | High-resolution multimedia timer (`timeBeginPeriod(1)`) |
