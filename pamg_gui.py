"""
Tkinter GUI to control the PAMG real-time clock.

Provides start/stop controls, game-variable sliders, and a live parameter
monitor so the system can be tested without a game runtime.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Coroutine, Optional, Tuple

from src.core import clock as clock_module
from src.core.configs import (
    DEBUG_MIDI,
    DRUM_PORT_NAME,
    MAX_ENEMIES,
    MAX_HEALTH,
    MELODY_PORT_NAME,
    PRESET_A,
    PRESET_B,
    PRESET_C,
    PRESET_D,
    ROUTING_MODE,
    SINGLE_PORT_NAME,
)
from src.core.preset_interpolator import MultiParameterPresetInterpolator


class SharedGameState:
    """Thread-safe holder for game-state values used by the clock.

    This object is shared between the UI thread and the async clock thread.
    """

    def __init__(self, health: float, enemies: float) -> None:
        """Initialize the shared game-state container.

        Args:
            health (float): Initial player health value.
            enemies (float): Initial enemy count value.
        """
        self._lock = threading.Lock()
        self._health = health
        self._enemies = enemies

    def set_values(self, health: float, enemies: float) -> None:
        """Update the game-state values atomically.

        Args:
            health (float): New player health value.
            enemies (float): New enemy count value.
        """
        with self._lock:
            self._health = health
            self._enemies = enemies

    def get_values(self) -> Tuple[float, float]:
        """Return the latest (health, enemies) values.

        Returns:
            Tuple[float, float]: Current health and enemy count.
        """
        with self._lock:
            return self._health, self._enemies


class QueueLoggingHandler(logging.Handler):
    """Logging handler that writes formatted records into a queue."""

    def __init__(self, message_queue: queue.Queue[str]) -> None:
        """Initialize the handler with the target queue.

        Args:
            message_queue (queue.Queue[str]): Queue that receives log strings.
        """
        super().__init__()
        self._message_queue = message_queue

    def emit(self, record: logging.LogRecord) -> None:
        """Format and enqueue a log record.

        Args:
            record (logging.LogRecord): Log record to format and enqueue.
        """
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()
        self._message_queue.put(message + "\n")


class StreamRedirector:
    """Redirects stdout/stderr writes into a queue."""

    def __init__(self, message_queue: queue.Queue[str]) -> None:
        """Initialize the redirector with the target queue.

        Args:
            message_queue (queue.Queue[str]): Queue receiving stream data.
        """
        self._message_queue = message_queue

    def write(self, message: str) -> int:
        """Write a string into the queue.

        Args:
            message (str): Text to enqueue.

        Returns:
            int: Length of the written message.
        """
        if message:
            self._message_queue.put(message)
        return len(message)

    def flush(self) -> None:
        """No-op flush to satisfy the stream API."""
        return None


class AsyncClockRunner:
    """Runs the PAMG clock in a background asyncio loop."""

    def __init__(self) -> None:
        """Initialize loop and task tracking state."""
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._task: Optional[asyncio.Task] = None
        self._task_lock = threading.Lock()
        self._ready = threading.Event()

    def start(self) -> None:
        """Start the background asyncio loop if not running."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop,
            name="pamg-async-loop",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=1.0)

    def _run_loop(self) -> None:
        """Create and run the private asyncio event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        loop.run_forever()
        loop.close()

    def start_clock(
        self,
        coro_factory: Callable[[], Coroutine[Any, Any, None]],
    ) -> None:
        """Schedule a new clock task if none is running.

        Args:
            coro_factory (Callable[[], Coroutine[Any, Any, None]]): Factory
                that builds the clock coroutine.
        """
        self.start()
        if self._loop is None:
            return

        def _create_task() -> None:
            with self._task_lock:
                if self._task and not self._task.done():
                    return
                self._task = self._loop.create_task(coro_factory())
                self._task.add_done_callback(self._on_task_done)

        self._loop.call_soon_threadsafe(_create_task)

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Release the stored task and log any unexpected errors.

        Args:
            task (asyncio.Task): Completed clock task.
        """
        with self._task_lock:
            self._task = None
        try:
            task.result()
        except asyncio.CancelledError:
            return
        except Exception:
            logging.getLogger(__name__).exception("Clock task failed")

    def stop_clock(self) -> None:
        """Cancel the running clock task if present."""
        if self._loop is None:
            return

        def _cancel_task() -> None:
            with self._task_lock:
                if self._task and not self._task.done():
                    self._task.cancel()

        self._loop.call_soon_threadsafe(_cancel_task)

    def shutdown(self) -> None:
        """Stop the clock task and close the background loop."""
        self.stop_clock()
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._loop = None
        self._thread = None
        self._task = None


