# PAMG System Architecture
## Progressive-Adaptive Music Generator — Development Blueprint

**Source:** Duarte, A. E. L. (2024). *A Progressive-Adaptive Music Generator (PAMG): An Approach to Interactive Procedural Music for Videogames.* FARM '24, ACM SIGPLAN, Milan, Italy. https://doi.org/10.1145/3677996.3678291

> **How to read this document**
> Boxes describe **processes/algorithms**. Bold enclosed items are **input parameters**. Ovals indicate **data accessible by multiple agents at runtime**. Dashed regions are **process groups**. This notation mirrors the custom flow diagrams used in the paper (Figures 1–7).

---

## System Overview

PAMG is a real-time algorithmic music generation system that produces continuous MIDI output driven by external gameplay variables or composer controls. It consists of five numbered agents/modules connected through a shared timing grid and a live parameter stream.

```
┌─────────────────────────────────────────────────────────────────┐
│                     COMPOSER / GAME INPUTS                      │
│  User presets (A/B/C/D)  ·  XY pad position  ·  Base seed       │
└───────────────┬─────────────────────────┬───────────────────────┘
                │                         │
                ▼                         ▼
   ┌────────────────────┐    ┌────────────────────────────┐
   │ Multi-Parameter    │    │  Seeded Phrase Generator   │
   │ Preset Interpolator│    │  (Motif Management)        │
   │ (XY pad bridge)    │    │  Fig. 7                    │
   │ Fig. 6             │    └──────────────┬─────────────┘
   └────────┬───────────┘                   │
            │ Interpolated                  │ Seed broadcast
            │ parameter vectors             │ (on chord change)
            │                               │
            ▼                               ▼
┌───────────────────────────────────────────────────────────────┐
│                        AGENT NETWORK                          │
│                                                               │
│    Play/Stop ──► 1. Clock (Tempo, Loop size, Grain)           │
│                        │                                      │
│          Count Loop  0, 1, 2 … (loop×grain)-1                 │
│                        │                                      │
│         ┌──────────────┼──────────────┐                       │
│         ▼              ▼              ▼                       │
│   2. Melody      3. Harmony    4. Percussion                  │
│      Agent          Agent         Agent                       │
│         │              │              │                       │
│         └──────┬───────┘              │                       │
│                ▼                      │                       │
│         5. Orchestration              │                       │
│            Agent                      │                       │
└────────────────┬──────────────────────┼───────────────────────┘
                 ▼                      ▼
        MIDI stream                MIDI percussion
        (MA+HA, instrument         stream
         channels assigned)
                 │                      │
                 └──────────┬───────────┘
                            ▼
                       MIDI port(s)
```

---

## Module 0 — Playback Control

**Terminal control:** `Play / Stop`

Starts and stops the entire system. On `Play`, the Clock is initialised and all agents begin listening to the Count Loop. On `Stop`, all event streams are flushed and agents reset.

---

## Module 1 — Clock & Count Loop
*(Paper: Fig. 1 — "Playback" section)*

The Clock is the **single authoritative time source** for the entire system. No agent may self-time; all events are scheduled as indices into the Count Loop.

### Input Parameters

| Parameter | Description |
|---|---|
| **Tempo** (BPM) | Global playback speed |
| **Loop size** | Length of the repeating loop in beats or bars |
| **Grain** | Subdivision granularity — sets the minimum onset resolution per loop step |

### Output

The Clock emits a continuous, indexed pulse sequence:

```
Count Loop:  0, 1, 2, 3, … (loop_size × grain) − 1, 0, 1, 2, …
```

Each pulse index is the smallest allowed onset for any musical event. Agents schedule events as integer offsets into this loop and may request **lookahead** (next N pulses) when constructing complex patterns.

### Design constraints
- The Clock is authoritative: agents must not introduce independent timing sources.
- Rate-limit parameter updates relative to the Clock (e.g., once per beat) to prevent excessive parameter churn.

