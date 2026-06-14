"""Orchestration agent for channel assignment and range enforcement."""

import random
from itertools import zip_longest
from typing import Any, Dict, Iterable, List, Optional, Tuple


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
        harmony_layer_mode: str = "probabilistic",
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
            harmony_layer_mode (str): "deterministic" or "probabilistic".
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
        self._rng = random.Random(seed)
        self.harmony_channels = self._normalize_harmony_channels(harmony_channels)
        self.harmony_layer_weights = self._normalize_layer_weights(
            harmony_layer_weights,
        )
        self.melody_program = self._clamp_program(melody_program)
        self.harmony_programs = self._normalize_harmony_programs(
            harmony_programs,
        )
        self.harmony_layer_mode = self._normalize_layer_mode(
            harmony_layer_mode,
        )
        self._harmony_layer_mask: Optional[List[bool]] = None
        self._channel_families: Dict[int, str] = {}
        self._family_ranges: Dict[str, Tuple[int, int]] = {}
        self._channel_ranges: Dict[int, Tuple[int, int]] = {}
        self._pending_program_changes: List[Tuple[int, int]] = []
        self._pending_cc_changes: List[Tuple[int, int, int]] = []  # (channel, cc, value)
        self._last_melody_channels: Optional[List[int]] = None
        self._last_melody_program: Optional[int] = None
        self._last_harmony_pairs: List[Tuple[int, int]] = []
        self._queue_program_changes(force=True)
        self._queue_cc_changes(force=True)

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    def _transpose_note_to_range(self, note: int, note_range: Tuple[int, int]) -> int:
        """
        Transpose a note by octaves until it falls within the specified range.

        If the note is already in range, it is returned unchanged.
        If it is below, it is shifted up by 12-semitone steps.
        If it is above, it is shifted down.

        Args:
            note (int): Initial MIDI note.
            note_range (Tuple[int, int]): (Low, High) bounds.

        Returns:
            int: Transposed note within [Low, High].
        """
        low, high = note_range
        note = int(note)

        # Edge case: range is invalid or too small for octave shift.
        if low >= high:
            return low
        if (high - low) < 1:
            return low

        # Transpose by octaves.
        while note < low:
            note += 12
        while note > high:
            note -= 12

        # Final safety clamp in case the range is smaller than an octave.
        return max(low, min(high, note))

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
            prepared["note"] = self._transpose_note_to_range(
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
        """
        merged: List[Dict[str, Any]] = []

        # Prepare melody events (with doubling support).
        for event in melody_events:
            for channel in self.melody_channels:
                merged.append(
                    self._prepare_event(
                        event,
                        channel,
                        self.melody_range,
                    )
                )

        if harmony_events:
            # Apply layer masks and weights per harmony channel.
            layer_mask = self._normalize_layer_mask(self._harmony_layer_mask)
            
            # Arpeggio/Voice distribution logic:
            # If an event has a `voice_index`, it is assigned to a specific
            # channel rather than being duplicated across all layers.
            for event in harmony_events:
                voice_index = event.get("voice_index")
                
                if voice_index is not None:
                    # Distribute this specific voice to one channel.
                    target_idx = voice_index % len(self.harmony_channels)
                    channel = self.harmony_channels[target_idx]
                    weight = self.harmony_layer_weights[target_idx]
                    
                    if layer_mask is not None and not layer_mask[target_idx]:
                        continue
                    
                    # Instead of probabilistic note-dropping, we use a 
                    # threshold check for polyphony conservation.
                    if weight < 0.05:
                        continue
                        
                    merged.append(
                        self._prepare_event(
                            event,
                            channel,
                            self.harmony_range,
                        )
                    )
                else:
                    # Fallback: duplicate the event across all active layers.
                    for idx, (channel, weight) in enumerate(
                        zip(self.harmony_channels, self.harmony_layer_weights)
                    ):
                        if layer_mask is not None and not layer_mask[idx]:
                            continue
                        if weight < 0.05:
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
            changed = True

        if "melody_program" in kwargs:
            new_val = self._clamp_program(kwargs["melody_program"])
            if new_val != self.melody_program:
                self.melody_program = new_val
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

        if "melody_range" in kwargs:
            new_range = kwargs["melody_range"]
            new_val = (int(new_range[0]), int(new_range[1]))
            if new_val != self.melody_range:
                self.melody_range = new_val
                changed = True

        if "harmony_range" in kwargs:
            new_range = kwargs["harmony_range"]
            new_val = (int(new_range[0]), int(new_range[1]))
            if new_val != self.harmony_range:
                self.harmony_range = new_val
                changed = True

        if "harmony_layer_mode" in kwargs:
            new_val = self._normalize_layer_mode(kwargs["harmony_layer_mode"])
            if new_val != self.harmony_layer_mode:
                self.harmony_layer_mode = new_val
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

        if program_state_changed:
            self._queue_program_changes()

        return changed

    # ------------------------------------------------------------------
    # Program change handling
    # ------------------------------------------------------------------

    def consume_program_changes(self) -> List[Tuple[int, int]]:
        """
        Return and clear pending program changes as (channel, program) pairs.
        """
        changes = list(self._pending_program_changes)
        self._pending_program_changes.clear()
        return changes

    def consume_cc_changes(self) -> List[Tuple[int, int, int]]:
        """
        Return and clear pending Control Change (CC) messages.
        Format: (channel, control_number, value)
        """
        changes = list(self._pending_cc_changes)
        self._pending_cc_changes.clear()
        return changes

    def on_phrase_start(self) -> None:
        """Force a program-change snapshot at phrase boundaries."""
        self._queue_program_changes(force=True)

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

    def _queue_program_changes(self, force: bool = False) -> None:
        if force or (
            self._last_melody_channels != self.melody_channels
            or self._last_melody_program != self.melody_program
        ):
            for channel in self.melody_channels:
                self._pending_program_changes.append(
                    (channel, self.melody_program)
                )
            self._last_melody_channels = list(self.melody_channels)
            self._last_melody_program = self.melody_program

        harmony_pairs = self._build_harmony_program_pairs()
        if force or harmony_pairs != self._last_harmony_pairs:
            self._pending_program_changes.extend(harmony_pairs)
            self._last_harmony_pairs = list(harmony_pairs)

    def _queue_cc_changes(self, force: bool = False) -> None:
        """Queue Expression (CC 11) messages based on layer weights."""
        # CC 11 is Expression; mapped from weight [0, 1] to [0, 127]
        EXPRESSION_CC = 11
        for idx, (channel, weight) in enumerate(
            zip(self.harmony_channels, self.harmony_layer_weights)
        ):
            cc_value = int(round(weight * 127))
            self._pending_cc_changes.append(
                (int(channel), EXPRESSION_CC, cc_value)
            )

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
