# Melody Agent

**Module:** `modules/melody_agent.py`  
**Architecture stage:** Module 2 - Melody Agent

---

## Overview

The Melody Agent generates the lead melodic line. It builds rhythmic onset
patterns, shapes velocity with a random walk, selects pitches using a stochastic
step model, and snaps pitches to the current harmony for musical coherence.

---

## Architecture Context

```
Clock pulse -> Melody Agent
    |           |
    |           +-> accent list -> Harmony / Percussion
    |
Current chord <---------------- Harmony Agent
```

See `system-architecture.md` for the high-level agent flow.

---

## Responsibilities

- Generate onset patterns with add/sub and syncopation rules.
- Maintain an accent list shared with Harmony and Percussion agents.
- Create velocity values via random walk and accent boosts.
- Produce melodic pitches using a step-based random process.
- Snap pitches to the current chord (harmony filter).
- Emit MIDI-ready event dictionaries per clock tick.

---

## Inputs

- Loop configuration: `loop_size`, `grain`.
- Runtime chord context: `current_chord` from Harmony Agent.
- Parameters: `max_step`, `syncopation_probability`, `accent_probability`,
  `ratchet_probability`, `pitch_range`, `drunk_mode`.
- Optional seed for reproducibility.

## Outputs

- A list of event dicts with `note`, `velocity`, `duration`, `channel`, and
  optional ratchet fields.
- A sorted list of accent beats via `get_accent_list()`.

---

## Public API

### `__init__(...)`

Configures the melody generator, including movement bias and pitch mode.

### `process_tick(index, current_chord, pulse_duration) -> List[dict]`

Generates all melody events for a single clock tick.

### `update_params(**kwargs) -> bool`

Updates runtime parameters such as step size, probabilities, and ranges.

### `on_loop_start(loop_index) -> None`

Refreshes onset and accent patterns at loop boundaries.

### `on_phrase_start() -> None`

Advances the long-term transposition contour at phrase boundaries.

### `get_accent_list() -> List[int]`

Returns a sorted list of accent beats for coordination with other agents.

---

## Usage Pattern

```python
melody_agent = MelodyAgent(movement="odd", loop_size=4, grain=2)
melody_agent.update_params(max_step=4, syncopation_probability=0.3)

melody_hits = melody_agent.process_tick(
    index=local_index,
    current_chord=current_chord,
    pulse_duration=pulse_duration,
)
```

---

## Dependencies

| Import | Role |
|---|---|
| `random.Random` | Stochastic rhythm, pitch, and velocity decisions |
| `logging` | Debug tracing for pitch decisions |
