# PAMG Baseline Implementation Audit

**Audit date:** 2026-10-21
**Scope:** documented PAMG generation path, agent contracts, presets, MIDI
event safety, offline dataset parity, and focused tests. TCP transport and
SoundFont rendering are intentionally retained infrastructure and are not
alignment targets.

## Current assessment

The repository follows the documented architecture: a central clock drives
Melody, Harmony, Percussion, and Orchestration; Melody and Harmony route
through OA; Percussion retains its independent direct MIDI path.

The implementation now applies phrase boundaries by loop index, preserves PA
plans during velocity-only updates, keeps Harmony filtering authoritative, and
normalizes MIDI event values at the model boundary.

## Verified documented alignment

- PA remains independent of OA and preserves the owner-observed behavior in
  [pa-observations.md](pa-observations.md), including orchestral rows, fills,
  rolls, velocity changes, and Melody Moved List accent exchange.
- Single-port and split-port queue routing remain supported.
- Melody shape length is constrained to the documented `1/4` to `8` loop
  range.
- Preset interpolation uses bilinear XY blending, exponential smoothing, and
  phrase-quantized discrete values.
- Presets A/C use Minor and B/D use Major; mode changes occur at phrase
  boundaries. Minor mode uses the project-selected natural-minor qualities.
- Harmony uses Roman grammar, chord pools, the 12-level dictionary,
  right-most voice selection, bass construction, post-filtering, and the
  documented local arpeggio behavior.
- A supplied Harmony post-filter is authoritative; an empty intersection
  produces intentional Harmony silence.
- Deterministic seed changes remain gated by Pool 1 re-entry. Seed `0` emits
  fresh pitch and rhythm seed state on every clock tick.
- OA layer-weight CC messages are emitted only when their value changes, while
  forced phrase snapshots remain available.
- MIDI events enforce integral MIDI fields, MIDI ranges, and finite positive
  duration. Compatibility normalization remains responsible for raw agent
  dictionaries.

## Owner-observed behavior

PA behavior is based on [pa-observations.md](pa-observations.md) where the
demonstration behavior is not contradicted by the documented routing and
ownership rules. PA is not permitted to depend on OA or Melody/Harmony
articulation logic.

## Local implementation decisions

These are documented project decisions, not claims about an exact source-level
PAMG formula:

1. Natural-minor mode uses `i`, `ii°`, `III`, `iv`, `v`, `VI`, and `VII`
   qualities.
2. Phrase segmentation gates arpeggiation and tension levels `4–10.5` select
   arpeggiation inside the open segment.
3. The arpeggio-rate denominator is `4 × grain`.
4. An empty Harmony post-filter produces silence.
5. Exact augmented-sixth pitch spellings and the precise combined arpeggiator
   segmentation formula remain unspecified by the supplied PAMG sources.

## Historical findings

Earlier audit versions listed routing, lookahead, PA phrase propagation, layer
CC propagation, MIDI normalization, cancellation safety, and missing tests as
active defects. Those findings are archived; the current audit does not treat
them as unresolved alignment gaps.

## Verification limits

- Focused agent and model tests pass in the current environment.
- Full Windows asyncio/audio verification remains environment-dependent; the
  MIDI cancellation/audio path can hang before pytest reports completion.
- Live MIDI hardware and real FluidSynth output were not used for compliance
  tests.
- TCP packet behavior and SoundFont rendering were intentionally not modified
  or redesigned.