---

## Module — Multi-Parameter Preset Interpolator
*(Paper: Fig. 6 — "The Game Variable Bridge")*

Translates external game variables or composer XY pad input into live parameter vectors distributed to all agents.

### Concept: XY Pad & Four Preset Corners

Composers define four complete parameter snapshots (Presets A, B, C, D), each assigned to a corner of a 2D interpolation surface (the XY pad). An external position `(x, y)` on the pad drives a continuous bilinear blend across all four presets.

```
C (0,1) ─────── D (1,1)
│               │
│    XY pad     │       ← game variables / UI map to (x, y)
│               │
A (0,0) ─────── B (1,0)
```

Each preset stores a **full set of agent-controlling parameters**, including (but not limited to): tempo overrides, note density, articulation, ratchet chance, instrument weights, filter settings.

### Process

1. Receive `(x, y)` position from game variables, sensors, or UI controls.
2. Compute bilinear weights: `w_A=(1−x)(1−y)`, `w_B=x(1−y)`, `w_C=(1−x)y`, `w_D=xy`.
3. Blend all preset parameters using these weights.
4. Apply exponential-lag smoothing so transitions feel gradual.
5. Broadcast the resulting parameter vector continuously to all agents.

### Design constraints
- Interpolation runs continuously but is rate-limited to avoid parameter churn.
- Discrete parameters (e.g., instrument programs) snap to the dominant preset's value and are deferred to phrase boundaries to prevent mid-phrase timbral jumps.
- Implementation: `core/preset_interpolator.py`

---

## Module — Seeded Phrase Generator
*(Paper: Fig. 7 — "Motif Management")*

Decides when a new seed should be issued to the Agent Network and computes its value. A shared seed ensures all agents generate mutually consistent musical variations simultaneously.

### Input

| Input | Source |
|---|---|
| **User seed** (base seed) | Composer / config; `0` activates improvisation mode |
| **Seed Rhy. / Seed number** | Same value — seeds both rhythm and pitch generation |
| **Chord Pool #** | Harmony Agent (current harmonic pool identifier) |
| **Seeded Phrase Length** | Interpolator or config — scales the random offset magnitude |

### Decision Gate (Fig. 7 logic)

```
Is current Chord Pool == 1?
        │
   No ──┴── Yes
   │         │
Do Nothing   Add seeded random value to user seed
             (scaled by Seeded Phrase Length)
                        │
             Update Seed/Rhy. Seed in ALL agents
             → triggers new phrase/motif variation
```

### Two Operating Modes

**Deterministic mode** (`base_seed != 0`):
- On Chord Pool == 1: compute `new_seed = base_seed + rng.randint(1, 1000) × phrase_length`; re-seed the internal RNG; broadcast to all agents.
- On Chord Pool != 1: return existing seed unchanged (agents stay on the current phrase).
- Same base_seed + phrase_length = reproducible seed sequence.

**Improvisation mode** (`base_seed == 0`):
- Generate a new OS-entropy seed on every chord change regardless of pool.
- Produces spontaneous, non-repeating variations for live performance.

### Design constraints
- Seeds must be distributed **atomically** when updated so all agents generate consistent motif variants on the same loop boundary.
- Implementation: `core/seeded_phrase_generator.py`

---

## Module 2 — Melody Agent (MA)
*(Paper: Fig. 2)*

Generates the lead melodic line. All sub-processes receive the Count Loop pulse and the current interpolated parameter vector.

### 2.1 Rhythm Generation

**Input parameters:** move even/odd, motion value

1. **Beat and Moved list** — constructs a list of onset positions aligned to beats.
2. **Add/Sub Filling** — adds or subtracts onsets to vary density and pattern complexity.
3. **Syncopation** — displaces onsets (anticipation / delay) using even/odd pulse division; alternating directions avoid metric over-simplification.
4. **Staccato/Legato duration** — assigns note length per onset.

