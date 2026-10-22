"""Orchestration agent for channel assignment and range enforcement."""

import random
from itertools import zip_longest
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.core.configs import AUDIO_CONFIG, PERCUSSION_PROGRAM


# ---------------------------------------------------------------------------
# Orchestration agent
# ---------------------------------------------------------------------------


class OrchestratorAgent:
    """
    The Orchestration Agent (OA) assigns channels and enforces simple ranges
    for melodic and harmonic events before they are routed to MIDI output.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        melody_channels: Optional[List[int]] = None,
        harmony_channel: int = 2,
        harmony_channels: Optional[List[int]] = None,
        harmony_layer_weights: Optional[List[float]] = None,
        melody_range: Tuple[int, int] = (48, 84),
        harmony_range: Tuple[int, int] = (40, 76),
        harmony_programs: Optional[List[int]] = None,
        melody_program: int = 0,
        melody_programs: Optional[List[int]] = None,
        percussion_program: int = PERCUSSION_PROGRAM,
        harmony_layer_mode: str = "deterministic",
        ma_orch_plus_minus: float = 0.5,
        ha_ins_plus_minus: float = 0.5,
        ha_register_ins: float = 1.0,
        audio_config: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None,
    ) -> None:
        """
        Initialize orchestration settings and program state.

        Args:
            melody_channels (Optional[List[int]]): List of melody channels.
            harmony_channel (int): Default MIDI channel for harmony events.
            harmony_channels (Optional[List[int]]): Harmony channels list.
            harmony_layer_weights (Optional[List[float]]): Per-layer weights.
            melody_range (Tuple[int, int]): Allowed melody pitch range.
            harmony_range (Tuple[int, int]): Allowed harmony pitch range.
            harmony_programs (Optional[List[int]]): Programs per layer.
            melody_program (int): Program for melody channel(s).
            melody_programs (Optional[List[int]]): Programs per melody layer.
            harmony_layer_mode (str): Mode for instrument layering.
            ma_orch_plus_minus (float): Orch +/- (MA) baseline control (§5.1.1).
            ha_ins_plus_minus (float): Ins +/- (HA) baseline control (§5.1.2).
            ha_register_ins (float): Reg ins (HA) baseline control (§5.1.2).
            audio_config (Optional[Dict[str, Any]]): Audio and spatial staging config.
            seed (Optional[int]): RNG seed for weighted layer selection.
        """
        self.melody_channels = self._normalize_melody_channels(melody_channels)
        self.harmony_channel = int(harmony_channel)
        self.melody_range = (
            int(melody_range[0]),
            int(melody_range[1]),
        )
        self.harmony_range = (
            int(harmony_range[0]),
            int(harmony_range[1]),
        )
        self.ma_orch_plus_minus = float(ma_orch_plus_minus)
        self.ha_ins_plus_minus = float(ha_ins_plus_minus)
        self.ha_register_ins = float(ha_register_ins)
        self.audio_config = dict(audio_config) if audio_config is not None else dict(AUDIO_CONFIG)
        self._rng = random.Random(seed)
        self.harmony_channels = self._normalize_harmony_channels(harmony_channels)
        self.harmony_layer_weights = self._normalize_layer_weights(
            harmony_layer_weights,
        )
        self.melody_program = self._clamp_program(melody_program)
        self.melody_programs = self._normalize_melody_programs(melody_programs)
        self.harmony_programs = self._normalize_harmony_programs(
            harmony_programs,
        )
        self.percussion_program = self._clamp_program(percussion_program)
        self.harmony_layer_mode = self._normalize_layer_mode(harmony_layer_mode)
        self._harmony_layer_mask: Optional[List[bool]] = None
        self._channel_families: Dict[int, str] = {}
        self._family_ranges: Dict[str, Tuple[int, int]] = {}
        self._channel_ranges: Dict[int, Tuple[int, int]] = {}
        self._pending_program_changes: List[Tuple[int, int]] = []
        self._pending_cc_changes: List[Tuple[int, int, int]] = []
        self._queued_reverb_channels: set = set()
        self._queued_volume_channels: set = set()
        self._last_melody_channels: Optional[List[int]] = None
        self._last_melody_programs: Optional[List[int]] = None
        self._last_melody_program: Optional[int] = None
        self._last_melody_pairs: List[Tuple[int, int]] = []
        self._last_harmony_pairs: List[Tuple[int, int]] = []
        self._last_harmony_cc_values: Dict[int, int] = {}
        self._last_percussion_program: Optional[int] = None
        self._queue_program_changes(force=True)
        self._queue_cc_changes(force=True)

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    def _clamp_note_to_range(self, note: int, note_range: Tuple[int, int]) -> int:
        """
        Clamp a note to the specified range bounds [Low, High].

        Args:
            note (int): Initial MIDI note.
            note_range (Tuple[int, int]): (Low, High) bounds.

        Returns:
            int: Clamped note within [Low, High].
        """
        low, high = note_range
        return max(low, min(high, int(note)))

    def _prepare_event(
        self,
        event: Dict[str, Any],
        channel: int,
        note_range: Tuple[int, int],
    ) -> Dict[str, Any]:
        prepared = dict(event)
        prepared["channel"] = channel
        if "note" in prepared:
            resolved_range = self._resolve_range(channel, note_range)
            prepared["note"] = self._clamp_note_to_range(
                prepared["note"],
                resolved_range,
            )
        return prepared

    def process_tick(
        self,
        melody_events: Iterable[Dict[str, Any]],
        harmony_events: Optional[Iterable[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Merge melody and harmony events, assigning channels and clamping notes.
        Strict deterministic instrument addition/subtraction (§5.1.1, §5.1.2)
        and dynamic 4x2 matrix routing based on preset parameters.
        """
        merged: List[Dict[str, Any]] = []

        # 5.1.1 Add/subtract instruments (melody lines) {Orch +/- (MA)}
        if len(self.melody_channels) == 4:
            if self.ma_orch_plus_minus < 0.4:
                # Solo Strings
                active_mel_channels = [self.melody_channels[0]]
            elif self.ma_orch_plus_minus < 0.8:
                # Strings + Woodwinds doubling
                active_mel_channels = [self.melody_channels[0], self.melody_channels[2]]
            else:
                # Strings + Woodwinds + Brass tutti doubling
                active_mel_channels = [
                    self.melody_channels[0],
                    self.melody_channels[2],
                    self.melody_channels[3],
                ]
        else:
            if len(self.melody_channels) > 1 and self.ma_orch_plus_minus < 0.5:
                active_mel_channels = self.melody_channels[:1]
            else:
                active_mel_channels = self.melody_channels

        # Prepare melody events (with doubling support).
        for event in melody_events:
            for channel in active_mel_channels:
                merged.append(
                    self._prepare_event(
                        event,
                        channel,
                        self.melody_range,
                    )
                )

        if harmony_events:
            # 5.1.2 Add/subtract instruments (assign voices) {Reg ins & Ins +/- (HA)}
            layer_mask = self._normalize_layer_mask(self._harmony_layer_mask)

            if len(self.harmony_channels) == 4:
                # Registration priority: Piano (idx 1), Strings (idx 0), Woodwinds (idx 2), Brass (idx 3)
                reg_order = [1, 0, 2, 3]
                reg_count = max(1, min(4, int(round(self.ha_register_ins))))
                registered_indices = reg_order[:reg_count]
                pool_size = len(registered_indices)
                active_count = max(
                    1,
                    min(
                        pool_size,
                        int(round(1 + self.ha_ins_plus_minus * (pool_size - 1))),
                    ),
                )
                active_harm_channels = [
                    self.harmony_channels[i] for i in registered_indices[:active_count]
                ]
            else:
                max_harm = len(self.harmony_channels)
                active_count = max(
                    1,
                    min(
                        max_harm,
                        int(round(1 + self.ha_ins_plus_minus * (max_harm - 1))),
                    ),
                )
                active_harm_channels = self.harmony_channels[:active_count]

            for event in harmony_events:
                for channel in active_harm_channels:
                    family = self._channel_families.get(channel)
                    if event.get("is_arpeggio") and family == "brass":
                        # Baseline idiomatic restriction: brass avoids
                        # arpeggiated figures.
                        continue
                    if event.get("arpeggio_rate_denominator", 0) >= 32 and (
                        family != "keys" or len(active_harm_channels) != 1
                    ):
                        # Only solo Piano may use the documented 1/32 rate.
                        continue
                    orig_idx = (
                        self.harmony_channels.index(channel)
                        if channel in self.harmony_channels
                        else 0
                    )
                    if layer_mask is not None and orig_idx < len(layer_mask) and not layer_mask[orig_idx]:
                        continue
                    weight = (
                        self.harmony_layer_weights[orig_idx]
                        if orig_idx < len(self.harmony_layer_weights)
                        else 1.0
                    )
                    if self.harmony_layer_mode == "probabilistic":
                        if self._rng.random() >= weight:
                            continue
                    elif weight < 0.5:
                        continue
                    merged.append(
                        self._prepare_event(
                            event,
                            channel,
                            self.harmony_range,
                        )
                    )

        return merged

    # ------------------------------------------------------------------
    # Parameter updates
    # ------------------------------------------------------------------

    def update_params(self, **kwargs) -> bool:
        """
        Apply parameter updates for orchestration behavior.

        Supported keys:
            - melody_channels
            - harmony_channel
            - harmony_channels
            - harmony_layer_weights
            - melody_range
            - harmony_range
            - melody_program
            - harmony_programs
            - harmony_layer_mode
            - harmony_layer_mask
            - channel_families
            - family_ranges
            - channel_ranges

        Returns:
            bool: True if any parameter changed.
        """
        changed = False

        program_state_changed = False

        if "melody_channels" in kwargs:
            new_val = self._normalize_melody_channels(kwargs["melody_channels"])
            if new_val != self.melody_channels:
                self.melody_channels = new_val
                self.melody_programs = self._normalize_melody_programs(
                    kwargs.get("melody_programs", self.melody_programs)
                )
                changed = True
                program_state_changed = True

        if "harmony_channel" in kwargs:
            new_val = int(kwargs["harmony_channel"])
            if new_val != self.harmony_channel:
                self.harmony_channel = new_val
                self.harmony_channels = [new_val]
                self.harmony_layer_weights = [1.0]
                self.harmony_programs = self._normalize_harmony_programs(
                    kwargs.get("harmony_programs"),
                )
                changed = True
                program_state_changed = True

        harmony_programs = kwargs.get("harmony_programs")
        if "harmony_channels" in kwargs:
            new_channels = kwargs["harmony_channels"]
            normalized_channels = self._normalize_harmony_channels(new_channels)
            if normalized_channels != self.harmony_channels:
                self.harmony_channels = normalized_channels
                self.harmony_layer_weights = self._normalize_layer_weights(
                    kwargs.get("harmony_layer_weights"),
                )
                self.harmony_programs = self._normalize_harmony_programs(
                    harmony_programs
                    if harmony_programs is not None
                    else self.harmony_programs,
                )
                changed = True
                program_state_changed = True

        if "harmony_layer_weights" in kwargs:
            self.harmony_layer_weights = self._normalize_layer_weights(
                kwargs["harmony_layer_weights"],
            )
            self._queue_cc_changes()
            changed = True

        if "melody_program" in kwargs and "melody_programs" not in kwargs:
            new_val = self._clamp_program(kwargs["melody_program"])
            if new_val != self.melody_program:
                self.melody_program = new_val
                self.melody_programs = self._normalize_melody_programs([new_val])
                changed = True
                program_state_changed = True

        if "melody_programs" in kwargs:
            new_progs = self._normalize_melody_programs(kwargs["melody_programs"])
            if new_progs != self.melody_programs:
                self.melody_programs = new_progs
                changed = True
                program_state_changed = True

        if "harmony_programs" in kwargs and "harmony_channels" not in kwargs:
            normalized_programs = self._normalize_harmony_programs(
                kwargs["harmony_programs"],
            )
            if normalized_programs != self.harmony_programs:
                self.harmony_programs = normalized_programs
                changed = True
                program_state_changed = True

        if "ha_register_ins" in kwargs:
            new_val = max(1.0, min(4.0, float(kwargs["ha_register_ins"])))
            if new_val != self.ha_register_ins:
                self.ha_register_ins = new_val
                changed = True

        if "ma_orch_plus_minus" in kwargs:
            new_val = max(0.0, min(1.0, float(kwargs["ma_orch_plus_minus"])))
            if new_val != self.ma_orch_plus_minus:
                self.ma_orch_plus_minus = new_val
                changed = True

        if "ha_ins_plus_minus" in kwargs:
            new_val = max(0.0, min(1.0, float(kwargs["ha_ins_plus_minus"])))
            if new_val != self.ha_ins_plus_minus:
                self.ha_ins_plus_minus = new_val
                changed = True

        if "ma_orch_range_low" in kwargs and "ma_orch_range_high" in kwargs:
            new_val = (int(kwargs["ma_orch_range_low"]), int(kwargs["ma_orch_range_high"]))
            if new_val != self.melody_range:
                self.melody_range = new_val
                changed = True
        elif "melody_range" in kwargs:
            new_range = kwargs["melody_range"]
            new_val = (int(new_range[0]), int(new_range[1]))
            if new_val != self.melody_range:
                self.melody_range = new_val
                changed = True

        if "ha_range_ins_low" in kwargs and "ha_range_ins_high" in kwargs:
            new_val = (int(kwargs["ha_range_ins_low"]), int(kwargs["ha_range_ins_high"]))
            if new_val != self.harmony_range:
                self.harmony_range = new_val
                changed = True
        elif "harmony_range" in kwargs:
            new_range = kwargs["harmony_range"]
            new_val = (int(new_range[0]), int(new_range[1]))
            if new_val != self.harmony_range:
                self.harmony_range = new_val
                changed = True

        if "harmony_layer_mode" in kwargs:
            new_mode = self._normalize_layer_mode(kwargs["harmony_layer_mode"])
            if new_mode != self.harmony_layer_mode:
                self.harmony_layer_mode = new_mode
                changed = True

        if "harmony_layer_mask" in kwargs:
            new_mask = self._normalize_layer_mask(kwargs["harmony_layer_mask"])
            if new_mask != self._harmony_layer_mask:
                self._harmony_layer_mask = new_mask
                changed = True

        if "channel_families" in kwargs:
            raw_map = kwargs["channel_families"] or {}
            new_map = {
                int(key): str(value)
                for key, value in raw_map.items()
            }
            if new_map != self._channel_families:
                self._channel_families = new_map
                changed = True

        if "family_ranges" in kwargs:
            raw_ranges = kwargs["family_ranges"] or {}
            new_ranges = {
                str(key): (int(val[0]), int(val[1]))
                for key, val in raw_ranges.items()
            }
            if new_ranges != self._family_ranges:
                self._family_ranges = new_ranges
                changed = True

        if "channel_ranges" in kwargs:
            raw_ranges = kwargs["channel_ranges"] or {}
            new_ranges = {
                int(key): (int(val[0]), int(val[1]))
                for key, val in raw_ranges.items()
            }
            if new_ranges != self._channel_ranges:
                self._channel_ranges = new_ranges
                changed = True

        if "audio_config" in kwargs and kwargs["audio_config"] is not None:
            self.audio_config = dict(kwargs["audio_config"])
            self._queue_cc_changes(force=True)
            changed = True

        if "seed" in kwargs and kwargs["seed"] is not None:
            self._rng.seed(int(kwargs["seed"]))
            changed = True

        if "percussion_program" in kwargs and kwargs["percussion_program"] is not None:
            new_val = self._clamp_program(kwargs["percussion_program"])
            if new_val != self.percussion_program:
                self.percussion_program = new_val
                program_state_changed = True

        if program_state_changed:
            self._queue_program_changes()

        return changed

    # ------------------------------------------------------------------
    # Program and CC change handling
    # ------------------------------------------------------------------

    def _queue_cc_changes(self, force: bool = False) -> None:
        """Queue MIDI CC updates (CC 91 Reverb, CC 7 Volume, and CC 11 Expression)."""
        reverb_sends = self.audio_config.get("channel_reverb_sends", {})
        volumes = self.audio_config.get("channel_volumes", {})

        # 1. CC 91 Reverb Sends (Spatial placement in concert hall)
        for ch, val in reverb_sends.items():
            if force or ch not in self._queued_reverb_channels:
                self._pending_cc_changes.append((int(ch), 91, max(0, min(127, int(val)))))
                self._queued_reverb_channels.add(int(ch))

        # 2. CC 7 Channel Volume Staging (Soloist pocket for lead melody)
        for ch, val in volumes.items():
            if force or ch not in self._queued_volume_channels:
                self._pending_cc_changes.append((int(ch), 7, max(0, min(127, int(val)))))
                self._queued_volume_channels.add(int(ch))

        # 3. CC 11 Dynamic Harmony Expression
        for idx, channel in enumerate(self.harmony_channels):
            weight = self.harmony_layer_weights[idx] if idx < len(self.harmony_layer_weights) else 1.0
            val = max(0, min(127, int(round(weight * 127))))
            channel = int(channel)
            if force or self._last_harmony_cc_values.get(channel) != val:
                self._pending_cc_changes.append((channel, 11, val))
                self._last_harmony_cc_values[channel] = val

    def consume_cc_changes(self) -> List[Tuple[int, int, int]]:
        """Return and clear pending CC changes as (channel, control, value) tuples."""
        changes = list(self._pending_cc_changes)
        self._pending_cc_changes.clear()
        return changes

    def consume_program_changes(self) -> List[Tuple[int, int]]:
        """
        Return and clear pending program changes as (channel, program) pairs.
        """
        changes = list(self._pending_program_changes)
        self._pending_program_changes.clear()
        return changes


    def on_phrase_start(self) -> None:
        """Force a program-change and CC snapshot at phrase boundaries."""
        self._queue_program_changes(force=True)
        self._queue_cc_changes(force=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_melody_channels(
        self,
        channels: Optional[Iterable[int]],
    ) -> List[int]:
        if channels is None:
            return [1]  # Default channel 1

        normalized = [int(ch) for ch in channels]
        if not normalized:
            return [1]
        return normalized

    def _normalize_harmony_channels(
        self,
        channels: Optional[Iterable[int]],
    ) -> List[int]:
        if channels is None:
            return [self.harmony_channel]

        normalized = [int(ch) for ch in channels]
        if not normalized:
            return [self.harmony_channel]
        return normalized

    def _normalize_layer_weights(
        self,
        weights: Optional[Iterable[float]],
    ) -> List[float]:
        if weights is None:
            return [1.0 for _ in self.harmony_channels]

        normalized = [self._clamp_weight(val) for val in weights]
        if len(normalized) < len(self.harmony_channels):
            last = normalized[-1] if normalized else 1.0
            missing = len(self.harmony_channels) - len(normalized)
            normalized.extend([last for _ in range(missing)])
        return normalized[: len(self.harmony_channels)]

    def _normalize_layer_mask(
        self,
        mask: Optional[Iterable[bool]],
    ) -> Optional[List[bool]]:
        if mask is None:
            return None

        normalized = [bool(val) for val in mask]
        if len(normalized) < len(self.harmony_channels):
            normalized.extend(
                [True for _ in range(len(self.harmony_channels) - len(normalized))]
            )
        return normalized[: len(self.harmony_channels)]

    def _normalize_melody_programs(
        self,
        programs: Optional[Iterable[int]],
    ) -> List[int]:
        if programs is None:
            programs = [self.melody_program]

        normalized = [self._clamp_program(val) for val in programs]
        if not normalized:
            normalized = [self.melody_program]

        if len(normalized) < len(self.melody_channels):
            last = normalized[-1]
            missing = len(self.melody_channels) - len(normalized)
            normalized.extend([last for _ in range(missing)])
        return normalized[: len(self.melody_channels)]

    def _normalize_harmony_programs(
        self,
        programs: Optional[Iterable[int]],
    ) -> List[int]:
        if programs is None:
            programs = [self.melody_program]

        normalized = [self._clamp_program(val) for val in programs]
        if not normalized:
            normalized = [self.melody_program]

        if len(normalized) < len(self.harmony_channels):
            last = normalized[-1]
            missing = len(self.harmony_channels) - len(normalized)
            normalized.extend([last for _ in range(missing)])
        return normalized[: len(self.harmony_channels)]

    def _build_melody_program_pairs(self) -> List[Tuple[int, int]]:
        if not self.melody_channels:
            return []

        programs = list(self.melody_programs)
        fallback = programs[-1] if programs else self.melody_program
        sentinel = object()
        pairs: List[Tuple[int, int]] = []

        for channel, program in zip_longest(
            self.melody_channels,
            programs,
            fillvalue=sentinel,
        ):
            if channel is sentinel:
                break
            if program is sentinel:
                program = fallback
            prog = self._clamp_program(program)
            if prog == self.melody_program and channel == 1 and self._channel_families.get(channel) == "woodwinds":
                prog = 73
            pairs.append((int(channel), prog))
            fallback = program

        return pairs

    def _queue_program_changes(self, force: bool = False) -> None:
        melody_pairs = self._build_melody_program_pairs()
        if force or (
            self._last_melody_channels != self.melody_channels
            or self._last_melody_programs != self.melody_programs
            or self._last_melody_program != self.melody_program
            or melody_pairs != self._last_melody_pairs
        ):
            self._pending_program_changes.extend(melody_pairs)
            self._last_melody_channels = list(self.melody_channels)
            self._last_melody_programs = list(self.melody_programs)
            self._last_melody_program = self.melody_program
            self._last_melody_pairs = list(melody_pairs)

        harmony_pairs = self._build_harmony_program_pairs()
        if force or harmony_pairs != self._last_harmony_pairs:
            self._pending_program_changes.extend(harmony_pairs)
            self._last_harmony_pairs = list(harmony_pairs)

        # Percussion bypasses the Orchestration Agent in the PAMG baseline.
        # PA owns its own direct instrument path; retain this constructor field
        # only for compatibility with existing callers.


    def _build_harmony_program_pairs(self) -> List[Tuple[int, int]]:
        if not self.harmony_channels:
            return []

        programs = list(self.harmony_programs)
        fallback = programs[-1] if programs else self.melody_program
        sentinel = object()
        pairs: List[Tuple[int, int]] = []

        for channel, program in zip_longest(
            self.harmony_channels,
            programs,
            fillvalue=sentinel,
        ):
            if channel is sentinel:
                break
            if program is sentinel:
                program = fallback
            pairs.append(
                (int(channel), self._clamp_program(program))
            )
            fallback = program

        return pairs

    def _normalize_layer_mode(self, mode: Optional[str]) -> str:
        if mode is None:
            return "probabilistic"
        normalized = str(mode).strip().lower()
        if normalized not in {"deterministic", "probabilistic"}:
            return "probabilistic"
        return normalized

    def _clamp_program(self, value: int) -> int:
        return max(0, min(127, int(value)))

    def _clamp_weight(self, value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def _resolve_range(
        self,
        channel: int,
        default_range: Tuple[int, int],
    ) -> Tuple[int, int]:
        if channel in self._channel_ranges:
            return self._channel_ranges[channel]

        family = self._channel_families.get(channel)
        if family and family in self._family_ranges:
            return self._family_ranges[family]

        return default_range
