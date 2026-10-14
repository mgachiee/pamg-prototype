# Seeded Phrase Generator

**Module:** `core/seeded_phrase_generator.py`  
**Architecture stage:** Stage 1 — Global Control & Parameter Input

---

## Overview

The `SeededPhraseGenerator` is the motif management sub-system within Stage 1. Its sole responsibility is deciding *when* to issue a new integer seed to the Agent Network and *what* that seed value should be.

Because every agent (Harmony, Melody, Percussion, Orchestration) uses the same shared seed for its internal random generators, a seed change is effectively a **phrase event** — all agents simultaneously begin generating a new, mutually consistent musical variation. The generator therefore acts as a global synchronisation signal rather than just a number source.

---

## Architecture Context

```
User-provided base_seed
        │
        ▼
 SeededPhraseGenerator  ◄──── Harmony Agent: current_chord_pool
        │                ◄──── Interpolator / config: phrase_length
        │
        └─► updated seed ──► broadcast to all agents
                               (Harmony, Melody, Percussion, Orchestration)
```

See `system_architecture.md § Stage 1` ("Seeded Phrase Generator — Motif Management") for the broader data-flow picture.

---

## Two Operating Modes

The generator's entire behaviour is determined by the single value of `base_seed` passed at construction.

### Deterministic Mode (`base_seed != 0`)

Seeds are derived from the user-supplied `base_seed` using a seeded pseudo-random number generator. Given the same `base_seed` and `phrase_length`, the sequence of seeds produced over a session is fully **reproducible** — useful for composed or rehearsed pieces where the composer wants consistent musical variations night after night.

A new seed is only issued when the Harmony Agent signals **Chord Pool == 1**. All other chord pool changes reuse the existing seed, keeping agents aligned to the current phrase.

### Improvisation Mode (`base_seed == 0`)

Seeds are drawn from OS-level entropy (`random.SystemRandom`) on **every** chord change, ignoring `base_seed` and `phrase_length` entirely. This produces spontaneous, non-repeating variations — intended for live performance contexts where the composer wants the system to "play freely."

| Property | Deterministic (`base_seed != 0`) | Improvisation (`base_seed == 0`) |
|---|---|---|
| Reproducible? | ✅ Yes | ❌ No |
| Gated on Chord Pool 1? | ✅ Yes | ❌ No (fires every change) |
| Respects `phrase_length`? | ✅ Yes (scales offset) | ❌ No |
| RNG source | `random.Random(base_seed)` | `random.SystemRandom()` |

---

## Chord Pool Gating (Deterministic Mode)

The seed-update decision gate is taken directly from Duarte's PAMG fig. 7:

```
process_chord_change() called
         │
    improvisation mode?
    ┌──── Yes ────┬──── No ────────────────────┐
    ▼             │                            │
OS-entropy        Chord Pool == 1?             │
new seed          ┌─── Yes ───┬─── No ──┐      │
                  ▼           ▼         │      │
           compute new    return        │      │
           seed           current_seed  │      │
           (base +        (no change)   │      │
            offset)                     │      │
                  └───────────┘         │      │
                                        └──────┘
```

**Why Chord Pool 1?**  
Pool 1 is the "home" chord group — harmonically, the start of a new phrase. Issuing a new seed here means all agents begin their new motif variation at the same musically meaningful moment, preserving phrase structure.

**Why not update on other chord pools?**  
Changing the seed mid-phrase would cause the melody, harmony, and percussion agents to independently "reset" to unrelated random states, destroying the motivic coherence of the current phrase.

---

## Seed Derivation Formula (Deterministic Mode)

When `current_chord_pool == 1`:

```
random_offset = rng.randint(1, 1000) × phrase_length
new_seed      = base_seed + random_offset
```

After computing `new_seed`, the internal RNG is **re-seeded** with `new_seed`:

```python
self._rng.seed(self.current_seed)
```

