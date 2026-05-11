# Orchestration Agent

**Module:** `modules/orchestrator_agent.py`  
**Architecture stage:** Module 5 - Orchestration Agent

---

## Overview

The Orchestration Agent merges melody and harmony events, assigns channels,
clamps notes to instrument ranges, and manages program changes. It does not
generate rhythm; it post-processes events produced by the Melody and Harmony
agents.

---

## Architecture Context

```
Melody events  ---->
                     Orchestration Agent -> merged events -> MIDI port
Harmony events ---->
```

See `system-architecture.md` for orchestration responsibilities.

---

## Responsibilities

- Merge melody and harmony event streams.
- Assign MIDI channels for each layer.
- Clamp notes to configured pitch ranges.
- Manage program changes at phrase boundaries.
- Apply layer weights and optional layer masks.

---

## Inputs

- Melody and harmony event lists per tick.
- Parameters: channel assignments, layer weights, layer mode, program lists,
  and range constraints.

## Outputs

- A combined list of event dicts ready for MIDI dispatch.
- Program change pairs via `consume_program_changes()`.

---

## Public API

### `process_tick(melody_events, harmony_events) -> List[dict]`

Returns merged, range-safe event dictionaries for the current tick.

### `update_params(**kwargs) -> bool`

Updates orchestration parameters and queues program changes when needed.

### `consume_program_changes() -> List[Tuple[int, int]]`

Returns queued `(channel, program)` pairs and clears the queue.

### `on_phrase_start() -> None`

Forces a program-change snapshot at phrase boundaries.

---

## Usage Pattern

```python
orchestrator = OrchestratorAgent(melody_channel=1, harmony_channels=[2, 3])
merged = orchestrator.process_tick(melody_hits, harmony_hits)

for channel, program in orchestrator.consume_program_changes():
    send_program_change(channel, program)
```

---

## Dependencies

| Import | Role |
|---|---|
| `random.Random` | Probabilistic layer selection when enabled |
| `itertools.zip_longest` | Align channel and program lists |
