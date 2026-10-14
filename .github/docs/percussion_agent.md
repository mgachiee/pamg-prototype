# Percussion Agent

**Module:** `src/modules/percussion_agent.py`  
**Architecture stage:** Module 4 - Percussion Agent  
**Reference:** [PAMG Technical Reference §5](../../docs/technical-reference.md#5-percussion-agent-pa--4x)

---

## Overview

The Percussion Agent generates cinematic, orchestral percussion patterns independently of the Orchestration Agent, routing events directly to the MIDI engine on Channel 9 (configured for the General MIDI Orchestra Kit, Bank 128, Program 48). 

It constructs a complete per-voice onset grid across the Count Loop index, coordinates anticipatory ghost notes and fills against scheduled base hits, triggers phrase fills on verified transitions into Chord Pool #1, shapes authentic exponential crescendo drum rolls, and applies stochastic Add/Sub Filling to preserve delicate acoustic textures in low-tension states.

---

## Architecture Context

```
Clock pulse ───► Percussion Agent ───► drum events (Ch 9) ───► MIDI Port / FluidSynth (Direct)
                      │
                      ├─► accent list ◄────────────── Melody Agent
                      │
                      └─► chord pool transitions ◄─── Harmony Agent (Pool 1 Gate)
```

In strict alignment with Technical Reference §5.3, **percussion instrument management is architecturally self-contained**: it does not pass through Orchestration Agent instrument-switching, range-management, or voice-assignment machinery.

---

## General MIDI Orchestra Kit Mapping (Bank 128, Program 48)

To achieve an authentic cinematic orchestral sound rather than a pop/rock drum kit, the agent routes directly to Channel 9 using the General MIDI Orchestra Kit:

| Baseline Row (§2.1) | Note Number | GM Orchestra Kit Instrument | Musical Role |
|---|---|---|---|
| **Row 1: Kick** | **36** | **Gran Cassa (Concert Bass Drum)** | Resonant downbeat structural anchor pulse |
| **Row 2: Snare** | **38** | **Concert Snare** | Half-time cadence punctuation (when `pa_vel_perc >= 60`) |
| | **40** | **Concert Snare Roll** | Orchestral crescendo snare swell on phrase boundaries |
| | **37** | **Side Stick / Rimshot** | Delicate wood clicks on half-time cadences (`pa_vel_perc < 60` or `ks_delta < 0`) |
| **Row 3: Toms** | **45** | **Timpani A** | Pitched orchestral timpani downbeat preparation |
| | **48** | **Timpani c** | Intermediate timpani melodic movement |
| | **50** | **Timpani d** | High timpani melodic movement and rolls |
| **Row 4: Cymbals** | **42** | **Closed / Suspended Cymbal** | Ambient phrase entrance and subtle cymbal washes |
| | **57** | **Concert Cymbal 2 (Crash)** | Dramatic phrase climax punctuation |

---

## Core Algorithms (§5.1, §5.2)

### 1. Rhythm Generation & Orchestral Phrasing (`_plan_loop`)
* Reconstructs the full onset grid per loop across `0..total_pulses-1`.
* **Removal of the Rock Backbeat**: The standard pop/rock 2-and-4 backbeat is eliminated in [`PERCUSSION_TEMPLATE`](../core/configs.py). The template focuses on:
  * **Beat 0 (Kick / Gran Cassa)**: Downbeat anchor pulse.
  * **Beat 2 (Snare / Side Stick)**: Half-time orchestral cadence punctuation.
  * **Beat 3 (Toms / Timpani)**: Preparation roll leading into the subsequent measure's downbeat.
  * **Beat 0 (Cymbal)**: Phrase entrance accent.
* Driven by baseline GUI controls:
  * `pa_ks_plus_minus`: Combined Kick/Snare density control.
  * `pa_toms_plus_minus`: Toms (Timpani) density control.
  * `pa_cymb_plus_minus`: Cymbals density control.
  * `pa_vel_perc`: Base percussion velocity scaling.
  * `pa_acc_beat_p`: Accent / beat follower probability.

### 2. Crescendo Drum Rolls & Duration Protection
* **Exponential Velocity Swell**: In [`src/core/players.py`](../core/players.py), [`play_ratchet`](../core/players.py) computes stroke velocity using an exponential crescendo curve:
  $$\text{factor} = 0.30 + 0.70 \times \left(\frac{i}{\text{subdivisions} - 1}\right)^{1.2}$$
  Strokes start softly at 30% velocity ($p$ / piano) and smoothly ramp up to 100% ($f$ / forte) on the final hit.
* **Extended Duration**: Drum rolls are given `duration = 0.45s` with `ratchet_count = 6`. In [`src/core/clock.py`](../core/clock.py), drum dispatch enforces `ratchet_dur = max(event.duration or 0.35, 0.35)` to prevent short 16th-note clock pulses from compressing rolls into inaudible 18ms clicks.

### 3. Dynamic Articulation & Low-Tension Dynamics
* **Organic Side Stick Substitution**: When `pa_vel_perc < 60.0` or `ks_delta < 0`, the agent automatically selects [`SIDE_STICK`](#general-midi-orchestra-kit-mapping-bank-128-program-48) (Note 37) instead of the loud Concert Snare (Note 38).
* **Add/Sub Filling Stochastic Subtraction (§4.1.2)**: Negative delta parameters trigger calibrated stochastic subtraction and phrase-aligned gating:
  * **Kick downbeats**: In deep ambient states (`ks_delta < -0.3`), pulses on phrase starts or even measures as a gentle anchor with `kick_sub = max(0.0, -ks_delta * 0.5)`.
  * **Snare cadences**: When `ks_delta < 0`, mid-measure pop backbeats are gated off, reserving side-stick strikes for phrase cadences (`self._phrase_end`).
  * **Timpani preparation**: When `tom_delta < 0`, routine beat 3 hits are gated off, sounding only on phrase boundaries.
  * **Cymbals**: When `cymb_delta < 0`, cymbal strikes are restricted to phrase entrances (`self._phrase_start`).
  This guarantees that low-tension presets (Preset A & B) maintain subtle, breathing acoustic textures without continuous mid-measure kit clatter.

### 4. Anticipatory Fills & Chord Pool #1 Phrase Gating
* Precomputes tom fills and ratchet rolls on the final beat or at phrase boundaries.
* `notify_chord_change(chord_pool)` checks for transitions into Chord Pool 1 from another pool to arm phrase-ending fills.

---

## Public API

### `__init__(loop_size, grain, meter=None, seed=0, phrase_length=4)`
Initializes the percussion agent with loop dimensions, seed, and phrase length. Sets default General MIDI Orchestra Kit constants.

### `process_tick(index) -> List[dict]`
Emits scheduled drum events for the given tick index from the precomputed grid. All events specify `channel = 9`.

### `on_loop_start(loop_index) -> None`
Recomputes the complete per-voice onset grid and fill plans for the new loop.

### `notify_chord_change(chord_pool) -> None`
Arms phrase fills when transitioning into Chord Pool 1 from a different pool.

### `notify_accents(accent_beats) -> None`
Aligns percussion groove accents with melody accents.

### `update_params(**kwargs) -> bool`
Updates runtime parameters (`pa_ks_plus_minus`, `pa_toms_plus_minus`, `pa_cymb_plus_minus`, `pa_vel_perc`, `pa_acc_beat_p`, `phrase_length`).

---

## Dependencies

| Import | Role |
|---|---|
| `src.core.configs.PERCUSSION_TEMPLATE` | Metric beat templates for orchestral groove generation |
| `src.core.configs.PERCUSSION_PROGRAM` | MIDI program 48 (Orchestra Kit) |
| `random.Random` | Deterministic stochastic decisions |
