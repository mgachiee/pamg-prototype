# PAMG Prototype

A high-performance, agent-driven MIDI sequencer prototype designed for real-time generative music. The system produces melodic, harmonic, and percussion events that adapt dynamically to a global state (e.g., game variables like health and tension). It is built for seamless integration with DAWs via virtual MIDI ports (like loopMIDI).

## Key Features

*   **Multi-Agent Orchestration**: Discrete agents for Melody, Harmony, Percussion, and Orchestration work in tandem to produce cohesive musical output.
*   **Advanced Orchestrator (OA)**:
    *   **Musical Octave Transposition**: Ensures notes stay within instrument-specific ranges by shifting them by octaves rather than simple clipping.
    *   **Melody Doubling**: Simulates multiple performers by duplicating melody lines across multiple MIDI channels.
    *   **Intelligent Voice Distribution**: Automatically distributes chord tones and arpeggiated notes across multiple harmony instruments for rich orchestral textures.
    *   **Phrase-Bound Program Changes**: Manages MIDI instrument changes at phrase boundaries to maintain musical form.
*   **XY Pad Interpolation**: Real-time blending between four corner presets (Exploration, Combat, Tension, Chaotic) with temporal smoothing.
*   **High-Precision Timing**: An `asyncio`-driven clock that prevents drift and decouples MIDI output via asynchronous queues to eliminate jitter.
*   **Live State Monitoring**: Real-time broadcasting of the system's internal state (parameters, XY coordinates, game variables) to a monitor panel.

## Reference

This prototype is based on and inspired by the study:
[A Progressive-Adaptive Music Generator (PAMG)](https://dl.acm.org/doi/epdf/10.1145/3677996.3678291) (Duarte, A. E. L., 2024).

For details on the specific implementation rules and architectural refinements added to this prototype, see [Custom Implementations & Rules](.github/docs/custom_implementations.md).

## Quick Start

### Prerequisites
*   Python 3.9+
*   **Windows Users**: [loopMIDI](https://www.tobias-erichsen.de/software/loopmidi.html) to create virtual MIDI ports.
*   **DAW**: Ableton Live, Cakewalk, FL Studio, etc., to host your virtual instruments.

### Setup
1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
2.  Create virtual MIDI ports in loopMIDI (e.g., `Melody 1` and `Drums 2`).
3.  In your DAW, enable these ports as MIDI Inputs.

### Running
*   **Launch GUI Control Panel**:
    ```bash
    python pamg_gui.py
    ```
*   **Headless/CLI Mode**:
    ```bash
    python main.py
    ```

## Offline MIDI Dataset Generation

PAMG includes a tool for bulk generating MIDI files from the four corner presets. This is useful for creating datasets for training or for generating static musical assets.

*   **Generate Dataset**:
    ```bash
    python generate_dataset.py
    ```
    This will generate 25 MIDI files for each preset (A, B, C, D) and save them in the `dataset/` directory. Each file represents a unique seeded variation of the preset's musical character.

## Multi-Channel Configuration

PAMG supports sophisticated multi-instrument setups. Configuration is centralized in `src/core/configs.py`.

### Example Orchestral Setup
In `src/core/configs.py`, you can define an orchestra across 5 MIDI channels:
```python
MELODY_CHANNELS = [0, 1]      # MIDI Ch 1 (Violin) and Ch 2 (Flute doubling)
HARMONY_CHANNELS = [2, 3, 4]  # MIDI Ch 3 (Piano), Ch 4 (Strings), Ch 5 (Bass)

# Define instrument-specific ranges
FAMILY_RANGES = {
    "strings": (55, 96),
    "brass": (48, 84),
    "bass": (24, 48),
}

# Map channels to families for range enforcement
CHANNEL_FAMILIES = {
    0: "strings",
    3: "brass",
    4: "bass",
}
```

## Project Structure

*   `pamg_gui.py`: Tkinter-based control panel with XY pad and state monitor.
*   `src/core/clock.py`: The authoritative timing loop and agent coordinator.
*   `src/core/preset_interpolator.py`: High-performance bilinear blending for musical parameters.
*   `src/modules/orchestrator_agent.py`: Handles MIDI routing, doubling, and musical transposition.
*   `src/modules/harmony_agent.py`: Generates chord progressions and tagged voices for distribution.
*   `src/modules/melody_agent.py`: Stochastic melody generator based on tension and seeds.
*   `src/modules/percussion_agent.py`: Procedural drum pattern and groove generator.
*   `src/core/players.py`: Low-level asynchronous MIDI dispatching.

## Development & Debugging

*   **Verbose Logging**: Set `DEBUG_MIDI = True` in `src/core/configs.py` to see raw event dispatching in the console.
*   **Performance**: The core loop is optimized to minimize object allocation and garbage collection churn for real-time stability.
*   **Customization**: Adjust the corner presets in `src/core/configs.py` to change how the system responds to different tension levels.
