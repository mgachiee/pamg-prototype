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

### Calibrated Corner Presets Reference (`src/core/configs.py`)

| Parameter | Preset A `(0, 0)`<br/>Somber / Ambient | Preset B `(1, 0)`<br/>Calm / Sanctuary | Preset C `(0, 1)`<br/>Danger / Combat | Preset D `(1, 1)`<br/>Heroic / Triumphant |
|---|---|---|---|---|
| **Affect Quadrant** | $-V, -A$ | $+V, -A$ | $-V, +A$ | $+V, +A$ |
| **`ma_velocity`** | 45.0 ($pp$) | 60.0 ($mp$) | 105.0 ($ff$) | 100.0 ($f$) |
| **`ma_orch_plus_minus`** | 0.0 (Solo Strings) | 0.2 (Solo Strings) | 0.8 (Tutti Strings+Winds+Brass) | 1.0 (Full Tutti) |
| **`ha_tension`** | 1.0 (Root triad) | 3.0 (Tertian triad) | 10.0 (Modal borrowed colors) | 5.0 (Diatonic 7th/9th) |
| **`ha_register_ins`** | 1.0 (Piano) | 1.0 (Piano) | 3.0 (Piano+Strings+Winds) | 4.0 (Full Tutti 4 Families) |
| **`ha_ins_plus_minus`** | 0.0 (1 instrument) | 0.2 (Sparse) | 0.8 (Dense Tutti) | 1.0 (Full Ensemble) |
| **`ha_vel_ins`** | 42.0 ($pp$) | 58.0 ($mp$) | 105.0 ($ff$) | 100.0 ($f$) |
| **`pa_vel_perc`** | 35.0 ($pp$) | 48.0 ($p$) | 115.0 ($ff$) | 100.0 ($f$) |
| **`pa_acc_beat_p`** | 0.15 | 0.25 | 0.90 | 0.60 |
| **`pa_ks_plus_minus`** | -0.5 (Downbeat pulse) | -0.2 (Downbeat + side stick) | 0.7 (Driving gran cassa + snare) | 0.5 (Driving heroic groove) |
| **`pa_toms_plus_minus`**| -0.5 (Soft timpani swell) | -0.3 (Gentle timpani prep) | 0.6 (Full timpani rolls) | 0.4 (Timpani cadence) |
| **`pa_cymb_plus_minus`**| -0.6 (Soft cymbal wash) | -0.4 (Ambient touch) | 0.7 (Concert crashes) | 0.5 (Concert crashes) |
| **`seeded_phrase_length`**| 8.0 beats | 6.0 beats | 2.0 beats | 4.0 beats |

---

## Parameter Field Classification

Not every parameter in a `Preset` should be interpolated the same way. The interpolator classifies each `Preset` field into one of four categories:

### 1. Continuous (default)
All baseline PAMG parameters (§3.5, §4.5, §5.4) are continuous numeric fields that change smoothly across the XY pad:
- **Melody Agent:** `ma_step`, `ma_range_low`, `ma_range_high`, `ma_velocity`, `ma_tac`, `ma_plus_minus_notes`, `ma_mv_even`, `ma_mv_odd`, `ma_orch_plus_minus`, `ma_orch_range_low`, `ma_orch_range_high`, `ma_trans`
- **Harmony Agent:** `ha_tension`, `ha_cpx_prog`, `ha_plus_minus_notes`, `ha_acc_beat`, `ha_vel_ins`, `ha_voice_ins`, `ha_range_ins_low`, `ha_range_ins_high`, `ha_register_ins`, `ha_ins_plus_minus`, `ha_move`
- **Percussion Agent:** `pa_vel_perc`, `pa_acc_beat_p`, `pa_ks_plus_minus`, `pa_toms_plus_minus`, `pa_cymb_plus_minus`
- **Shared:** `seeded_phrase_length`, `shape_depth`, `shape_length`

- **Blend:** weighted sum across the four corner values.
- **Smooth:** one lerp step toward the blended target every pulse.

### 2. Quantized State at Phrase Boundaries
`get_quantized_state(phrase_start)` snapshots the interpolated parameter state on phrase boundaries, ensuring macro structure transitions land on bar boundaries.

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