This ensures subsequent Pool-1 events derive their offsets from a different, but reproducible, position in the pseudo-random sequence — producing musically diverse phrases without ever revisiting the same offset pattern.

### Effect of `phrase_length` on seed spacing

`phrase_length` scales the random offset, so longer phrases produce larger seed jumps:

| `phrase_length` | Offset range | Effect |
|---|---|---|
| 1 measure | `[1, 1000]` | Tightly clustered seeds; subtle variation |
| 4 measures | `[4, 4000]` | Moderate spacing; clearer phrase contrast |
| 8 measures | `[8, 8000]` | Widely spaced seeds; pronounced variation |

---

## RNG Architecture & Dual Seeds (§7.1, S2 §3.2.2)

The dissertation specification requires that reseeding drives **both pitch and rhythm seeds independently**. The generator therefore maintains independent RNG instances:

| Attribute | Type | Mode | Purpose |
|---|---|---|---|
| `_rng` | `random.Random` | Both | Drives pitch seed offset computation in deterministic mode. |
| `_rhythm_rng` | `random.Random` | Both | Drives rhythm seed offset computation in deterministic mode. |
| `_system_rng` | `random.SystemRandom` | Improvisation only | OS-entropy source; produces unpredictable pitch and rhythm seeds. |

---

## Public API

### `__init__(base_seed: int)`

Initialise the generator and select operating mode.

```python
# Deterministic mode
generator = SeededPhraseGenerator(base_seed=42)

# Improvisation mode
generator = SeededPhraseGenerator(base_seed=0)
```

---

### `process_chord_change(current_chord_pool, phrase_length) → SeedState`

Evaluate whether a new seed should be issued and return the active `SeedState`.

| Arg | Type | Description |
|---|---|---|
| `current_chord_pool` | `int` | Harmony Agent's current chord pool. `1` = home group; gates seed updates in deterministic mode. |
| `phrase_length` | `int` | Phrase length in measures. Scales the random offset. Clamped internally to `≥ 1`. |

**Returns:** An atomic `SeedState(base_seed, current_seed, rhythm_seed)`. Can also be unpacked as `pitch_seed, rhythm_seed` or cast to `int`.

---

## Usage Pattern (Clock Broadcast)

```python
# core/clock.py
generator = SeededPhraseGenerator(base_seed=base_seed)

seed_state = generator.process_chord_change(
    harmony_agent.get_chord_pool(), phrase_length
)
if seed_state != prev_seed_state:
    melody_agent.update_params(
        seed=seed_state.current_seed,
        rhythm_seed=seed_state.rhythm_seed,
        seed_state=seed_state,
    )
    percussion_agent.update_params(
        seed=seed_state.current_seed,
        rhythm_seed=seed_state.rhythm_seed,
        seed_state=seed_state,
    )
    harmony_agent.update_params(
        seed=seed_state.current_seed,
        rhythm_seed=seed_state.rhythm_seed,
        seed_state=seed_state,
    )
    orchestrator_agent.update_params(seed=seed_state.current_seed)
```

---

## Relationship to Other Stage 1 Modules

| Module | Role | Interaction with SeededPhraseGenerator |
|---|---|---|
| `MultiParameterPresetInterpolator` | Continuous parameter vectors | Provides `phrase_length` from interpolated parameters |
| `SeededPhraseGenerator` | Seed / motif management | Consumes `phrase_length`; outputs `SeedState` |
| `HarmonyAgent` | Chord progressions | Provides `current_chord_pool` on each chord change |
| All agents | Music generation | Consume `SeedState` (pitch and rhythm seeds) to produce consistent variations |

---

## Dependencies

| Import | Role |
|---|---|
| `random.Random` | Seedable pseudo-random generator for deterministic pitch and rhythm offset computation |
| `random.SystemRandom` | OS-entropy source for improvisation mode (non-replayable) |
| `src.models.seed_state.SeedState` | Shared atomic container for base, pitch, and rhythm seeds |
| `src.core.logger.Logger` | Structured logger; records mode, seed values, and offsets at INFO level |