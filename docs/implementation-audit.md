# PAMG Baseline Implementation Audit

**Audit date:** 2026-10-07  
**Scope:** `src/`, runtime entry points, configuration, dependencies, and supporting `.github/docs/` documentation  
**Reference:** [PAMG Baseline Model - Technical Reference](technical-reference.md)

## 1. Executive Summary

The codebase has the expected high-level PAMG decomposition: a clock drives a count loop, Melody/Harmony/Percussion agents generate content, and Melody/Harmony pass through an Orchestration Agent while Percussion has a direct MIDI path. The implementation is therefore structurally recognizable as PAMG.

It is not currently a faithful implementation of the baseline algorithm, and several runtime contracts are broken. The most important issues are:

| Priority | Finding | Impact |
|---|---|---|
| Critical | Single-port routing leaves the percussion target as `None`. | Percussion playback fails in the documented single-port configuration. |
| High | `MelodyAgent.get_lookahead()` references an uninitialized `total_pulses`. | The documented API raises `AttributeError` at runtime. |
| High | Harmony is a custom scale-degree chord generator rather than the specified grammar, chord pools, 12-level dictionary, and voice-selection model. | Core baseline harmony behavior is not implemented. |
| High | Interpolated harmony layer weights do not queue new MIDI CC 11 values. | Continuous orchestration fading stops after initialization. |
| High | The clock computes phrase length but does not propagate it to the Percussion Agent. | Percussion phrase structure can diverge from the shared phrase configuration. |
| Medium | MIDI note values outside `0..127` are accepted by normalization. | Invalid MIDI events can reach the backend and fail later. |
| Medium | There is no automated test suite. | Runtime regressions are currently detected only by manual probes or live use. |
| Medium | Seed gating works, but there is no explicit shared `SeedState` object or atomic broadcast. | The behavior is distributed across agents rather than represented as the reference contract. |

The implementation also contains useful extensions, including extra percussion voices, modal interchange, octave/range handling, and a richer preset model. These should be documented as product extensions, not counted as baseline compliance unless they preserve the reference invariants.

## 2. Audit Method and Evidence Rules

The audit compares implementation behavior with [technical-reference.md](technical-reference.md) and the local design notes in `.github/docs/`. The reference provenance is treated as follows:

- `[SPEC]`: compliance requirement unless the implementation explicitly documents a deliberate product deviation.
- `[FIG]`: architectural or data-flow requirement, especially for routing ownership.
- `[DEMO]`: observed behavior; useful for validation, but lower confidence than written specification.
- `[INFER]`: not used alone to classify a defect; reported as an uncertainty or design question.

Findings are classified as:

- **Confirmed defect:** reproducible runtime failure, unsafe contract, or behavior contradicted by a high-confidence requirement.
- **Baseline mismatch:** implemented behavior is materially different from the reference algorithm, even if it works as custom software.
- **Extension:** additional behavior that does not inherently contradict a baseline invariant.
- **Unresolved:** the reference does not provide enough information to assert one correct implementation.

Static inspection was supplemented by compilation and focused Python probes. No hardware MIDI port was used for this audit.

## 3. Architecture and Routing Audit

### 3.1 Expected routing invariant

The reference requires two distinct output paths:

1. Melody and Harmony produce content for the Orchestration Agent, which assigns instruments/channels and emits the melodic/harmonic MIDI stream.
2. Percussion bypasses the Orchestration Agent and emits its own direct MIDI stream.

