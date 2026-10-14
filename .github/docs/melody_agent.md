# Melody Agent

**Module:** `src/modules/melody_agent.py`  
**Architecture stage:** Module 2 - Melody Agent  
**Reference:** [PAMG Technical Reference §3](../../docs/technical-reference.md#3-melody-agent-ma--2x)

---

## Overview

The Melody Agent generates the lead melodic line. It builds rhythmic onset patterns across the Count Loop, records syncopation displacements in a **Moved List**, shapes velocities using a random walk with accent boosts, selects pitches using `drunk` or `drunk_contour` modes, filters raw pitches through the active Harmony pitch-class set, and classifies note durations as Staccato or Legato based on inter-onset spacing.

---

## Architecture Context

```
Clock pulse ───► Melody Agent ───► melody events ───► Orchestration Agent
                      │
                      ├─► accent list ───────────────► Harmony / Percussion Agents
                      │
Current chord ◄───────┴─────────────────────────────── Harmony Agent
```

---

## Core Algorithms

### 1. Rhythm Generation & Moved List (§3.1)
- **Beat and Moved List (`2.1.1`)**: Builds base onsets on metric beats; syncopated/displaced onsets are recorded in `self._moved_list`.
- **Add/Sub Filling (`2.1.2`)**: Subdivides and thins the grid according to `add_probability` and `sub_probability`.
- Accent list is shared with Harmony and Percussion agents to coordinate rhythmic emphasis.

### 2. Computed Staccato / Legato Articulation (§3.2)
Note articulation is classified from the inter-onset distance after rhythm generation completes:
$$\text{gap} = \text{distance\_to\_next\_onset}(\text{onset})$$
$$\text{articulation} = \begin{cases} \text{STACCATO} & \text{if } \text{gap} \le \text{threshold} \\ \text{LEGATO} & \text{otherwise} \end{cases}$$
Where $\text{threshold} = \max(1, \text{grain} // 2)$. Rapid onsets sound staccato ($0.50 \times \text{base}$), while spaced onsets sound legato ($1.05 \times \text{base}$).

### 3. Pitch Generation (`2.3`) & Harmony Filter (`2.3.3`)
- **Note Stream Generation**: Random-walk step size within `pitch_range` in `drunk` mode. In `dcontour` mode, Moved List onsets and loop boundaries act as contour anchor nodes whose pitches are generated via drunk walk, while intermediate onsets are explicitly interpolated between anchor nodes (§2.3.1, §3.3).
- **Harmony Filter**: Snaps raw pitches to the nearest active pitch class provided by the Harmony Agent (`current_chord`). In strict compliance with §6.1, local pitch clamping does *not* occur prior to the Harmony Filter; the filtered stream feeds OrchestratorAgent directly, which is solely responsible for instrument range clamping.
- **Shape Melody (`2.4`)**: Applies macro directional pitch drift using `shape_depth` and `shape_length`.

### 4. Velocity Generation (`2.2`)
- **Mean-Reverting Drunk Walk**: Operates via a bounded random walk with a mean-reverting pull towards `ma_velocity` (`pull = (base_vel - current_vel) * 0.35`).
- **Dynamic Proportional Scaling**: Syncopation and metric accent boosts are scaled proportionally to the preset dynamic level (`dynamic_scale = max(0.3, min(1.2, base_vel / 80.0))`), ensuring quiet presets ($pp \approx 45$) stay softly bounded while heroic presets ($ff \ge 100$) achieve authoritative dynamic presence.

---

## Public API

### `__init__(movement, loop_size, grain, max_step=4, ...)`
Initializes the agent, rhythm generators, and pitch constraints.

### `process_tick(index, current_chord, pulse_duration) -> List[dict]`
Generates melody events for the given clock tick.

### `get_accent_list() -> List[int]`
Returns the list of metric accent beats for the current loop.

### `on_loop_start(loop_index) -> None`
Rebuilds the onset pattern and Moved List for the new loop, updating `dcontour` nodes.

### `on_phrase_start() -> None`
Advances macro phrase transposition contour.

### `update_params(**kwargs) -> bool`
Updates runtime parameters, including baseline parameters (`ma_step`, `ma_range_low`, `ma_range_high`, `ma_velocity`, `ma_tac`, `ma_plus_minus_notes`, `ma_mv_even`, `ma_mv_odd`, `ma_trans`, `shape_depth`, `shape_length`).

---

## Dependencies

| Import | Role |
|---|---|
| `random.Random` | Stochastic rhythm, pitch, and velocity RNG |
| `logging` | Pitch filtering and decision diagnostics |
