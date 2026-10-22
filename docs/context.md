# Project Context: PAMG TCP Integration

## Primary Ground Truth
The single source of truth for the system's intended behavior, UI architecture, and technical rules is derived strictly from:
1. `pamg_gui.py`
2. `docs/technical-reference.md`
3. `docs/implementation-audit.md` (for auditing required fixes)
4. `docs/pa-observations.md` (owner-provided evidence for demo-observed Percussion Agent behavior)
5. `docs/tcp-contract.md` (TCP integration contract)

Any functions, logic, or architectural extensions currently in the codebase that
deviate from these sources (such as those formerly listed in
`custom_implementations.md`) must be removed or isolated to ensure strict
compliance with the original research model. PA behavior documented in
`pa-observations.md` is owner-provided demo evidence and is preserved when it
does not violate the documented PA routing invariant.

## Goal
The primary objective of this project is to integrate a TCP Socket Server into the Progressive-Adaptive Music Generator (PAMG) architecture. This server will listen for real-time game state variables sent from a game engine, and use them to drive the real-time music generation. 

## Architectural Alignment
According to the PAMG technical reference, the system generates music as MIDI events, which are sent to an Orchestrator Agent (OA) or directly to a MIDI port (in the case of the Percussion Agent). The core generation algorithms are deterministic and driven by a central clock and shared seed.

Integrating a TCP server to feed these inputs does not violate the core system architecture. The generation agents (Melody, Harmony, Percussion) still act upon the variables they are designed to consume. The only difference is the source of these variables: instead of being statically defined or generated via a local GUI, they are dynamically received over a network socket. The resulting MIDI notes can be captured and rendered by any capable external engine.

## Key Inputs to Support over TCP
*   **Tempo (BPM):** Affects the clock's `pulse_duration`.
*   **Time Signature / Loop Size / Grain:** Affects the clock's `loop_size` and `grain`.
*   **Seed:** Updates the `base_seed` for motif generation and variation.
*   **XY Pad Coordinates:** The TCP socket will receive continuous `(x, y)` float values (mapped to `0.0`-`1.0` internally). These single coordinates natively handle traversing the multidimensional parameter space (presets) using the `MultiParameterPresetInterpolator`.

By funneling these parameters through a local TCP server, PAMG becomes a flexible, standalone daemon capable of providing real-time adaptive music for any game engine capable of opening a socket connection.