The resulting accent/motion pattern is **shared with other agents** (HA, PA) to coordinate accents across the ensemble.

### 2.2 Velocity Generation

**Input parameters:** `ma_velocity`, random walk parameters

- Assigns note velocities using a **mean-reverting random-walk sequence** anchored to `ma_velocity`:
  $$\text{pull} = (\text{base\_vel} - \text{current\_vel}) \times 0.35$$
  with bounded step perturbations ($\pm 3$).
- Syncopated onsets receive a **proportional velocity boost** ($0.15 \times \text{base\_vel}$), dynamically scaling expressive accents relative to current intensity ($pp$ vs $ff$) rather than using static offsets.

### 2.3 Pitch Generation

**Input parameters:** step, range, non-repetition flag

Two stochastic pitch modes:

| Mode | Behaviour |
|---|---|
| `drunk` | Pure random walk — pitch moves step-by-step within a defined range without strict directionality |
| `dcontour` | Contour-preserving random walk — pitch drift follows a long-term melodic shape contour; accommodates listener expectation of periodic structure |

### 2.4 Shape Melody

**Input parameters:** depth, length

Applies a long-term transposition contour over time, shaping the overall melodic arc across multiple phrases.

### 2.5 Melody Change (Transposition Change)

Analyses previous pitches to adjust transposition and phrase structure — ensures melodic progression over time rather than static wandering.

### 2.6 Harmony Filter (post-pitch)

Adjusts raw pitch values so they conform to the Harmony Agent's current chord tones and voicing constraints. The filter maps out-of-harmony pitches to the nearest valid chord tone.

### 2.7 MIDI Event Construction

Combines rhythm (onset list + durations), velocity, and filtered pitch into a **MIDI event stream** sent to the Orchestration Agent (Module 5).

---

## Module 3 — Harmony Agent (HA)
*(Paper: Fig. 3)*

Generates the chordal harmonic layer. Coordinates with the Melody Agent via the shared accent list and provides the current chord context to all other agents.

### 3.1 Rhythm Generation

**Input parameters:** accent/beat follower parameters, add/sub filling parameters, staccato/legato duration

Uses the same Accent/Beat Follower + Add/Sub Filling approach as MA, but tuned for chordal rhythm. Receives MA's motion pattern to align chord onsets with melodic accents.

### 3.2 Velocity Generation

**Input parameters:** `ha_vel_ins`, MA accent pattern

- Dynamically scales harmonic attack velocities using `ha_vel_ins`:
  - Normal attacks: $[\text{vel}-6, \text{vel}+6]$ clamped to $[1, 127]$.
  - Accented attacks: $[\text{vel}+6, \text{vel}+16]$ clamped to $[1, 127]$.
- Emphasises chord onsets according to the **main accent list provided by MA**, ensuring harmonic attacks reinforce rather than conflict with melodic accents while maintaining a serene pianissimo or dramatic forte floor.

### 3.3 Harmony Sequence Generation

The core harmonic logic. Composed of:

#### 3.3.1 Switch Harmony
Decides when to switch harmonic content, based on loop position and parameter input.

#### 3.3.2 Harmonic Progression Selector
Manages harmonic content and complexity level. Contains two sub-components:
- **Chord Pools Manager** — groups available chords into pools (Pool 1 = home/tonic region; higher pools = increased tension/complexity). Publishes the current `Chord Pool #` consumed by the Seeded Phrase Generator.
- **Bass Selector** — chooses bass voice from the current chord pool.

Progression complexity increases by progressively adding pitches across **12 tension levels per chord**, mirroring historical use of dissonance. Chord transitions use **Western tonal system probability tables** (not pre-composed patterns), inspired by Tymoczko's first-order functional harmony properties.

#### 3.3.3 Chord Dictionary Query + Post Filter
Queries the chord dictionary for the current chord structure. A **Post Filter** enables rapid switching to a new pitch subset — used to implement fast harmonic changes (e.g., modulations) without waiting for the next full phrase boundary.

