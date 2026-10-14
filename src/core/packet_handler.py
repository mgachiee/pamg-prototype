"""
PacketHandler for incoming telemetry and lifecycle packets from the game client.
"""

from typing import Any, Dict
from src.core.logger import Logger
from src.models.game_state import GameState

logger = Logger()


class PacketHandler:
    """
    Handles incoming telemetry and lifecycle packets from the game client.
    Supports action-based routing: handshake, telemetry, pause, resume,
    stop, reset, status/query, and shutdown, as well as legacy flat payloads.
    """

    def __init__(self, state: GameState, sidecar_mode: bool = False):
        """
        Initialize PacketHandler.

        Args:
            state (GameState): Reference to the shared PAMG GameState instance.
            sidecar_mode (bool): Whether sidecar mode is active.
        """
        self.state = state
        self.sidecar_mode = sidecar_mode
        self.shutdown_requested: bool = False

    def handle_packet(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single JSON dictionary packet received over TCP.

        Args:
            packet (Dict[str, Any]): Parsed JSON payload.

        Returns:
            Dict[str, Any]: Response dictionary to serialize back to client.
        """
        action = packet.get("action")
        if action:
            handler = getattr(self, f"_handle_{action}", None)
            if callable(handler):
                return handler(packet)
            return {"status": "error", "message": f"Unknown action: {action}"}

        # Fallback for flat payloads without an explicit 'action' key
        return self._handle_flat_telemetry(packet)

    def _handle_handshake(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Acknowledge client handshake, reset session, and establish sidecar state.
        """
        logger.info("[PacketHandler] Handshake received. Resetting session.")
        self.state.reset()
        if packet.get("sidecar", False):
            self.sidecar_mode = True
            logger.info("[PacketHandler] Sidecar mode activated via handshake packet.")

        return {
            "status": "ready",
            "engine_state": "ready",
            "measure": self.state.measure,
            "current_step": self.state.current_step,
            "sidecar": self.sidecar_mode,
        }

    def _handle_telemetry(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingest telemetry updates: valence, arousal, macro_state (time signature, bpm),
        tempo, seed, or direct coordinates.
        """
        # 1. Valence / Arousal -> XY Pad mapping
        valence = packet.get("valence")
        arousal = packet.get("arousal")
        if valence is not None or arousal is not None:
            default_v = self.state.x if self.state.x is not None else 0.5
            default_a = self.state.y if self.state.y is not None else 0.5
            v = valence if valence is not None else default_v
            a = arousal if arousal is not None else default_a
            self.state.set_valence_arousal(v, a)

        # Direct x / y overrides
        if "x" in packet and packet["x"] is not None:
            self.state.x = max(0.0, min(1.0, float(packet["x"])))
        if "y" in packet and packet["y"] is not None:
            self.state.y = max(0.0, min(1.0, float(packet["y"])))

        # 2. MacroState / MusicConfig ingestion
        macro_state = packet.get("macro_state")
        if isinstance(macro_state, dict):
            music_cfg = macro_state.get("music_config")
            if isinstance(music_cfg, dict):
                if "time_signature" in music_cfg:
                    try:
                        self.state.set_time_signature(str(music_cfg["time_signature"]))
                    except ValueError as err:
                        return {"status": "error", "message": str(err)}
                bpm = music_cfg.get("bpm") or music_cfg.get("tempo")
                if bpm is not None and float(bpm) > 0:
                    self.state.tempo = float(bpm)

        # Direct time_signature in root packet
        if "time_signature" in packet and packet["time_signature"] is not None:
            try:
                self.state.set_time_signature(str(packet["time_signature"]))
            except ValueError as err:
                return {"status": "error", "message": str(err)}

        # Direct gameplay / engine parameters
        if "tempo" in packet and packet["tempo"] is not None:
            new_tempo = float(packet["tempo"])
            if new_tempo > 0:
                self.state.tempo = new_tempo

        if "seed" in packet and packet["seed"] is not None:
            self.state.base_seed = int(packet["seed"])
        elif "base_seed" in packet and packet["base_seed"] is not None:
            self.state.base_seed = int(packet["base_seed"])

        if "health" in packet and packet["health"] is not None:
            self.state.health = float(packet["health"])
        if "enemies" in packet and packet["enemies"] is not None:
            self.state.enemies = float(packet["enemies"])

        structure_changed = False
        if "loop_size" in packet and packet["loop_size"] is not None:
            new_loop = int(packet["loop_size"])
            if new_loop > 0 and new_loop != self.state.loop_size:
                self.state.loop_size = new_loop
                structure_changed = True

        if "grain" in packet and packet["grain"] is not None:
            new_grain = int(packet["grain"])
            if new_grain > 0 and new_grain != self.state.grain:
                self.state.grain = new_grain
                structure_changed = True

        if structure_changed:
            self.state.structure_dirty = True

        # Telemetry unpauses the engine if paused
        self.state.paused = False

        return {
            "status": "ok",
            "message": "Telemetry data ingested successfully.",
            "measure": self.state.measure,
            "step_in_measure": self.state.step_in_measure,
            "current_step": self.state.current_step,
            "x": self.state.x,
            "y": self.state.y,
            "tempo": self.state.tempo,
            "seed": self.state.base_seed,
        }

    def _handle_pause(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Pause the engine clock."""
        logger.info("[PacketHandler] Pause requested.")
        self.state.trigger_silence()
        return {"status": "paused", "engine_state": "paused"}

    def _handle_resume(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Resume playback."""
        logger.info("[PacketHandler] Resume requested.")
        self.state.paused = False
        return {"status": "resumed", "engine_state": "running"}

    def _handle_stop(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Stop and pause playback."""
        logger.info("[PacketHandler] Stop requested.")
        self.state.trigger_silence()
        return {"status": "stopped", "engine_state": "paused"}

    def _handle_reset(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Reset engine state to defaults."""
        logger.info("[PacketHandler] Reset requested.")
        self.state.trigger_silence()
        self.state.reset()
        return {
            "status": "ok",
            "message": "Engine reset successfully.",
            "measure": self.state.measure,
            "current_step": self.state.current_step,
        }


    def _handle_status(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Report live engine status."""
        return {
            "status": "ok",
            "engine_state": "paused" if self.state.paused else "running",
            "measure": self.state.measure,
            "step_in_measure": self.state.step_in_measure,
            "current_step": self.state.current_step,
            "bpm": self.state.tempo,
            "time_signature": self.state.time_signature,
            "x": self.state.x,
            "y": self.state.y,
        }

    _handle_query = _handle_status

    def _handle_shutdown(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Signal graceful shutdown."""
        logger.info("[PacketHandler] Graceful shutdown requested.")
        self.shutdown_requested = True
        self.state.shutdown_requested = True
        self.state.is_alive = False
        return {
            "status": "shutting_down",
            "message": "PAMG server shutting down gracefully.",
        }

    def _handle_flat_telemetry(self, packet: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback handler for flat JSON packets without an action key."""
        if "valence" in packet or "arousal" in packet:
            v = packet.get("valence", self.state.x or 0.5)
            a = packet.get("arousal", self.state.y or 0.5)
            self.state.set_valence_arousal(v, a)

        if "x" in packet and packet["x"] is not None:
            self.state.x = max(0.0, min(1.0, float(packet["x"])))
        if "y" in packet and packet["y"] is not None:
            self.state.y = max(0.0, min(1.0, float(packet["y"])))

        if "time_signature" in packet and packet["time_signature"] is not None:
            try:
                self.state.set_time_signature(str(packet["time_signature"]))
            except ValueError as err:
                return {"status": "error", "message": str(err)}

        if "health" in packet and packet["health"] is not None:
            self.state.health = float(packet["health"])
        if "enemies" in packet and packet["enemies"] is not None:
            self.state.enemies = float(packet["enemies"])

        if "tempo" in packet and packet["tempo"] is not None:
            new_tempo = float(packet["tempo"])
            if new_tempo > 0:
                self.state.tempo = new_tempo

        if "seed" in packet and packet["seed"] is not None:
            self.state.base_seed = int(packet["seed"])
        elif "base_seed" in packet and packet["base_seed"] is not None:
            self.state.base_seed = int(packet["base_seed"])

        structure_changed = False
        if "loop_size" in packet and packet["loop_size"] is not None:
            new_loop = int(packet["loop_size"])
            if new_loop > 0 and new_loop != self.state.loop_size:
                self.state.loop_size = new_loop
                structure_changed = True

        if "grain" in packet and packet["grain"] is not None:
            new_grain = int(packet["grain"])
            if new_grain > 0 and new_grain != self.state.grain:
                self.state.grain = new_grain
                structure_changed = True

        if structure_changed:
            self.state.structure_dirty = True

        # Flat telemetry unpauses the engine if paused
        self.state.paused = False

        return {
            "status": "ok",
            "x": self.state.x,
            "y": self.state.y,
            "tempo": self.state.tempo,
            "seed": self.state.base_seed,
        }
