# Orchestration Agent

**Module:** `src/modules/orchestrator_agent.py`  
**Architecture stage:** Module 5 - Orchestration Agent  
**Reference:** [PAMG Technical Reference §6](../../docs/technical-reference.md#6-orchestration-agent-oa--5x)

---

## Overview

The Orchestration Agent acts as the digital master orchestrator of PAMG. It merges melody and harmony event streams, manages the **4x2 Dynamic Orchestral Matrix across 8 MIDI channels**, applies instrumental family range constraints with octave transposition, handles dynamic doubling and registration tiers, and manages concert hall acoustic staging (CC64 Sustain, CC7 Volume, CC10 Pan, CC91 Reverb, CC11 Expression) and program change routing.

---

## Architecture Context

```
Melody events (MA)  ─────┐
                         ▼
Harmony events (HA) ─────► Orchestration Agent ───► 8 Orchestral MIDI Channels (0-7) ──► MIDI Port / FluidSynth
                                │
                                ├─► Program Changes: [(0, 48), (1, 0) ... (9, 48)]
                                └─► Acoustic Staging CCs: CC64, CC7, CC10, CC91, CC11
```

---

## 4x2 Dynamic Orchestral Matrix (§6.2)

The system models four core orchestral instrument families across two parallel streams (Melody and Harmony), matching standard professional DAW multi-track templates (e.g., REAPER Tracks 1–8) plus Percussion on Channel 9:

| Channel | Stream | Family | GM Program | Default Patch Name |
|---|---|---|---|---|
| **Ch 0** | Melody | Strings | **48** | String Ensemble 1 |
| **Ch 1** | Melody | Piano | **0** | Acoustic Grand Piano |
| **Ch 2** | Melody | Woodwinds | **73** | Flute |
| **Ch 3** | Melody | Brass | **61** | Brass Section |
| **Ch 4** | Harmony | Strings | **48** | String Ensemble 1 |
| **Ch 5** | Harmony | Piano | **0** | Acoustic Grand Piano |
| **Ch 6** | Harmony | Woodwinds | **73** | Flute |
| **Ch 7** | Harmony | Brass | **61** | Brass Section |
| **Ch 9** | Percussion | Orchestra Kit | **48** | General MIDI Orchestra Kit (Bank 128) |

---

## Instrument Addition / Subtraction (§5.1.1, §5.1.2)

### 1. Melody Doubling Tiers (`ma_orch_plus_minus`)
Melody orchestration dynamically expands based on `ma_orch_plus_minus` ($\in [0.0, 1.0]$):
* **$\text{val} < 0.4$ (Solo Strings)**: Routes melody notes solely to Channel 0 (Strings).
* **$0.4 \le \text{val} < 0.8$ (Strings + Woodwinds Doubling)**: Doubles the melody line across Channel 0 (Strings) and Channel 2 (Woodwinds / Flute).
* **$\text{val} \ge 0.8$ (Tutti Orchestral Doubling)**: Full tutti doubling across Channel 0 (Strings), Channel 2 (Woodwinds), and Channel 3 (Brass Section).

### 2. Harmony Registration & Density (`ha_register_ins`, `ha_ins_plus_minus`)
Harmony orchestration is driven by registration level and density controls:
* **Registration Order (`ha_register_ins`)**:
  * **Level 1.0**: Piano (Ch 5) — foundation for calm/somber presets.
  * **Level 2.0**: Piano + Strings (Ch 5, Ch 4).
  * **Level 3.0**: Piano + Strings + Woodwinds (Ch 5, Ch 4, Ch 6).
  * **Level 4.0**: Full Tutti (Ch 5, Ch 4, Ch 6, Ch 7) — energetic combat/heroic presets.
* **Density Gating (`ha_ins_plus_minus`)**: Scales the active instrument count deterministically from 1 instrument up to the registered maximum, weighted by `harmony_layer_weights`.

---

## Instrument Family Range Enforcement (§5.3)

To ensure realistic, playable orchestral voicings without clipped notes, the agent applies hierarchical range enforcement:
1. **Global Ranges**: `MELODY_RANGE = (48, 84)` and `HARMONY_RANGE = (36, 72)`.
2. **Family Ranges (`FAMILY_RANGES`)**:
   * `"strings"`: (48, 84)
   * `"piano"`: (36, 84)
   * `"woodwinds"`: (60, 84)
   * `"brass"`: (48, 77)
3. **Octave Transposition**: When a note falls outside its instrument family's register, it is shifted up or down in 12-semitone octave intervals until it lands within the bounds, preserving the pitch-class and harmonic identity.

---

## Acoustic Concert Hall Staging & CC Control

On startup and phrase boundaries, the agent queues continuous controller (CC) messages configured in `AUDIO_CONFIG` (`src/core/configs.py`):
* **CC64 (Sustain Pedal)**: Sent with value 127 to Piano channels (Ch 1 and Ch 5) for natural resonance and ringing chords.
* **CC7 (Channel Volume)**: Balances orchestral mix levels (Strings 100, Piano 95, Woodwinds 90, Brass 85, Drums 110).
* **CC10 (Stereo Panning)**: Places instruments realistically across the virtual stereo stage:
  * Strings: Left (`45`)
  * Piano: Center-Left (`56`)
  * Percussion: Center (`64`)
  * Woodwinds: Center-Right (`72`)
  * Brass: Right (`85`)
* **CC91 (Reverb Send)**: Dialed to create deep concert hall space (Strings 75, Woodwinds 70, Piano 60, Brass 65, Drums 70).
* **CC11 (Expression)**: Continuously dispatched proportional to layer weights ($\text{CC} = \text{round}(\text{weight} \times 127)$) for seamless dynamic swells during preset transitions.

---

## Public API

### `process_tick(melody_events, harmony_events) -> List[dict]`
Returns merged, range-safe, family-transposed event dictionaries for the current tick, deterministically gated by `ma_orch_plus_minus`, `ha_register_ins`, and `ha_ins_plus_minus`.

### `update_params(**kwargs) -> bool`
Updates orchestration parameters (`melody_channels`, `harmony_channels`, `ma_orch_plus_minus`, `ha_register_ins`, `ha_ins_plus_minus`, `audio_config`, `percussion_program`, etc.) and queues program and CC changes when state transitions occur.

### `consume_program_changes() -> List[Tuple[int, int]]`
Returns queued `(channel, program)` pairs for all 8 orchestral channels plus Channel 9 (`(9, 48)`) and clears the internal queue.

### `consume_cc_changes() -> List[Tuple[int, int, int]]`
Returns queued `(channel, cc_number, value)` staging tuples (CC64, CC7, CC10, CC91, CC11) and clears the internal queue.

### `on_phrase_start() -> None`
Forces a fresh program-change and CC acoustic staging snapshot at phrase boundaries.

---

## Dependencies

| Import | Role |
|---|---|
| `src.core.configs.MELODY_CHANNELS` | MIDI channels [0, 1, 2, 3] |
| `src.core.configs.HARMONY_CHANNELS` | MIDI channels [4, 5, 6, 7] |
| `src.core.configs.MELODY_PROGRAMS` | GM program patches [48, 0, 73, 61] |
| `src.core.configs.HARMONY_PROGRAMS` | GM program patches [48, 0, 73, 61] |
| `src.core.configs.PERCUSSION_PROGRAM` | GM program patch 48 (Orchestra Kit) |
| `src.core.configs.AUDIO_CONFIG` | CC7, CC10, CC91, CC64 staging specifications |
| `src.core.configs.FAMILY_RANGES` | Family pitch boundaries |