#### 3.3.4 Chord Builder
Constructs the full chord voicing from chord tones, tension levels, and spectral distance-based perceptual affinities.

#### 3.3.5 Arpeggiator
Configurable arpeggiator that distributes chord tones rhythmically. Coordinated with the Orchestration Agent for multi-instrument voicing.
- **Tension Gating:** Arpeggiation is strictly gated by harmonic tension ($3.0 < \text{ha\_tension} \le 10.5$). When $\text{ha\_tension} \le 3.0$ (calm / ambient states), the agent renders sustained block chords, avoiding uncharacteristic 16th-note movement.

### 3.4 Harmony Change
Adjusts internal parameters based on chord progression events, including modulations and rhythmic pattern changes at chord boundaries.

### 3.5 MIDI Event Construction
Combines harmony pitches, velocity, and duration into a **MIDI event stream** sent to the Orchestration Agent.

### Published data (accessible by other agents)
- `Chord Pool #` → consumed by Seeded Phrase Generator
- Current chord tones / harmony pitches → consumed by MA Harmony Filter and OA

---

## Module 4 — Percussion Agent (PA)
*(Paper: Fig. 4)*

Generates the cinematic orchestral percussion layer. Operates **independently** of the Orchestration Agent — its MIDI stream routes directly to MIDI Channel 9 (configured for the General MIDI Orchestra Kit, Bank 128, Program 48).

### 4.1 Rhythm Generation (per instrument row)

The rhythm engine runs **separately for each of the four baseline percussion rows**:

| Instrument Row | GM Orchestra Kit Notes | Rhythm & Articulation Algorithm |
|---|---|---|
| **Kick** | Note 36 (Gran Cassa / Concert Bass Drum) | Downbeat structural anchor; Add/Sub stochastic downbeat pulse; phrase-gated to even measures in low-tension states |
| **Snare** | Note 38 (Concert Snare), 40 (Snare Roll), 37 (Side Stick) | Half-time cadence punctuation; automatic `SIDE_STICK` in calm/low-vel states; suppressed mid-measure in negative deltas |
| **Toms** | Notes 45, 48, 50 (Timpani A, c, d) | Preparation rolls into downbeats; pitched timpani movement; cadential gating in negative deltas |
| **Cymbals** | Notes 42 (Susp. Cymbal), 57 (Concert Cymbal 2) | Phrase entrance accents and ambient wash; restricted to phrase boundaries in negative deltas |

Each instrument row has its own onset pattern, density, and accent profile derived from its own baseline parameters (`pa_ks_plus_minus`, `pa_toms_plus_minus`, `pa_cymb_plus_minus`).

### 4.2 Velocity Generation & Low-Tension Dynamics
Accentuates specific percussion onsets based on beat position and `pa_vel_perc`. Applies Add/Sub Filling stochastic subtraction (§4.1.2) with phrase-aligned sparseness rather than binary track mutes, preserving quiet, organic textures (~2–3 $pp$ events/measure) in low-tension states.

### 4.3 Ratchet (Exponential Crescendo Drum Rolls)
Inserts controlled rhythmic repetitions (subdivided bursts) at rule-selected points. Ratchets follow an exponential crescendo curve ($\text{factor} = 0.30 + 0.70 \times (i / (N-1))^{1.2}$ in `play_ratchet()`) with duration protection ($\ge 0.35$s–0.45s) to guarantee clear, audible swells from $p$ to $f$.

### 4.4 Change (Percussion Change)
Change-detection logic that **aligns percussion fills, rolls, and pattern shifts with Harmony Agent chord changes** (gated by Chord Pool 1 transitions), preserving musical form at harmonic boundaries.

### 4.5 MIDI Event Construction
Outputs a **MIDI percussion stream** sent directly to Channel 9 on the MIDI port / FluidSynth (bypasses Orchestration Agent).

