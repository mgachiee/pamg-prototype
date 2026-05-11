
# PAMG Prototype

A compact agent-driven MIDI sequencer prototype that generates melodic, harmonic, and percussion events and outputs them as live MIDI messages (using `mido` with `python-rtmidi`). The system is built for experimentation and routes MIDI to virtual ports (e.g., loopMIDI) so you can receive the output in a DAW.

## Reference

This prototype is based on and inspired by the referenced study:

https://dl.acm.org/doi/epdf/10.1145/3677996.3678291

Please cite or reference the paper when using this prototype in academic or published work.

## Quick start

Prerequisites
- Python 3.9+ installed
- Windows users: loopMIDI (or another virtual MIDI driver) to create virtual MIDI ports

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

Create virtual MIDI ports (Windows + loopMIDI)
1. Download and install loopMIDI (e.g., loopMIDI by Tobias Erichsen).
2. Open loopMIDI and click `+` to create new ports.
3. Create ports named to match the defaults in the project (or change them in configuration):
	 - `Melody 1`
	 - `Drums 2`
	 - (optional) `Clock 0` — useful for `midi_monitor.py`
4. In your DAW, enable the corresponding loopMIDI ports as MIDI inputs so the DAW can receive from this app.

## Running

Start the sequencer (sends MIDI to configured output ports):

```bash
python main.py
```

- `main.py` uses `run_clock(...)` with example parameters — edit `main.py` to change tempo / loop size / grain.
- Stop the process with Ctrl+C.

## GUI (Tkinter)

Launch the control panel (runs the async clock in the background):

```bash
python pamg_gui.py
```

- Includes Start/Stop, tempo/loop/grain inputs, base seed, X/Y sliders,
	a state monitor, and a live console output panel.
- Uses the same routing and port settings from
	[src/core/configs.py](src/core/configs.py).

Monitor an input port (simple test script):

```bash
python midi_monitor.py
```

- Edit the `PORT_NAME` in `midi_monitor.py` to match your loopMIDI input (default `'Clock 0'`).

## Configuration

- Routing and port names: edit [src/core/configs.py](src/core/configs.py)
	- `ROUTING_MODE`: `RoutingType.split_ports` (default) or `RoutingType.single_port`
	- `MELODY_PORT_NAME`, `DRUM_PORT_NAME`, `SINGLE_PORT_NAME`: names that must match your loopMIDI/DAW ports
	- `DEBUG_MIDI`: set to `True` to enable verbose MIDI debug logging

- In `split_ports` mode, both `MELODY_PORT_NAME` and `DRUM_PORT_NAME` must be available; otherwise the app raises an error at startup.

## Project structure (key files)

- [main.py](main.py): example runner — calls `run_clock(...)`.
- [midi_monitor.py](midi_monitor.py): tiny script to listen to a named input port.
- [src/core/midi_io.py](src/core/midi_io.py): port discovery/open/close helper functions.
- [src/core/clock.py](src/core/clock.py): `run_clock()` — main real-time loop, queues, MIDI writers, scheduling.
- [src/core/midi_events.py](src/core/midi_events.py): `MidiEvent` dataclass and normalization.
- [src/core/players.py](src/core/players.py): async helpers to send `note_on` / `note_off` / chords / ratchets.
- [src/core/configs.py](src/core/configs.py): routing & port name defaults and `DEBUG_MIDI`.
- [src/core/routing.py](src/core/routing.py): routing enum (`single_port` / `split_ports`).
- [src/modules/melody_agent.py](src/modules/melody_agent.py): melody generation.
- [src/modules/percussion_agent.py](src/modules/percussion_agent.py): percussion/groove generator.
- [src/modules/harmony_agent.py](src/modules/harmony_agent.py): chord progression provider.

## Development notes & tips

- There is no CLI implemented; runtime parameters (tempo, loop size, grain) are set in `main.py`. For experiments, call `run_clock()` directly or add an argument parser.
- Debugging:
	- Set `DEBUG_MIDI = True` in [src/core/configs.py](src/core/configs.py) for verbose logging.
	- `open_midi_ports()` prints available output ports; ensure names match exactly.
- MIDI details:
	- Uses `mido` with `python-rtmidi` backend (see `requirements.txt`).
	- Melody defaults to MIDI channel 0; percussion uses channel 9 (GM drum channel).

## Notes / Next steps

- Add CLI flags for runtime parameters and port overrides.
- Add a small health-check that lists available ports and gives clearer errors.
- Optionally add tests and CI for packaging.

---

If you'd like, I can also (A) add CLI argument parsing to `main.py`, or (B) prepare a short checklist for connecting a specific DAW (e.g., Ableton Live) to loopMIDI ports.

