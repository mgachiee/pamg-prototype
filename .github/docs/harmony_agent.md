# Harmony Agent

**Module:** `src/modules/harmony_agent.py`  
**Architecture stage:** Module 3 - Harmony Agent  
**Reference:** [PAMG Technical Reference §4](../../docs/technical-reference.md#4-harmony-agent-ha--3x)

---

## Overview

The Harmony Agent generates Western tonal chord progressions, builds tension-driven pitch-class sets across 12 ordered levels, and emits harmonic MIDI events (block chords, arpeggios, and bass lines) aligned with the clock grid. It manages the 4-tier Chord Pools and publishes the active Chord Pool to gate the Seeded Phrase Generator upon re-entry into Pool #1.

---

## Architecture Context

```
Clock pulse ───► Harmony Agent ───► harmony events ───► Orchestration Agent
                       │
                       ├─► active chord pool (Pool 1) ──► Seeded Phrase Generator (Reseed Gate)
                       │
                       ├─► voiced chord notes ────────► Melody Agent (Harmony Filter)
                       │
                       └─► melody accent list ◄──────── Melody Agent
```

---

## Pipeline Components (§4.3)

1. **Harmonic Progression Selector (`src/core/harmony_grammar.py`)**: Traverses an Augmented Transition Network (ATN) based on Western tonal transition probabilities between functional states (Tonic $\to$ Subdominant $\to$ Dominant $\to$ Tonic).
2. **Chord Pools Manager (`src/models/harmony_types.py`)**: 
   - **Pool 1**: Primary diatonic triads ($\text{I}, \text{IV}, \text{V}$) — sole gate condition for Seeded Phrase Generator reseeding.
   - **Pool 2**: Full diatonic chords ($\text{ii}, \text{iii}, \text{vi}, \text{vii}^\circ$).
   - **Pool 3**: Secondary dominants and subdominants ($\text{V/V}, \text{V/ii}, \text{V/vi}, \text{IV/IV}$, etc.).
   - **Pool 4**: Chromatic tension modifications ($\text{N}^7, \text{It}^{+6}, \text{Fr}^{+6}, \text{Ger}^{+6}$).
   - Gated by `Cpx Prog` (`chord_complexity` $\in [0, 1]$).
3. **12-Level Tension Dictionary (`src/core/chord_dictionary.py`)**:
   - For every chord symbol, pitch classes are ordered across 12 levels:
     - **Levels 1–3**: Root triad (Root, 5th, 3rd)
     - **Levels 4–7**: Upper tertian extensions (7th, 9th, 11th, 13th)
     - **Levels 8–10**: Borrowed parallel-minor modal colors ($\flat 3, \flat 7, \flat 6$)
     - **Levels 11–12**: Chromatic dissonances ($\sharp 4/\flat 5, \flat 2$)
4. **Voice Selection (`voice_ins`)**: Takes the right-most $N$ active pitch classes of the prefix:
   $$\text{voiced\_pitches}(\text{tension}, N) = \text{ordered\_pitches}[0:\text{tension}][-N:]$$
5. **Bass Selector**: Emits an independent bass note (root or inversion) in the bass octave (MIDI 36–48).
6. **Chord Builder vs. Arpeggiator**: Low tension ($\le 3$) voices sustained block chords (calm/sanctuary); intermediate tension ($4 \dots 10$) plays flowing broken arpeggios across subdivisions; high tension ($\ge 11$) switches back to heavy block chords.
7. **Velocity Generation (`ha_vel_ins`, §3.2, §4.4)**: Dynamically scales normal and accent velocity ranges based on `ha_vel_ins` forwarded from MPIC presets, allowing quiet pianissimo ($pp$) in calm states and fortissimo in combat.

---

## Public API

### `get_current_chord(measure_index) -> List[int]`
Advances and returns the voiced MIDI notes for the current measure.

### `get_chord_pool() -> int`
Returns the active Chord Pool level (1..4). Pool 1 gates the Seeded Phrase Generator.

### `get_roman_numeral() -> str`
Returns the active Roman numeral chord symbol (e.g., `'I'`, `'V'`, `'N7'`).

### `process_tick(index, pulse_duration) -> List[dict]`
Emits block chord or arpeggiated MIDI events for the current tick.

### `notify_accents(accent_beats) -> None`
Receives melody accent beats to emphasize harmonic onsets.

### `set_post_filter(pitch_subset) -> None`
Applies a fast-cut pitch subset filter for rapid harmonic switching.

### `update_params(**kwargs) -> bool`
Updates runtime parameters (`tension`, `chord_complexity`, `voice_count`, `seed`, etc.).

---

## Dependencies

| Module | Role |
|---|---|
| `src.models.harmony_types` | `ChordPoolLevel` and `ChordDefinition` models |
| `src.core.chord_dictionary` | 12-level pitch-class construction and `voice_ins` query |
| `src.core.harmony_grammar` | ATN progression grammar and Chord Pools Manager |
| `src.core.configs.HARMONY_TEMPLATE` | Metric rhythm and accent templates |