---

## Module 5 — Orchestration Agent (OA)
*(Paper: Fig. 5)*

A downstream master orchestrator that receives completed MIDI streams from MA and HA and manages the **4x2 Dynamic Orchestral Matrix across 8 MIDI channels**, range enforcement with octave transposition, dynamic doubling/registration, and acoustic concert hall staging.

> **Important:** The Orchestration Agent does NOT independently generate rhythm or receive seeds. It is a post-processing and routing layer for MA and HA output.

### 4x2 Orchestral Matrix & Channel Mapping (§6.2)

| Channel | Stream | Family | GM Program | Default Patch |
|---|---|---|---|---|
| **Ch 0** | Melody | Strings | **48** | String Ensemble 1 |
| **Ch 1** | Melody | Piano | **0** | Acoustic Grand Piano |
| **Ch 2** | Melody | Woodwinds | **73** | Flute |
| **Ch 3** | Melody | Brass | **61** | Brass Section |
| **Ch 4** | Harmony | Strings | **48** | String Ensemble 1 |
| **Ch 5** | Harmony | Piano | **0** | Acoustic Grand Piano |
| **Ch 6** | Harmony | Woodwinds | **73** | Flute |
| **Ch 7** | Harmony | Brass | **61** | Brass Section |

### 5.1 Add/Subtract Instruments & Doubling

- **Melody Doubling (`ma_orch_plus_minus`):**
  - $< 0.4$: Solo Strings (Ch 0).
  - $0.4 \dots 0.8$: Strings + Woodwinds doubling (Ch 0, Ch 2).
  - $\ge 0.8$: Tutti Strings + Woodwinds + Brass Section (Ch 0, Ch 2, Ch 3).
- **Harmony Registration (`ha_register_ins`) & Density (`ha_ins_plus_minus`):**
  - Hierarchical registration levels: Level 1.0 (Piano), Level 2.0 (Piano + Strings), Level 3.0 (Piano + Strings + Woodwinds), Level 4.0 (Tutti).
  - Density scaled continuously via `ha_ins_plus_minus`.

### 5.2 Switch Instruments & Acoustic CC Staging

Dispatches program changes for all 8 orchestral channels plus Channel 9 (`(9, 48)`), and continuously maintains concert hall acoustic balance:
- **CC64 (Sustain)**: Value 127 on Piano channels (Ch 1 and Ch 5).
- **CC7 (Volume)** & **CC10 (Pan)**: Establishes realistic orchestral stereo placement (Strings left, Piano center-left, Drums center, Woodwinds center-right, Brass right).
- **CC91 (Reverb)**: Concert hall reverb send balance.
- **CC11 (Expression)**: Continuous dynamic expression swells driven by layer weight interpolation.

### 5.3 Range Enforcement & Octave Transposition

Enforces instrument pitch range constraints across global ranges (`MELODY_RANGE`, `HARMONY_RANGE`) and family bounds (`FAMILY_RANGES`). Out-of-bounds notes are transposed by octaves ($\pm 12$ semitones) until they land within the instrument's playable range, preserving harmonic pitch identity.

### Output

A combined **MIDI stream** with explicit instrument channel assignments, sent to the MIDI port.

---

## Final Output — MIDI Output & Audio Synthesis

Both output streams are routed to MIDI ports (virtual loopback, DAWs) or directly rendered via native embedded FluidSynth (`--sf2`):

| Stream | Source | Content | Channel Assignment |
|---|---|---|---|
| Main Orchestral Stream | Orchestration Agent (OA) | Melody + Harmony across 4 instrumental families | Channels 0–7 (Strings, Piano, Woodwinds, Brass) |
| Percussion Stream | Percussion Agent (PA) | Cinematic Concert Percussion (Gran Cassa, Timpani, Snare, Cymbals) | Channel 9 (General MIDI Orchestra Kit, Program 48) |

