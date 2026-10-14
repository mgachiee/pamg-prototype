# PAMG System Revisions

This document tracks system-level extensions and infrastructural revisions applied to the baseline Progressive-Adaptive Music Generator (PAMG) architecture to facilitate real-time game engine integration, cross-platform audio synthesis, and modern development workflows.

> **Note on Musical & Generative Architecture:**  
> The 4x2 Orchestral Matrix, General MIDI Orchestra Kit percussion, crescendo rolls, tension-calibrated voicings, and preset behaviors reflect the actual musical design and behavior of the PAMG system as demonstrated in Duarte (2024). These core algorithmic behaviors are documented directly in the respective module specifications ([`system-architecture.md`](system-architecture.md), [`orchestrator_agent.md`](orchestrator_agent.md), [`percussion_agent.md`](percussion_agent.md), [`harmony_agent.md`](harmony_agent.md), [`melody_agent.md`](melody_agent.md)) and are part of the baseline reproduction rather than system extensions.

---

## 1. Real-Time Game Engine Integration (TCP Socket Server & Packet Handler)

To bridge the gap between the internal PAMG Python ecosystem and external game engines (such as Unity, Unreal, or Godot), we introduced a **Live TCP Socket Server with a Dedicated Packet Handler** (`src/core/tcp_server.py` and `src/core/packet_handler.py`).

- **Component:** `src/core/tcp_server.py`, `src/core/packet_handler.py`, `src/models/game_state.py`
- **Protocol:** Line-delimited JSON with action-based routing (`handshake`, `telemetry`, `pause`, `resume`, `stop`, `reset`, `status`/`query`, `shutdown`), plus backward compatibility for flat parameter payloads.
- **Affective Valence–Arousal Mapping:** Directly maps game engine `valence` and `arousal` into PAMG's XY pad coordinates $(x, y)$, automatically normalizing both $[-1.0, 1.0]$ and $[0.0, 1.0]$ inputs to Russell's circumplex quadrants:
  - Preset A `(0, 0)`: $-V, -A$ (Subdued / Somber)
  - Preset B `(1, 0)`: $+V, -A$ (Calm / Open)
  - Preset C `(0, 1)`: $-V, +A$ (Tense / Driving)
  - Preset D `(1, 1)`: $+V, +A$ (Energetic / Heroic)
- **Time Signature Ingestion:** Supports the 4 standard meters (`"4/4"`, `"3/4"`, `"6/8"`, `"6/4"`) received via `macro_state.music_config.time_signature`, automatically deducing `loop_size` and `grain` at loop boundaries.
- **Latency & Lifecycle:** Configures `TCP_NODELAY` (disabling Nagle's algorithm) for real-time game telemetry, supports client-directed `shutdown`, and `--sidecar` mode to auto-terminate when the game client disconnects.
- **Usage:** Run `python main.py --tcp --tcp-port 9000 [--sidecar]`.

---

## 2. Cross-Platform Embedded FluidSynth Rendering

While the theoretical PAMG baseline strictly scopes the generative architecture to output "MIDI streams" to an external "MIDI port" (relying on downstream DAWs or virtual loopback middleware like loopMIDI + FluidSynth), configuring virtual MIDI ports introduces friction across operating systems.

To resolve this, we introduced an **Embedded Native FluidSynth Renderer with Cross-Platform Driver Detection**.

- **Component:** `NativeFluidSynthPort` in `src/core/midi_io.py`, `src/utils/audio.py`
- **Purpose:** Bypass virtual MIDI loopback ports entirely and pipe MIDI events directly to an embedded FluidSynth subprocess.
- **Automatic Audio Drivers:**
  - **Windows:** `wasapi` (with fallback or `--audio-driver dsound`)
  - **Linux:** `pulseaudio` (or `alsa`)
  - **macOS (Darwin):** `coreaudio`
- **High-Resolution Scheduling:** Activates Windows multimedia timer (`timeBeginPeriod(1)`) via `use_highres_timer` for sub-millisecond scheduling precision.
- **Usage:** Run `python main.py --sf2 path/to/soundfont.sf2 [--audio-driver wasapi]`.

---

*Note: The generative engine and agent behaviors (Melody, Harmony, Percussion, Orchestration, and Preset Interpolation) adhere strictly to the baseline PAMG specifications and reference implementation as demonstrated in Duarte (2024).*

