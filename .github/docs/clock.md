# Clock and Count Loop

**Module:** `core/clock.py`  
**Architecture stage:** Module 1 - Clock and Count Loop

---

## Overview

The clock is the single authoritative time source for PAMG. It builds the
count-loop grid, samples game-state input, drives the preset interpolator,
updates all agent parameters, and dispatches MIDI events in real time. The
clock also coordinates phrase boundaries so discrete parameters and shared
seeds change only at musically meaningful points.

---

## Architecture Context

```
Game state / UI
    |
    v
map_gamevars_to_xy() -> (x, y)
    |
    v
Preset Interpolator -> parameter vectors
    |
    v
Clock pulses (count loop)
    |
    +-> Melody Agent
    +-> Harmony Agent -----> Chord Pool -> Seeded Phrase Generator
    +-> Percussion Agent
    +-> Orchestrator Agent
    |
    v
MIDI ports
```

See `system-architecture.md` for the end-to-end data flow and constraints.

---

## Responsibilities

- Build the timing grid from tempo, loop size, and grain.
- Sample game-state values and map them into XY inputs.
- Interpolate continuous parameters every pulse.
- Quantize discrete parameter changes at phrase boundaries.
- Update agent parameters and trigger loop/phrase hooks.
- Update shared seeds on chord pool changes (Pool 1 gate).
- Dispatch MIDI events to output ports via async writers.
- Ensure clean shutdown and flush of pending note tasks.

---

## Inputs

- `tempo`, `loop_size`, `grain`: define the count loop.
- `game_state_callback`: returns `(health, enemies)` when provided.
- `routing_mode`, `single_port_name`, `melody_port_name`, `drum_port_name`:
  MIDI routing configuration.
- `base_seed`: shared seed base (0 = improvisation mode).

## Outputs

- Real-time MIDI events streamed to configured output ports.
- Log messages for timing and event tracing when `debug_midi` is enabled.

---

## Main Loop Phases

1. **Timing grid** - compute `total_pulses` and `pulse_duration`.
2. **Agent network** - initialize all agents and seeded phrase generator.
3. **MIDI setup** - open ports, start writer tasks, send program changes.
4. **Per-tick processing**
   - sleep to scheduled tick
   - compute loop indices
   - sample game state and interpolate parameters
   - update agents and apply phrase/loop hooks
   - update seeds and chord pool state
   - generate events and dispatch MIDI
5. **Shutdown** - await pending note tasks, stop writers, close ports.

---

## Public API

### `run_clock(...) -> None`

Runs the real-time clock loop and drives all agents. This coroutine should be
started in an asyncio event loop.

### `map_gamevars_to_xy(...) -> Tuple[float, float]`

Maps raw game values into normalized `(x, y)` coordinates for the interpolator.

---

## Usage Pattern (Scheduler Integration)

```python
asyncio.run(
    run_clock(
        tempo=120,
        loop_size=6,
        grain=2,
        routing_mode=ROUTING_MODE,
        base_seed=42,
        game_state_callback=demo_game_state,
    )
)
```

---

## Dependencies

| Import | Role |
|---|---|
| `src.core.preset_interpolator` | Continuous and quantized parameter updates |
| `src.core.seeded_phrase_generator` | Seed management at chord pool changes |
| `src.modules.*` | Melody, Harmony, Percussion, Orchestration agents |
| `src.core.midi_io` | Port opening and cleanup |
| `src.core.players` | Note and ratchet playback |
| `src.core.midi_events` | Event normalization |
| `src.core.scheduler` | Task tracking during playback |
