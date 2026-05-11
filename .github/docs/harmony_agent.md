# Harmony Agent

**Module:** `modules/harmony_agent.py`  
**Architecture stage:** Module 3 - Harmony Agent

---

## Overview

The Harmony Agent generates chord progressions and harmony events. It selects a
progression based on tension and chord complexity, builds chord tones, and
emits chord or arpeggio events aligned to the clock grid. The agent also
publishes the current chord pool so the seeded phrase generator can gate seed
updates.

---

## Architecture Context

```
Clock pulse -> Harmony Agent -> harmony events
                     |
                     +-> current chord pool -> Seeded Phrase Generator
                     |
                     +-> current chord -> Melody Agent filter
```

See `system-architecture.md` for chord pool and progression flow.

---

## Responsibilities

- Maintain a chord progression and update it at loop boundaries.
- Generate chord tones with tension and complexity rules.
- Build arpeggio events when complexity or tension is high.
- Apply post-filter pitch subsets for rapid harmonic changes.
- Emit harmony events per tick and expose the current chord pool.

---

## Inputs

- Loop configuration: `loop_size`, `grain`, optional `meter`.
- Harmonic context: `key_root`, `scale_mode`.
- Parameters: `tension`, `chord_complexity`, `chord_change_probability`,
  add/sub probabilities, accent probabilities.
- Accent beats from the Melody Agent.

## Outputs

- A list of harmony event dicts per tick.
- The current chord list via `get_current_chord()`.
- The current chord pool via `get_chord_pool()`.

---

## Public API

### `get_current_chord(measure_index) -> List[int]`

Returns the current chord for the active measure.

### `process_tick(index, pulse_duration) -> List[dict]`

Generates harmony events for a single tick.

### `get_chord_pool() -> int`

Returns the current chord pool identifier (Pool 1 gates seed updates).

### `notify_accents(accent_beats) -> None`

Receives accent beats from the Melody Agent.

### `set_post_filter(pitch_subset) -> None`

Restricts chord output to a pitch subset for rapid harmonic switches.

### `update_params(**kwargs) -> bool`

Updates harmonic parameters and returns whether anything changed.

---

## Usage Pattern

```python
harmony_agent = HarmonyAgent(loop_size=4, grain=2, key_root=60)
harmony_agent.update_params(tension=0.5, chord_complexity=0.7)

current_chord = harmony_agent.get_current_chord(measure_index)
harmony_hits = harmony_agent.process_tick(local_index, pulse_duration)
```

---

## Dependencies

| Import | Role |
|---|---|
| `src.core.configs.HARMONY_TEMPLATE` | Beat templates for chord and accent patterns |
| `random.Random` | Progression selection and stochastic decisions |
