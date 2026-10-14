# TCP Socket Server & Game Engine Integration

**Module:** `src/core/tcp_server.py`  
**Packet Handler:** `src/core/packet_handler.py`  
**State container:** `src/models/game_state.py`  
**Architecture stage:** Real-Time External Game Engine Interface

---

## Overview

The PAMG TCP Socket Server allows external game engines (such as Unreal Engine, Unity, Godot, or custom game clients) to stream live runtime telemetry and lifecycle commands to the PAMG engine in real time. It enables adaptive musical transitions based on game events, player affect, and scene changes.

Communication occurs over standard TCP using **newline-delimited JSON** (`\n`), with low-latency `TCP_NODELAY` enabled.

---

## Network Architecture

```
┌─────────────────────────────────┐
│ External Game Engine (Unreal /  │
│ Unity / Godot / Custom Client)  │
└────────────────┬────────────────┘
                 │ TCP Socket (127.0.0.1:9000)
                 │ Line-delimited JSON packets
                 ▼
┌─────────────────────────────────┐
│   src/core/tcp_server.py        │
│   (asyncio.start_server)        │
│   TCP_NODELAY, sidecar lifecycle│
└────────────────┬────────────────┘
                 │ raw packet (dict)
                 ▼
┌─────────────────────────────────┐
│   src/core/packet_handler.py    │
│   (PacketHandler dispatch)      │
│   handshake, telemetry, pause,  │
│   resume, reset, status, shut.  │
└────────────────┬────────────────┘
                 │ thread-safe / async state mutation
                 ▼
┌─────────────────────────────────┐
│   src/models/game_state.py      │
│   (shared GameState instance)   │
└────────────────┬────────────────┘
                 │ sampled per tick / loop boundary
                 ▼
┌─────────────────────────────────┐
│   src/core/clock.py (run_clock) │
│   - Instantaneous tempo change  │
│   - Direct XY interpolation     │
│   - Boundary structural update  │
│   - Dynamic Seed re-init        │
└─────────────────────────────────┘
```

---

## Action-Based Protocol Specification

Each message sent by the game client must be a valid JSON object followed by a newline character (`\n`).

### 1. `handshake`
Initiates a new session and confirms engine readiness.
```json
{"action": "handshake", "sidecar": true}
```
**Response:**
```json
{"status": "ready", "engine_state": "ready", "measure": 0, "current_step": 0, "sidecar": true}
```

---

### 2. `telemetry`
Transmits live game state, affective Valence/Arousal coordinates, or meter configurations.

```json
{
  "action": "telemetry",
  "valence": 0.8,
  "arousal": -0.4,
  "tempo": 120,
  "macro_state": {
    "music_config": {
      "time_signature": "6/4"
    }
  }
}
```

**Supported Telemetry Fields:**
* `valence` (float): Valence in `[-1.0, 1.0]` or `[0.0, 1.0]`. Automatically maps to `x`.
* `arousal` (float): Arousal in `[-1.0, 1.0]` or `[0.0, 1.0]`. Automatically maps to `y`.
* `x` / `y` (float): Direct normalized `[0.0, 1.0]` XY Pad coordinates.
* `tempo` / `bpm` (float): Updates tempo in BPM.
* `time_signature` (str): One of the 4 standard meters (`"4/4"`, `"3/4"`, `"6/8"`, `"6/4"`). Automatically calculates `loop_size` and `grain`.
* `seed` (int): Re-seeds the phrase generator.
* `health` / `enemies` (float): Fallback variables used if `valence`/`arousal` are omitted.

**Response:**
```json
{
  "status": "ok",
  "message": "Telemetry data ingested successfully.",
  "measure": 2,
  "step_in_measure": 8,
  "current_step": 40,
  "x": 0.9,
  "y": 0.3,
  "tempo": 120.0,
  "seed": 42
}
```

---

### 3. `pause` and `resume`
Controls live music playback during menus or game pauses.
* Pause: `{"action": "pause"}` $\to$ `{"status": "paused", "engine_state": "paused"}`
* Resume: `{"action": "resume"}` $\to$ `{"status": "resumed", "engine_state": "running"}`

---

### 4. `status` (or `query`)
Reports live engine position, playback state, and current parameters.
* Request: `{"action": "status"}`
* Response:
  ```json
  {
    "status": "ok",
    "engine_state": "running",
    "measure": 3,
    "step_in_measure": 4,
    "current_step": 52,
    "bpm": 120.0,
    "time_signature": "4/4",
    "x": 0.9,
    "y": 0.3
  }
  ```

---

### 5. `reset`
Resets the session state back to defaults.
* Request: `{"action": "reset"}`
* Response: `{"status": "ok", "message": "Engine reset successfully."}`

---

### 6. `shutdown`
Gracefully signals the server process to stop and terminate.
* Request: `{"action": "shutdown"}`
* Response: `{"status": "shutting_down", "message": "PAMG server shutting down gracefully."}`

---

## Backward Compatibility (Flat Payloads)
The server also accepts legacy flat JSON objects without an `"action"` key (e.g. `{"x": 0.8, "y": 0.2, "tempo": 130}`).

---

## Running PAMG with the TCP Server

Launch PAMG with TCP server and embedded FluidSynth:

```powershell
python main.py --tcp --tcp-port 9000 --sf2 "path/to/soundfont.sf2" --sidecar
```

* `--tcp`: Activates the live TCP server.
* `--tcp-port 9000`: Specifies port (default 9000).
* `--sidecar`: Automatically terminates the server process when the game client disconnects.
* `--audio-driver`: Optionally override the auto-detected audio driver (`wasapi`, `dsound`, `pulseaudio`, `coreaudio`).
