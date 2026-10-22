# Percussion Agent Observation Notes

## Provenance

The project owner has identified the current Percussion Agent behavior as being
based in part on direct observations of the PAMG demonstration video. These
observations are project-owned evidence for the PA implementation, even when a
detail is not restated in the written technical reference.

This note records that provenance without replacing the normative architecture
in `technical-reference.md`.

## Preserved observed behavior

The PA implementation may retain the following observed behaviors when they do
not violate the documented routing invariant:

- independent Kick, Snare, Toms, and Cymbals onset rows;
- combined Kick/Snare density control with independent row generation;
- velocity accents and subdued/ghost articulations;
- ratchet and fill-in activity;
- phrase-boundary and harmonic-change fills;
- orchestral drum timbres and additional fill/tom choices visible in the demo.

The current implementation uses General MIDI Crash Cymbal 1 (note 49) for the
baseline Cymbals row. GM note 42 is a closed hi-hat and is intentionally not
used for this orchestral row. Positive `+/- KS` increases the Kick/Snare row
activity on their template beats and phrase events; it does not add a regular
offbeat pop/rock backbeat. These are implementation choices for the owner-
observed orchestral sound, not additional PAMG algorithm requirements.

## Architectural constraint

Percussion remains an independent agent and emits directly to the MIDI output
path. It must not depend on the Orchestration Agent for melodic/harmonic voice
assignment or instrument management.

Any behavior not covered by the written reference or these owner-provided
observations must be treated as an implementation detail, not as PAMG baseline
behavior.