---

## Complete Data Flow

```
1. Composer sets Presets A/B/C/D and base_seed
2. Game variable / XY pad position → Preset Interpolator
   → continuous parameter vectors → all agents (continuously)
3. base_seed → Seeded Phrase Generator
   → monitors HA Chord Pool #
   → when Pool == 1: broadcasts new seed → all agents
   → when Pool != 1: keeps current seed
4. Play/Stop → Clock
   → Count Loop pulses (0 … loop×grain−1) → all agents
5. Count Loop + parameter vector + seed:
   → MA generates rhythm, velocity, pitch, MIDI events → OA
   → HA generates rhythm, velocity, chords, MIDI events → OA
     HA also publishes: Chord Pool #, current harmony pitches
   → PA generates per-instrument patterns + ratchet → MIDI port
6. OA manages instruments, ranges, switching → MIDI port
7. MIDI port → external synthesizers / DAW
```

---

## Design Constraints & Implementation Guidance

| Constraint | Rationale |
|---|---|
| Clock is the single time authority | Prevents drift; all agents schedule as Count Loop indices |
| Seeds are distributed atomically at loop boundaries | Ensures all agents start new motif variants simultaneously |
| Parameter updates are rate-limited relative to the Clock | Avoids excessive parameter churn that would disrupt phrase structure |
| Discrete parameters (instrument programs, modes) change only at phrase boundaries | Prevents mid-phrase timbral jumps or MIDI re-trigger artifacts |
| Agents are designed to be mostly stateless between loops | Relies on Clock and Seed for global continuity; local state (pattern counters, ratchet queues) is permitted for short-term behaviour only |
| Agents expose simple parameter hooks | Allows the interpolator to influence behaviour without deep coupling |
| Percussion Agent bypasses the Orchestration Agent | PA outputs directly to MIDI port; OA handles only melodic/harmonic content |
| Balance between real-time responsiveness and phrase integrity | Some parameters quantize to phrase/measure boundaries; direct continuous control is an ongoing design challenge |

---

## Module File Mapping (Implementation Reference)

| Module | File(s) |
|---|---|
| Preset Interpolator | `core/preset_interpolator.py` |
| Seeded Phrase Generator | `core/seeded_phrase_generator.py` |
| Clock & timing | `core/clock.py`, `core/scheduler.py` |
| MIDI I/O & routing | `core/midi_io.py`, `core/midi_events.py`, `core/routing.py` |
| Melody Agent | `modules/melody_agent.py` |
| Harmony Agent | `modules/harmony_agent.py` |
| Percussion Agent | `modules/percussion_agent.py` |
| Orchestration Agent | `modules/orchestrator_agent.py` |

> File paths are implementation-defined and may evolve. The module boundaries above are authoritative; the file paths are not.

---

## Known Limitations & Future Work
*(From paper § 4 Discussion)*

- **Western tonal bias:** PAMG primarily produces western tonal orchestral scores. Adapting to other styles (e.g., EDM) requires significant algorithmic and instrument management changes.
- **Real-time vs phrase integrity:** Immediate parameter changes can disrupt musical phrasing tied to rhythmic structures. Phrasing quantization partially mitigates this but the balance remains an open design challenge.
- **Parameter resolution:** Using full MIDI ranges for certain parameters may produce no perceptible change or abrupt shifts. Gradual transitions and phrasing quantization partially address this.
- **Composer integration:** Aligning PAMG with a composer's existing aesthetic (potentially via Markov chains or ML analysis of existing music) is future work.
- **Sample / timbre management:** Licensing and idiomatic textures for sample-based timbres may require new sample management or re-synthesis approaches.
- **Test validity:** The preliminary user study (n=18, 10–20 min gameplay) was insufficient to distinguish novelty effects from genuine music quality preference. A larger sample, priming gameplay, and longer sessions are recommended for future evaluation.