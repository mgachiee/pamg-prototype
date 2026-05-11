# Multi-Parameter Preset Interpolator

**Module:** `core/preset_interpolator.py`  
**Architecture stage:** Stage 1 — Global Control & Parameter Input

---

## Overview

The `MultiParameterPresetInterpolator` is the parameter bridge between external control signals (game variables, composer UI, XY pad hardware) and the PAMG Agent Network. It translates a single continuous 2D position `(x, y)` into a fully blended `Preset` object that agents consume to drive their musical behaviour.

It is responsible for two concerns that must be kept separate for musical coherence:

| Concern | Mechanism |
|---|---|
| **Spatial blending** — *what* the target parameter values are | Bilinear interpolation across four corner presets |
| **Temporal smoothing** — *how fast* the state moves toward the target | Exponential-lag filter applied every clock pulse |

---

## Architecture Context

```
External game variables / composer UI
         │
         ▼
 MultiParameterPresetInterpolator   ◄─── four corner Presets (A, B, C, D)
         │
         ├─► continuous parameter vectors  ──► Harmony / Melody / Percussion / Orchestration Agents
         │         (every clock pulse)
         │
         └─► quantized discrete changes   ──► Agents
                   (phrase boundaries only)
```

See `system_architecture.md § Stage 1` for the broader data-flow picture.

---

## XY Pad Interpolation Model

Four composer-defined `Preset` objects occupy the corners of a unit square. Any point `(x, y)` inside the square produces a **bilinear blend** of all four presets.

```
(x=0, y=1)  C ──────────── D  (x=1, y=1)
            │              │
            │    XY pad    │
            │              │
(x=0, y=0)  A ──────────── B  (x=1, y=0)
```

### Bilinear Weights

```
w_A = (1 - x)(1 - y)
w_B =  x     (1 - y)
w_C = (1 - x)  y
w_D =  x       y
```

The four weights always sum to **1.0**, so the blend is a convex combination — values can never exceed the range spanned by the four presets.

---

## Parameter Field Classification

Not every parameter in a `Preset` should be interpolated the same way. The interpolator classifies each `Preset` field into one of four categories:

### 1. Continuous (default)
Scalar numeric fields that change smoothly (e.g. `tempo_offset`, `density`, `filter_cutoff`).

- **Blend:** weighted sum across the four corner values.
- **Smooth:** one lerp step toward the blended target every pulse.

### 2. Discrete (`_DISCRETE_FIELDS`)
Scalar parameters that must not take intermediate values (e.g. `melody_program`, `harmony_layer_mode`).

```python
_DISCRETE_FIELDS = {"melody_program", "harmony_layer_mode"}
```

- **Blend:** winner-take-all — the preset with the highest bilinear weight is selected.
- **Smooth:** no smoothing; changes are deferred to phrase boundaries via `get_quantized_state()`.

### 3. List-Interpolated (`_LIST_INTERPOLATED_FIELDS`)
Lists of floats that are safe to blend continuously (e.g. `harmony_layer_weights`).

```python
_LIST_INTERPOLATED_FIELDS = {"harmony_layer_weights"}
```

- **Blend:** element-wise weighted sum; shorter lists are padded with their last value (fill = `1.0` for weights).
- **Smooth:** element-wise lerp toward the blended target list every pulse.

### 4. List-Discrete (`_LIST_DISCRETE_FIELDS`)
Lists of discrete values (e.g. `harmony_programs` — a list of MIDI program numbers per harmony layer).

```python
_LIST_DISCRETE_FIELDS = {"harmony_programs"}
```

- **Blend:** winner-take-all per list (the entire list from the dominant preset is selected).
- **Smooth:** no smoothing; deferred to phrase boundaries.

---

## Smoothing Model

Every call to `update()` moves the running internal state one step toward the blended target using an **exponential-lag (one-pole IIR) filter**:

```
α     = 1 − exp(−Δt / τ)
state ← lerp(state, target, α)
```

| Symbol | Meaning |
|---|---|
| `Δt` | `pulse_duration` — wall-clock length of the current pulse (seconds) |
| `τ` | `smoothing_time` — the time constant; set at construction |
| `α` | Smoothing factor ∈ (0, 1]; larger = faster tracking |

**Effect of `smoothing_time`:**