The implementation follows this split conceptually. Percussion playback is scheduled independently in [clock.py](../src/core/clock.py#L554), while Melody and Harmony are consumed by the orchestration path.

### 3.2 Confirmed critical routing defect

In single-port mode, [clock.py](../src/core/clock.py#L258) initializes `mel_queue` but leaves `perc_queue` as `None`. Later, the drum dispatch path passes that value to `play_note` and `play_ratchet` in [clock.py](../src/core/clock.py#L570). The MIDI player then calls `target.send(...)` in [players.py](../src/core/players.py#L49), producing a runtime failure because the target is `None`.

**Classification:** Confirmed defect, Critical.  
**Required action:** Make the single-port routing object explicit and share it between melodic and percussion dispatch, while retaining separate agent logic and direct PA ownership.

### 3.3 Routing compliance matrix

| Contract | Status | Evidence |
|---|---|---|
| Clock drives indexed count loop | Partial | Implemented in [clock.py](../src/core/clock.py#L309), but parameter validation is incomplete. |
| MA output reaches OA | Conforms structurally | Agent and clock wiring follow the intended path. |
| HA output reaches OA | Conforms structurally | Harmony events are consumed by orchestration. |
| PA bypasses OA | Conforms structurally | PA creates direct channel 9 events in [percussion_agent.py](../src/modules/percussion_agent.py#L317). |
| Single-port mode provides all agents a valid destination | Fails | `perc_queue` remains `None`. |
| Multiple MIDI ports close safely | Risk | [clock.py](../src/core/clock.py#L633) may close the same object twice in single-port mode. |

## 4. Shared Timing, Lifecycle, and State

### 4.1 Clock and count loop

The clock performs the central scheduling role and updates interpolated state on each pulse. However, parameter application is conditional: agent parameters are applied on initialization, phrase boundaries, or downbeats rather than on every interpolator update. This can delay continuous parameter response by up to a beat ([clock.py](../src/core/clock.py#L330), [clock.py](../src/core/clock.py#L369)). Whether this is acceptable depends on whether the intended control surface is continuous or beat-quantized; the reference presents continuous parameter interpolation but does not fully specify application latency.

`run_clock()` accepts `tempo`, `loop_size`, and `grain`, but does not validate zero or negative values before division/modulo operations ([clock.py](../src/core/clock.py#L173), [clock.py](../src/core/clock.py#L176)). Invalid configuration can therefore fail with low-level arithmetic errors.

During normal `max_ticks` shutdown, the clock waits for scheduled note tasks ([clock.py](../src/core/clock.py#L607)). Long notes or ratchets can delay completion. In addition, [scheduler.py](../src/core/scheduler.py#L35) cancels and clears its task set immediately, limiting the ability to await cancelled tasks reliably.

**Classification:** Medium lifecycle risks; unresolved product decision for continuous-versus-quantized parameter application.

### 4.2 Seeded phrase generation

The deterministic pool gate is implemented: Pool 1 generates a new seed, while another pool retains the existing seed ([seeded_phrase_generator.py](../src/core/seeded_phrase_generator.py#L163)). The runtime probe confirmed:

```text
Pool 1: new seed 2662
Pool 2: existing seed 2662
```

The clock broadcasts changed seeds to Melody, Percussion, and Harmony ([clock.py](../src/core/clock.py#L452)). This is a positive result and supersedes the earlier concern that Harmony was omitted from the broadcast.

The remaining mismatch is representational: the reference defines a shared `SeedState` containing base, current, and rhythm seeds, while the implementation distributes seed state across the generator and agent setters ([seeded_phrase_generator.py](../src/core/seeded_phrase_generator.py#L141)). There is no explicit atomic broadcast of pitch and rhythm seed values. This is a **baseline design mismatch**, not a confirmed current runtime failure.

The Pool 1 condition in Harmony is approximated by `degree_index == 0` ([harmony_agent.py](../src/modules/harmony_agent.py#L142)) rather than being driven by a true chord-pool manager. Seed behavior is therefore only as correct as the Harmony approximation.

### 4.3 Preset interpolation

Bilinear interpolation and exponential smoothing are implemented in [preset_interpolator.py](../src/core/preset_interpolator.py#L267) and [preset_interpolator.py](../src/core/preset_interpolator.py#L313). Discrete values are deferred to phrase boundaries, which is a reasonable implementation of the reference's four-corner preset model.

Issues:

- `get_quantized_state()` is annotated as returning `Preset` but returns `None` on non-phrase pulses ([preset_interpolator.py](../src/core/preset_interpolator.py#L230)). This is an API/type contract defect.
- The preset model omits baseline concepts such as explicit movement controls, shape depth/length exposure, articulation threshold, and orchestration add/subtract controls ([preset.py](../src/models/preset.py#L22)).
- `INTERPOLATION_SMOOTHING_TIME` is configured as three seconds in [configs.py](../src/core/configs.py#L108), while local documentation describes 0.25 seconds as the default. This must be identified as an intentional product choice or corrected.
- The four shipped presets reuse the same harmony weights, programs, melody program, and layer mode ([configs.py](../src/core/configs.py#L155)), so several interpolation paths are not meaningfully exercised.

## 5. Melody Agent Audit

### 5.1 Confirmed runtime defect: lookahead

`get_lookahead()` calculates indexes using `self.total_pulses` ([melody_agent.py](../src/modules/melody_agent.py#L323)), but the constructor does not initialize that attribute ([melody_agent.py](../src/modules/melody_agent.py#L66)). The focused probe reproduced:

```text
AttributeError: 'MelodyAgent' object has no attribute 'total_pulses'
```

**Classification:** Confirmed defect, High.  
**Required action:** Establish the count-loop size through construction or a validated setter, and test lookahead at loop boundaries.

### 5.2 Baseline mismatches

- Staccato/legato is selected probabilistically ([melody_agent.py](../src/modules/melody_agent.py#L349)) rather than computed from distance to the next onset as specified.
- There is no explicit Moved List. Syncopation is represented as added onset indexes ([melody_agent.py](../src/modules/melody_agent.py#L264)).
- `shape_depth`, `shape_length`, and drunk mode exist ([melody_agent.py](../src/modules/melody_agent.py#L105)) but are not exposed through the canonical `Preset` or updated by the clock.
- `drunk_contour` is implemented as directional random walk behavior, without the reference's explicit interpolation between Moved List onsets ([melody_agent.py](../src/modules/melody_agent.py#L224)).
- The documented non-repetition behavior is not represented as an explicit control.
- Harmony filtering occurs after pitch-range clamping ([melody_agent.py](../src/modules/melody_agent.py#L407)), allowing the selected chord tone to fall outside the configured range before Orchestration compensates through transposition.

**Classification:** Baseline mismatches, mostly High for algorithm fidelity and Medium for range behavior.

## 6. Harmony Agent Audit

### 6.1 Major baseline mismatch

The reference specifies a Roman-numeral grammar, tiered chord modifications, chord pools, a generated chord dictionary indexed by chord symbol and tension level, a 12-level tension construction, bass selection, post-filtering, and voice selection from the most recently unlocked pitch classes.

The implementation instead builds scale-degree triads with optional seventh/ninth extensions, suspensions, inversions, and borrowed chords ([harmony_agent.py](../src/modules/harmony_agent.py#L322)). It has no implementation of:

- The 12-level ordered pitch-class tension table.
- A chord dictionary keyed by chord symbol and tension level.
- A real chord-pool manager with higher-complexity pool access.
- The specified Roman-numeral transition grammar and modification tiers.
- A Bass Selector.
- `voice_ins` selection of the right-most active pitch classes.

**Classification:** Confirmed baseline mismatch, High. This is the largest algorithmic gap in the repository.

### 6.2 Additional harmony findings

- Arpeggiation is selected primarily from tension/complexity thresholds ([harmony_agent.py](../src/modules/harmony_agent.py#L370)) without the reference's phrase-segmentation and dominant/tonic gating.
- `set_post_filter()` filters the current chord after construction ([harmony_agent.py](../src/modules/harmony_agent.py#L129)); it is not a separate dictionary-query/post-filter stage.
- Tension and complexity affect chord construction, but parameter changes do not consistently regenerate the progression ([harmony_agent.py](../src/modules/harmony_agent.py#L231), [harmony_agent.py](../src/modules/harmony_agent.py#L536)).
- `voice_index` metadata is implemented and consumed by Orchestration ([harmony_agent.py](../src/modules/harmony_agent.py#L380), [orchestrator_agent.py](../src/modules/orchestrator_agent.py#L164)). This local contract is sound even though the reference's voice-selection algorithm is missing.

The exact combined rule for segmentation versus tension-based block/arpeggio selection remains unresolved by the reference and should not be overclaimed in remediation.

## 7. Percussion Agent Audit

### 7.1 Conforming behavior

Percussion bypasses Orchestration and emits direct MIDI events. Per-instrument decisions are generated independently, and ratchets plus chord-pool-triggered fills are present ([percussion_agent.py](../src/modules/percussion_agent.py#L259), [percussion_agent.py](../src/modules/percussion_agent.py#L317)).

### 7.2 Findings

- The reference baseline defines Kick, Snare, Toms, and Cymbals. The implementation adds Hi-hat, Ride, Crash, and additional fill behavior ([configs.py](../src/core/configs.py#L45)). These are extensions unless they alter baseline voice behavior.
- The explicit combined `+/- KS` control and separate Toms/Cymbals controls are not represented in the preset model; current controls expose kick, snare, and hat probabilities ([preset.py](../src/models/preset.py#L31)).
- The clock computes `phrase_length` ([clock.py](../src/core/clock.py#L333)) but constructs `PercussionAgent` without passing it ([clock.py](../src/core/clock.py#L185)). PA therefore remains at its constructor default of four loops ([percussion_agent.py](../src/modules/percussion_agent.py#L30)).
- PA lookahead treats template positions as planned hits even when later probabilistic subtraction removes them ([percussion_agent.py](../src/modules/percussion_agent.py#L439)).
- `notify_chord_change()` marks a fill whenever the observed pool is 1 ([percussion_agent.py](../src/modules/percussion_agent.py#L259)) but does not itself verify a transition from another pool.

**Classification:** Phrase-length propagation is a confirmed High integration defect. The remaining items are baseline mismatches or Medium lookahead behavior risks.

## 8. Orchestration Agent Audit

### 8.1 Conforming behavior

The implementation includes octave transposition and family/channel range overrides ([orchestrator_agent.py](../src/modules/orchestrator_agent.py#L89), [orchestrator_agent.py](../src/modules/orchestrator_agent.py#L524)). Harmony voice metadata is used to distribute events.

### 8.2 Confirmed CC propagation defect

CC 11 values are queued during initialization, and the clock consumes pending CC changes ([orchestrator_agent.py](../src/modules/orchestrator_agent.py#L488), [clock.py](../src/core/clock.py#L427)). However, `update_params()` does not call `_queue_cc_changes()` when `harmony_layer_weights` changes ([orchestrator_agent.py](../src/modules/orchestrator_agent.py#L273)). The focused probe returned initial values followed by an empty list after updating weights:

```text
[(2, 11, 127), (3, 11, 127)]
[]
```

**Classification:** Confirmed defect, High.  
**Impact:** Preset interpolation cannot produce the documented continuous layer fade after startup.

### 8.3 Baseline mismatches

- `harmony_layer_mode` is stored and normalized but not used in event selection ([orchestrator_agent.py](../src/modules/orchestrator_agent.py#L311), [orchestrator_agent.py](../src/modules/orchestrator_agent.py#L164)).
- Layer weights are applied as hard thresholds rather than the documented probabilistic add/subtract behavior ([orchestrator_agent.py](../src/modules/orchestrator_agent.py#L181)).
- The reference treats instrument count, switching, and range as separable OA decisions. The implementation has pieces of this behavior, but the preset does not expose the baseline `Orch +/-` and range controls explicitly.

## 9. MIDI Event Construction and Playback

### 9.1 Confirmed validation defect

`normalize_event()` coerces note values to integers but does not clamp or reject values outside MIDI's `0..127` range ([midi_events.py](../src/core/midi_events.py#L36)). The probe accepted `note=200` and returned a `MidiEvent` with note 200. Velocity and channel are clamped, creating an inconsistent validation contract.

Duration validation also accepts `NaN` because `NaN <= 0` is false ([midi_events.py](../src/core/midi_events.py#L52)).

**Classification:** Confirmed defects, Medium.

### 9.2 Playback safety risks

- `send_cc()` suppresses all exceptions ([players.py](../src/core/players.py#L12)), which can hide invalid controller/value/channel failures.
- `play_ratchet()` and `play_arpeggio()` do not guarantee note-off in a `finally` block ([players.py](../src/core/players.py#L98), [players.py](../src/core/players.py#L157)). Cancellation can leave stuck notes.
- Single-port shutdown can close the same port object twice ([clock.py](../src/core/clock.py#L633)). Make closure idempotent and deduplicate targets.
- `MidiEvent` is a useful canonical model, but it does not enforce MIDI ranges or duration invariants itself ([midi_event.py](../src/models/midi_event.py#L4)).

## 10. Models, Configuration, Dependencies, and Documentation

### 10.1 Models and configuration

The `Preset` model ([preset.py](../src/models/preset.py#L22)) is richer than the four-corner reference model in some areas but omits several reference-facing controls. It should be treated as a product model with a documented compliance mapping, not assumed to be a one-to-one implementation of the reference parameter surface.

`configs.py` imports `Preset` indirectly through `preset_interpolator` ([configs.py](../src/core/configs.py#L9)). This works through a re-export but obscures the canonical model dependency.

### 10.2 Dependencies and support claims

`requirements.txt` declares `pytest` and `pytest-asyncio`, but the repository contains no tests. `python-rtmidi` is backend-sensitive on Windows, and no fake/headless MIDI backend is documented for automated verification.

The README claims Python 3.9+ support. The pinned NumPy and Matplotlib versions should be checked against that minimum in CI; this audit did not certify every Python-version combination.

### 10.3 Documentation alignment

The `.github/docs/` module notes provide useful local implementation context, but they should explicitly label which behavior is baseline PAMG and which behavior is a custom implementation. In particular, the harmony implementation and extra percussion voices currently look like interchangeable baseline implementations unless the deviation is called out.

## 11. Verification Results

| Check | Result | Interpretation |
|---|---|---|
| `python -m compileall src main.py generate_dataset.py pamg_gui.py` | Passed | Source compiles successfully. |
| `pytest -q` | No tests ran; exit code 5 | There is no automated test coverage. |
| Melody lookahead smoke test | Failed with `AttributeError` | `total_pulses` is uninitialized. |
| Seeded phrase Pool 1/Pool 2 probe | Passed expected gate behavior | Seed generation is partially conforming. |
| Orchestration CC update probe | Initial CCs emitted; no updated CCs | Weight changes are not propagated. |
| Invalid note normalization probe | Accepted note 200 | MIDI note validation is incomplete. |
| Live MIDI hardware test | Not run | Requires a backend/port and is outside this non-destructive audit. |

## 12. Remediation Roadmap

### Phase 1: Restore runtime safety

1. Fix single-port queue initialization and add a fake-target integration test for both melodic and percussion dispatch.
2. Initialize and validate Melody lookahead loop dimensions.
3. Propagate phrase length into PA construction and subsequent parameter updates.
4. Queue CC changes whenever harmony layer weights change.
5. Validate note, channel, velocity, duration, and finite numeric values at the canonical event boundary.
6. Guarantee note-off in cancellation paths and make port closure idempotent.

### Phase 2: Establish testable contracts

1. Add tests for clock configuration validation and bounded shutdown.
2. Add deterministic seeded-phrase tests for Pool 1, non-Pool 1, and zero-seed improvisation.
3. Add preset interpolation tests for continuous fields, discrete fields, and phrase-boundary quantization.
4. Add agent lookahead tests at ordinary, wraparound, and empty-plan positions.
5. Add orchestration tests for layer modes, weight changes, CC generation, channel assignment, and range handling.
6. Add MIDI normalization tests for all boundary values and invalid values.

### Phase 3: Decide baseline fidelity versus product extension

1. Decide whether the project targets exact baseline compatibility or a PAMG-inspired variant.
2. If baseline compatibility is required, implement the Harmony chord grammar, chord pools, generated dictionary, 12-level tension table, bass selector, and `voice_ins` semantics before tuning surface behavior.
3. Implement explicit Moved List and distance-derived articulation for Melody and Harmony if exact rhythm fidelity is required.
4. Map reference parameters to `Preset` explicitly, including controls that are currently inferred or absent.
5. Document extra percussion voices, modal interchange, and other extensions as intentional deviations.

## 13. Audit Limitations and Open Questions

- The reference does not fully specify the combined segmentation/tension rule for Chord Builder versus Arpeggiator.
- The exact staccato/legato threshold is unspecified.
- `tac`, `Register ins`, `Vel ins`, `Range ins`, `trans`, and `Move` have incomplete written definitions.
- Live MIDI behavior was not tested against physical or OS-backed ports.
- Compilation success does not establish runtime correctness; the focused probes demonstrate several failures despite clean compilation.
- No claim is made that the current custom extensions are musically incorrect. They are classified according to deviation from the supplied baseline specification.

## 14. Overall Assessment

The repository is a viable prototype with a recognizable agent architecture and several useful working subsystems, especially the clock wiring, direct percussion ownership, deterministic seed gate, preset interpolation primitives, and basic orchestration/range handling. It should not currently be described as a complete implementation of the PAMG baseline. Runtime safety issues should be addressed first, followed by a deliberate decision about whether to invest in exact harmony and rhythm algorithm fidelity or formally position the project as a PAMG-inspired extension.