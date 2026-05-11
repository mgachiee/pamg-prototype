# System Architecture

This document describes the high-level system architecture for the PAMG Prototype. The design is divided into four stages: Global Control & Parameter Input, System Initiation & Timing, The Agent Network, and Final Output. Each stage defines clear responsibilities and data flows that together produce synchronized, parameter-driven MIDI output.

---

## Stage 1 — Global Control & Parameter Input
This stage acts as the "director," translating external inputs (composer presets, game variables, UI controls) into numerical parameter streams consumed by the agents.

- **Multi-Parameter Preset Interpolator (The Game Variable Bridge)**
	- Preset Creation: Users/composers place parameter snapshots into four preset slots labeled A, B, C, and D. Each slot stores a full set of agent-controlling parameters (tempo overrides, density, articulation, ratchet chance, instrument weights, filter settings, etc.).
	- The XY Pad: The four presets map to the corners of a 2D interpolation surface (an XY pad). The pad serves as a continuous control space.
	- Interpolation: External game variables, sensors, or UI axes are mapped to positions on the XY pad. The system performs smooth 2D interpolation (e.g., bilinear/interpolated blend) across the four corner presets to compute live parameter values.
	- Distribution: Interpolated parameter vectors are broadcast continuously to the agents (Melody Agent, Harmony Agent, Percussion Agent, Orchestration Agent) and to modules that consume global settings.

- **Seeded Phrase Generator (Motif Management)**
	- Base Input: Accepts a user-provided seed and a seed number as the phrase-generation base.
	- Chord Check: Monitors the Harmony Agent for the current "Chord Pool #" (a small integer identifying chord grouping/state).
	- Decision Gate: If the Harmony Agent's Chord Pool != 1, the generator stays idle. If Chord Pool == 1, it computes a new seeded value by adding a seeded random offset to the user seed; the magnitude of the random offset is scaled by a configurable `Seeded Phrase Length` parameter.
	- Seed Update: The computed seed is published to all agents to trigger the creation of new variations/motifs synchronized across the network.

---

## Stage 2 — System Initiation & Timing
This stage establishes the authoritative timing grid that all agents follow.

1. **Playback Initiation:** The system is started/stopped with a terminal control labeled `Play/Stop`. This toggles the central timing engine and the streaming of events.
2. **The Clock Module:** On `Play`, the Clock constructs a master time grid driven by three parameters:
	 - `Tempo` (BPM)
	 - `Loop size` (measured in beats or bars)
	 - `Grain` (subdivision granularity per loop step)
3. **The Count Loop:** The Clock emits a continuous, indexed pulse sequence: 0, 1, 2, ..., (loop_size × grain) - 1. Each pulse represents the smallest allowed onset for any musical event and serves as the synchronization tick for agents.

The Clock is authoritative: agents schedule events relative to the Count Loop indices and may request lookahead information (next N pulses) when building complex patterns.

---

## Stage 3 — The Agent Network
Clock pulses and the interpolated parameter stream are broadcast across the Agent Network. Each agent consumes timing, parameter vectors, and seeds to generate its MIDI event stream.

- **Harmony Agent (HA) — The Chords**
	- Rhythm: Generates chord rhythm using an Accent/Beat Follower and Add/Sub Filling strategies to vary density and accents.
	- Sequence: Queries a Chord Dictionary and uses a Harmonic Progression Selector to decide chord changes and progression complexity.
	- Construction: A Chord Builder combines chord tones and a configurable Arpeggiator to produce the actual harmonic pitch events for playback.

- **Melody Agent (MA) — The Lead Line**
	- Rhythm: Builds melodic onsets based on beat position and injects syncopation rules for interest.
	- Velocity: Uses a random-walk velocity generator to produce expressive accenting; syncopated notes often receive bias toward higher velocity.
	- Pitch: Supports `drunk` and `drunk-contour` modes for stochastic melodic motion and contour-preserving drift.
	- Filtering: A Harmony Filter maps/adjusts raw melodic pitches so they conform to the Harmony Agent's current chord tones and voicing constraints.

- **Percussion Agent (PA) — The Drums**
	- Rhythm: Creates distinct patterns per percussion instrument (Kick, Snare, Toms, Cymbals) each driven by an Accent/Beat Follower and Add/Sub Filling.
	- Ratcheting: A Ratchet module inserts controlled rhythmic repetitions (subdivided bursts) when chosen by pattern rules.
	- Alignment: Change-detection logic aligns percussion fills and shifts with Harmony changes to preserve musical form.

- **Orchestration Agent (OA) — The Ensemble Director**
	- Intake: Receives constructed MIDI event streams from MA and HA.
	- Management: Assigns instruments and channels to melodic/harmonic lines, enforces instrument ranges, applies dynamic voicing rules, and swaps orchestrations on loop or conditional triggers.

Agents should be designed to be mostly stateless between loops where possible, relying on the Clock and Seed updates for global continuity. Local state (pattern counters, ratchet queues) is permitted for short-term behavior.

---

## Stage 4 — Final Output
The Orchestration and Percussion Agents produce finalized MIDI streams intended for external instruments or DAWs.

- **Main Stream:** The Orchestration Agent emits a combined MIDI stream containing Melody and Harmony data with explicit instrument channel assignments.
- **Percussion Stream:** The Percussion Agent emits an independent MIDI stream scoped to percussion channels.
- **MIDI Port:** Both streams are routed to one or more MIDI ports (virtual synths, soft instruments, or external devices). The MIDI port(s) are the final boundary for audible rendering.

---

## Data Flow Summary
1. External controls / game variables / composer presets → Preset Interpolator (XY pad)
2. Interpolator → continuous parameter vectors → Agent Network
3. User seed + Seeded Phrase Generator (conditional on Chord Pool) → global seed broadcasts
4. `Play/Stop` → Clock → Count Loop pulses
5. Clock ticks + parameters + seeds → HA, MA, PA, OA generate MIDI events
6. OA merges MA/HA streams; PA remains separate → MIDI port(s)

## Module mapping (implementation reference)
- Preset interpolator: `core/preset_interpolator.py`
- Seeded phrase generator: `core/seeded_phrase_generator.py`
- Clock and timing: `core/clock.py`, `core/scheduler.py`
- MIDI I/O and routing: `core/midi_io.py`, `core/midi_events.py`, `core/routing.py`
- Agents: `modules/harmony_agent.py`, `modules/melody_agent.py`, `modules/percussion_agent.py`, `core/players.py`, `core/orchestration` (or similar)

## Notes & Implementation Guidance
- Keep the Clock authoritative to avoid drift; prefer scheduling events as indices into the Count Loop.
- Interpolation should run continuously but be rate-limited relative to the Clock to avoid excessive parameter churn (e.g., update parameter vectors once per beat or per fractional beat depending on precision needs).
- Seeds must be distributed atomically when updated so all agents generate consistent motif variants on the same loop.
- Design agents to expose simple parameter hooks so the interpolator can influence behavior without deep coupling.