class PamgGui:
    """Tkinter GUI for PAMG control and monitoring.

    This class builds the UI, manages a background clock runner, and keeps
    the state monitor in sync with the current interpolated parameters.
    """

    def __init__(self, root: tk.Tk) -> None:
        """Initialize the UI and wire background services.

        Args:
            root (tk.Tk): Root Tkinter window.
        """
        self._root = root
        self._root.title("PAMG Control Panel")

        self._runner = AsyncClockRunner()
        self._log_queue: queue.Queue[str] = queue.Queue()
        self._state = SharedGameState(MAX_HEALTH, 0.0)
        self._interpolator = MultiParameterPresetInterpolator(
            PRESET_A,
            PRESET_B,
            PRESET_C,
            PRESET_D,
            smoothing_time=0.12,
        )

        self._tempo_var = tk.IntVar(value=120)
        self._loop_size_var = tk.IntVar(value=6)
        self._grain_var = tk.IntVar(value=2)
        self._base_seed_var = tk.IntVar(value=42)
        self._game_x_var = tk.DoubleVar(value=MAX_HEALTH)
        self._game_y_var = tk.DoubleVar(value=0.0)
        self._game_x_label_var = tk.StringVar(
            value=f"{MAX_HEALTH:.1f}",
        )
        self._game_y_label_var = tk.StringVar(value="0.0")
        self._is_running = False

        self._console_text: Optional[tk.Text] = None
        self._state_text: Optional[tk.Text] = None

        self._build_ui()
        self._configure_logging()
        self._poll_logs()
        self._update_state_monitor()
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _configure_logging(self) -> None:
        """Redirect logging and stdout/stderr into the GUI console."""
        # Reset handlers so the GUI owns logging output.
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

        handler = QueueLoggingHandler(self._log_queue)
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] %(levelname)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        root_logger.addHandler(handler)

        sys.stdout = StreamRedirector(self._log_queue)
        sys.stderr = StreamRedirector(self._log_queue)

    def _build_ui(self) -> None:
        """Build and layout the Tkinter widgets."""
        main_frame = ttk.Frame(self._root, padding=10)
        main_frame.grid(row=0, column=0, sticky="nsew")

        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

        # Master clock controls.
        master_frame = ttk.LabelFrame(
            main_frame,
            text="Master Clock Controls",
            padding=10,
        )
        master_frame.grid(row=0, column=0, sticky="ew")

        start_button = ttk.Button(
            master_frame,
            text="Start",
            command=self._toggle_start_stop,
        )
        start_button.grid(row=0, column=0, padx=(0, 12), pady=4)
        self._start_stop_button = start_button

        ttk.Label(master_frame, text="Tempo (BPM)").grid(
            row=1,
            column=0,
            sticky="w",
            pady=4,
        )
        ttk.Spinbox(
            master_frame,
            from_=40,
            to=260,
            textvariable=self._tempo_var,
            width=8,
        ).grid(row=1, column=1, sticky="w", pady=4)

        ttk.Label(master_frame, text="Loop Size (Beats)").grid(
            row=2,
            column=0,
            sticky="w",
            pady=4,
        )
        ttk.Spinbox(
            master_frame,
            from_=1,
            to=16,
            textvariable=self._loop_size_var,
            width=8,
        ).grid(row=2, column=1, sticky="w", pady=4)

        ttk.Label(master_frame, text="Grain (Subdivisions)").grid(
            row=3,
            column=0,
            sticky="w",
            pady=4,
        )
        ttk.Spinbox(
            master_frame,
            from_=1,
            to=16,
            textvariable=self._grain_var,
            width=8,
        ).grid(row=3, column=1, sticky="w", pady=4)

        # Global settings (base seed, routing, etc.).
        system_frame = ttk.LabelFrame(
            main_frame,
            text="Global System Controls",
            padding=10,
        )
        system_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        ttk.Label(system_frame, text="Base Seed").grid(
            row=0,
            column=0,
            sticky="w",
            pady=4,
        )
        ttk.Spinbox(
            system_frame,
            from_=0,
            to=9999,
            textvariable=self._base_seed_var,
            width=10,
        ).grid(row=0, column=1, sticky="w", pady=4)

        # Game variable sliders and state monitor.
        game_frame = ttk.LabelFrame(
            main_frame,
            text="Game Variable Simulation",
            padding=10,
        )
        game_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        game_frame.columnconfigure(1, weight=1)

        sliders_frame = ttk.Frame(game_frame)
        sliders_frame.grid(row=0, column=0, sticky="nw")

        tk.Label(sliders_frame, text="Game Variable X (Health)").grid(
            row=0,
            column=0,
            sticky="w",
        )
        tk.Scale(
            sliders_frame,
            from_=0.0,
            to=float(MAX_HEALTH),
            resolution=0.5,
            orient="horizontal",
            variable=self._game_x_var,
            command=self._on_game_var_change,
            length=260,
        ).grid(row=1, column=0, sticky="ew")
        ttk.Label(sliders_frame, textvariable=self._game_x_label_var).grid(
            row=1,
            column=1,
            padx=(8, 0),
        )

        tk.Label(sliders_frame, text="Game Variable Y (Enemies)").grid(
            row=2,
            column=0,
            sticky="w",
            pady=(8, 0),
        )
        tk.Scale(
            sliders_frame,
            from_=0.0,
            to=float(MAX_ENEMIES),
            resolution=0.5,
            orient="horizontal",
            variable=self._game_y_var,
            command=self._on_game_var_change,
            length=260,
        ).grid(row=3, column=0, sticky="ew")
        ttk.Label(sliders_frame, textvariable=self._game_y_label_var).grid(
            row=3,
            column=1,
            padx=(8, 0),
        )

        state_frame = ttk.Frame(game_frame)
        state_frame.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        ttk.Label(state_frame, text="State Monitor").grid(
            row=0,
            column=0,
            sticky="w",
        )

        state_text = tk.Text(
            state_frame,
            height=10,
            width=50,
            wrap="none",
            font=("Courier New", 10),
        )
        state_text.grid(row=1, column=0, sticky="nsew")
        state_text.configure(state="disabled")
        self._state_text = state_text

        # Console output panel.
        console_frame = ttk.LabelFrame(
            main_frame,
            text="Console Output",
            padding=10,
        )
        console_frame.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
        console_frame.columnconfigure(0, weight=1)
        console_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

        console_text = tk.Text(
            console_frame,
            height=12,
            wrap="word",
            font=("Courier New", 10),
        )
        console_text.grid(row=0, column=0, sticky="nsew")
        console_text.configure(state="disabled")
        self._console_text = console_text

        scrollbar = ttk.Scrollbar(
            console_frame,
            orient="vertical",
            command=console_text.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        console_text.configure(yscrollcommand=scrollbar.set)

    def _pulse_duration(self) -> float:
        """Compute pulse duration from the current tempo and grain.

        Returns:
            float: Duration of a pulse in seconds.
        """
        tempo = max(1, int(self._tempo_var.get()))
        grain = max(1, int(self._grain_var.get()))
        return 60.0 / (tempo * grain)

    def _toggle_start_stop(self) -> None:
        """Start or stop the clock depending on the current state."""
        if self._is_running:
            self._runner.stop_clock()
            self._is_running = False
            self._start_stop_button.configure(text="Start")
            logging.info("Clock stop requested")
            return

        tempo = int(self._tempo_var.get())
        loop_size = int(self._loop_size_var.get())
        grain = int(self._grain_var.get())
        base_seed = int(self._base_seed_var.get())

        def _game_state_callback() -> Tuple[float, float]:
            return self._state.get_values()

        def _coro_factory() -> Coroutine[Any, Any, None]:
            return clock_module.run_clock(
                tempo=tempo,
                loop_size=loop_size,
                grain=grain,
                is_playing=True,
                routing_mode=ROUTING_MODE,
                single_port_name=SINGLE_PORT_NAME,
                melody_port_name=MELODY_PORT_NAME,
                drum_port_name=DRUM_PORT_NAME,
                debug_midi=DEBUG_MIDI,
                game_state_callback=_game_state_callback,
                base_seed=base_seed,
            )

        self._runner.start_clock(_coro_factory)
        self._is_running = True
        self._start_stop_button.configure(text="Stop")
        logging.info("Clock start requested")

    def _on_game_var_change(self, _value: str = "") -> None:
        """Handle slider changes and refresh the state monitor.

        Args:
            _value (str): Tkinter callback value (unused).
        """
        health = float(self._game_x_var.get())
        enemies = float(self._game_y_var.get())
        self._state.set_values(health, enemies)
        self._game_x_label_var.set(f"{health:.1f}")
        self._game_y_label_var.set(f"{enemies:.1f}")
        self._update_state_monitor()

    def _update_state_monitor(self) -> None:
        """Refresh the live state monitor panel."""
        if self._state_text is None:
            return

        health, enemies = self._state.get_values()
        x, y = clock_module.map_gamevars_to_xy(health, enemies)
        params = self._interpolator.update(
            x,
            y,
            self._pulse_duration(),
        )

        state = {
            "health": round(health, 2),
            "enemies": round(enemies, 2),
            "xy": {
                "x": round(x, 3),
                "y": round(y, 3),
            },
            "melody_pitch": [
                int(round(params.melody_pitch_low)),
                int(round(params.melody_pitch_high)),
            ],
            "melody_syncopation": round(params.melody_syncopation, 3),
            "drum_kick_prob": round(params.drum_kick_probability, 3),
            "harmony_tension": round(params.harmony_tension, 3),
            "phrase_length": int(round(params.seeded_phrase_length)),
        }

        self._state_text.configure(state="normal")
        self._state_text.delete("1.0", "end")
        self._state_text.insert("end", json.dumps(state, indent=2))
        self._state_text.configure(state="disabled")

    def _append_console(self, message: str) -> None:
        """Append a log message to the console widget.

        Args:
            message (str): Text to append.
        """
        if self._console_text is None:
            return
        self._console_text.configure(state="normal")
        self._console_text.insert("end", message)
        self._console_text.see("end")
        self._console_text.configure(state="disabled")

    def _poll_logs(self) -> None:
        """Drain queued log messages into the console widget."""
        while True:
            try:
                message = self._log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_console(message)
        self._root.after(50, self._poll_logs)

    def _on_close(self) -> None:
        """Handle window close by stopping background tasks."""
        self._runner.shutdown()
        self._root.destroy()


def main() -> None:
    """Launch the PAMG control panel GUI."""
    root = tk.Tk()
    PamgGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
