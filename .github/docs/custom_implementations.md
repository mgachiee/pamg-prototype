# PAMG Prototype: Custom Implementations & Rules

This document catalogs the specific implementation decisions, rules, and architectural refinements added to the PAMG Prototype that extend beyond the original blueprint described in the Duarte (2024) paper. These additions ensure technical robustness, improved musicality, and better system cohesion.

---

## 1. Unified `Preset` Data Model
**Location:** `src/models/preset.py`

While the original study discusses parameter snapshots, this implementation uses a canonical `Preset` dataclass to group all continuous and discrete parameters.

*   **Continuous Fields:** Blended linearly (e.g., `melody_max_step`, `drum_kick_probability`).
*   **Discrete Fields:** Snapped at phrase boundaries (e.g., `melody_program`, `scale_mode`).
*   **Benefits:** Ensures that all agents always receive a self-consistent state and allows the interpolator to handle complex structures natively without manual indexing.

## 2. Russell's Circumplex Model Mapping
**Location:** `src/core/configs.py`

The four corner presets (A, B, C, D) are explicitly mapped to the quadrants of Russell's Circumplex Model of Affect (Valence and Arousal):

*   **Preset A (Q1: Excited):** High Arousal, Positive Valence. Uses **Lydian** mode, high syncopation, and dense rhythms.
*   **Preset B (Q2: Angry):** High Arousal, Negative Valence. Uses **Locrian** mode, aggressive ratchets, and high tension.
*   **Preset C (Q3: Sad):** Low Arousal, Negative Valence. Uses **Aeolian** mode, sparse rhythms, and low pitch ranges.
*   **Preset D (Q4: Calm):** Low Arousal, Positive Valence. Uses **Major (Ionian)** mode, zero tension, and flowing legato movement.

This mapping ensures that the "tension" axis of the original study corresponds to a well-established psychological framework.

## 3. Modal Interchange (Mode Shifting)
**Location:** `src/modules/harmony_agent.py`, `src/core/clock.py`

Instead of relying on random chromatic dissonance to represent tension, the system uses **Modal Interchange**.

*   **Rule:** The `scale_mode` parameter defines the active scale (Major, Dorian, Phrygian, Locrian, etc.).
*   **Phrasing:** Mode changes are quantized to phrase boundaries via the `_DISCRETE_FIELDS` logic in the interpolator, preventing jarring mid-phrase key shifts.
*   **Benefit:** Provides a more professional and cinematically effective way to alter musical tension while remaining harmonically cohesive.

## 4. Continuous Volume Fading (MIDI CC 11)
**Location:** `src/modules/orchestrator_agent.py`, `src/core/players.py`

The original study describes adding/subtracting instruments via probabilistic note-dropping. This implementation improves upon this by using **MIDI CC 11 (Expression)**.

*   **Mechanism:** `harmony_layer_weights` are mapped directly to CC 11 values (0-127).
*   **Blending:** Instruments smoothly fade their volume in and out as the XY pad moves, creating a sophisticated orchestral crossfade.
*   **Benefit:** Eliminates the glitchy feel of "probabilistic dropping" and allows for subtle timbral shifting.

## 5. State Broadcasting Architecture
**Location:** `src/core/clock.py` -> `pamg_gui.py`

To enforce a **Single Source of Truth**, the GUI was decoupled from the interpolation logic.

*   **Functionality:** The `run_clock` loop accepts a `state_broadcast_callback`. Every tick, the Clock pushes its internal computed state (parameters, XY coordinates) back to the GUI.
*   **Benefit:** Ensures the GUI monitor panel reflects *exactly* what the generator is doing, eliminating discrepancies between UI and background processing.

## 6. Arpeggio Coordination via Metadata
**Location:** `src/modules/harmony_agent.py`, `src/modules/orchestrator_agent.py`

To implement multi-instrument arpeggio distribution, the system uses a metadata tagging system.

*   **Rule:** Harmony events are tagged with a `voice_index`.
*   **Distribution:** The Orchestrator uses this index to route specific notes of a chord/arpeggio to specific MIDI channels in the `harmony_channels` list.
*   **Benefit:** Allows for complex orchestral voicings where chord tones are split between different instruments (e.g., strings and brass).

## 7. Musical Octave Transposition
**Location:** `src/modules/orchestrator_agent.py`

Instead of simply "clipping" out-of-range notes (clamping), the Orchestrator uses octave shifting.

*   **Algorithm:** The `_transpose_note_to_range` method shifts notes by $\pm 12$ semitones until they fit the instrument's boundary.
*   **Benefit:** Preserves the harmonic function of the note (e.g., a C remains a C) while ensuring it stays within the technical range of the target instrument.

## 8. Lookahead API Implementation
**Location:** `src/modules/melody_agent.py`, `src/modules/percussion_agent.py`

The abstract requirement for "lookahead" was implemented as a public API.

*   **Method:** `get_lookahead(current_tick, lookahead_ticks)` returns relative indices of upcoming planned onsets.
*   **Technical Implementation:** Queries precomputed structures like `_onset_indices` (Melody) and `subfills` (Percussion).
*   **Benefit:** Provides a standardized interface for future-aware orchestration or UI visualisers.
