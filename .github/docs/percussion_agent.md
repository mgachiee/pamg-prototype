# Percussion Agent

**Module:** `modules/percussion_agent.py`  
**Architecture stage:** Module 4 - Percussion Agent

---

## Overview

The Percussion Agent generates drum patterns independently of the orchestration
layer. It uses beat templates, accent cues, and stochastic add/sub rules to
produce kick, snare, hat, and fill events. It also aligns fills to chord pool
changes to preserve phrase structure.

---

## Architecture Context

```
Clock pulse -> Percussion Agent -> percussion events -> MIDI port
                    |
                    +-> accent list (from Melody Agent)
                    +-> chord pool changes (from Harmony Agent)
```

See `system-architecture.md` for the percussion flow and constraints.

---

## Responsibilities

- Build per-instrument rhythm patterns using templates and probabilities.
- Apply accent and syncopation rules for groove variation.
- Precompute fill plans at loop boundaries.
- Trigger phrase fills on chord pool transitions.
- Emit drum events directly to the MIDI output.

---

## Inputs

- Loop configuration: `loop_size`, `grain`, optional `meter`.
- Parameters: kick/snare/hat probabilities, ratchet probabilities, fill
  probabilities, and density values.
- Accent beats from the Melody Agent.
- Chord pool changes from the Harmony Agent.

## Outputs

- A list of percussion event dicts per tick.

---

## Public API

### `process_tick(index) -> List[dict]`

Generates percussion events for a single tick.

### `update_params(**kwargs) -> bool`

Updates runtime probabilities and density settings.

### `on_loop_start(loop_index) -> None`

Refreshes loop-level fill plans and internal counters.

### `notify_accents(accent_beats) -> None`

Receives accent beats from the Melody Agent.

### `notify_chord_change(chord_pool) -> None`

Flags phrase fills when the harmony returns to Pool 1.

---

## Usage Pattern

```python
perc_agent = PercussionAgent(loop_size=4, grain=2)
perc_agent.update_params(kick_add_prob=0.1, snare_sub_prob=0.05)

perc_hits = perc_agent.process_tick(local_index)
```

---

## Dependencies

| Import | Role |
|---|---|
| `src.core.configs.PERCUSSION_TEMPLATE` | Beat templates for groove generation |
| `random.Random` | Stochastic rhythm and fill decisions |