| `smoothing_time` | Behaviour |
|---|---|
| Very small (e.g. 0.05 s) | Tight tracking; almost instant parameter changes |
| Medium (default: 0.25 s) | Smooth but responsive transitions |
| Large (e.g. 2.0 s) | Heavy inertia; slow drift between presets |

After one `smoothing_time` elapses, a step change reaches approximately **63 %** of its final value; after three `smoothing_time`s it reaches ~**95 %**.

---

## Phrase-Boundary Quantization

Discrete parameters (instrument programs, layer modes) must not change mid-phrase — doing so causes audible timbral jumps or MIDI re-triggers that break musical form.

The interpolator handles this with a two-stage approach:

1. **Every pulse:** `update()` stores the current winning discrete values in `_pending_discrete`. The running `_state` continues to reflect the *previous* discrete choice.
2. **At phrase boundaries:** the scheduler calls `get_quantized_state(phrase_start=True)`, which returns a snapshot that splices `_pending_discrete` into the otherwise-smoothed `_state`.

```
Clock pulse N (mid-phrase):
    update() → _state updated (continuous only) → broadcast to agents

Clock pulse M (phrase start):
    update() → _state updated
    get_quantized_state(phrase_start=True)
        → merges _pending_discrete into snapshot
        → broadcast discrete change to agents
```

---

## Public API

### `__init__(a, b, c, d, smoothing_time=0.25)`

Initialise with four corner presets and an optional smoothing time constant.

```python
interpolator = MultiParameterPresetInterpolator(
    a=preset_calm_sparse,
    b=preset_tense_sparse,
    c=preset_calm_full,
    d=preset_tense_full,
    smoothing_time=0.4,
)
```

---

### `update(x, y, pulse_duration) → Preset`

Advance the interpolator by one clock pulse.

| Arg | Type | Description |
|---|---|---|
| `x` | `float` | Horizontal XY-pad position `[0, 1]` |
| `y` | `float` | Vertical XY-pad position `[0, 1]` |
| `pulse_duration` | `float` | Duration of this pulse in seconds |

Returns a deep copy of the current smoothed state. Suitable for broadcasting to agents as continuous parameter vectors.

---

### `get_quantized_state(phrase_start=False) → Preset | None`

Return the current state with pending discrete changes applied, but only when `phrase_start=True`.

Returns `None` on non-phrase-start pulses, signalling to the caller that no discrete update should be dispatched.

---

## Usage Pattern (Scheduler Integration)

```python
# core/scheduler.py — called once per clock pulse

def on_pulse(x: float, y: float, pulse_dt: float, is_phrase_start: bool):
    # 1. Advance the interpolator and get continuous parameters.
    continuous_params = interpolator.update(x, y, pulse_dt)
    agents.apply_continuous_params(continuous_params)

    # 2. At phrase boundaries, also apply pending discrete changes.
    if is_phrase_start:
        quantized = interpolator.get_quantized_state(phrase_start=True)
        if quantized is not None:
            agents.apply_discrete_params(quantized)
```

---

## Internal Methods — Quick Reference

| Method | Purpose |
|---|---|
| `_blend(x, y)` | Compute bilinear weights and return blended target Preset |
| `_alpha_from_pulse(dt)` | Convert pulse duration → smoothing factor α |
| `_blend_value(name, weights)` | Dispatch correct blend strategy for one field |
| `_smooth_value(name, cur, tgt, α)` | Dispatch correct smooth strategy for one field |
| `_select_discrete(values, weights)` | Winner-take-all for discrete fields |
| `_blend_list(name, weights, values)` | Element-wise bilinear blend of four float lists |
| `_lerp_list(name, cur, tgt, t)` | Element-wise lerp between two float lists |
| `_pad_list(values, length, fill)` | Pad/truncate a list; repeat last element |
| `_list_fill_value(name)` | Return the neutral fill value (0.0 or 1.0) for a list field |
| `_copy_preset(preset)` | Deep-copy a Preset (copies list fields) |
| `_copy_if_list(value)` | Shallow-copy a value only if it is a list |

---

## Dependencies

| Import | Role |
|---|---|
| `src.models.preset.Preset` | Dataclass that holds all agent-controlling parameters |
| `src.core.logger.Logger` | Internal structured logger; debug logs blend weights |
| `dataclasses.fields` | Introspects `Preset` field names for generic iteration |
| `math.exp` | Exponential function used in the smoothing filter |