import math

from dataclasses import fields
from typing import Any, Iterable, List

from src.core.logger import Logger
from src.models.preset import Preset

logger = Logger()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def clamp(
    value: float,
    min_value: float = 0.0,
    max_value: float = 1.0,
) -> float:
    """
    Clamps a value between a minimum and maximum range.

    Used by `_blend()` to guarantee that incoming x/y coordinates remain
    within the unit square [0, 1] × [0, 1] before computing bilinear weights.

    Args:
        value (float): The value to clamp.
        min_value (float): The minimum allowed value (default 0.0).
        max_value (float): The maximum allowed value (default 1.0).

    Returns:
        float: The clamped value within [min_value, max_value].
    """
    return max(min_value, min(max_value, value))


def lerp(start: float, end: float, t: float) -> float:
    """
    Linear interpolation between start and end by factor t ∈ [0, 1].

    Used in two places:
        • `_blend_value()` — spatial blend across the four corner presets.
        • `_smooth_value()` — temporal smoothing from current state to target.

    Args:
        start (float): The starting value (t = 0).
        end   (float): The ending value   (t = 1).
        t     (float): Interpolation factor; 0 returns start, 1 returns end.

    Returns:
        float: start + (end - start) * t
    """
    return start + (end - start) * t


# ---------------------------------------------------------------------------
# Main interpolator
# ---------------------------------------------------------------------------

class MultiParameterPresetInterpolator:
    """
    Smooth 2D interpolation across four corner Presets (A, B, C, D).

    This class sits at the heart of Stage 1 (Global Control & Parameter Input)
    in the PAMG architecture.  It accepts a continuous (x, y) position from
    external game variables or composer controls, computes a bilinearly blended
    target Preset, and applies exponential-lag smoothing so parameter changes
    feel musically gradual rather than abrupt.

    Preset corner layout
    --------------------
        C (0,1) ── D (1,1)
        │              │
        A (0,0) ── B (1,0)

    Parameter field classification
    --------------------------------
    The Preset dataclass may contain many fields.  Each field falls into one of
    four categories that determine how it is blended and smoothed:

        _DISCRETE_FIELDS          — scalar discrete (e.g. MIDI program numbers,
                                    mode enums).  Winner-take-all blend;
                                    deferred to phrase boundaries.
        _LIST_INTERPOLATED_FIELDS — list of floats blended element-wise and
                                    smoothed continuously (e.g. layer weights).
        _LIST_DISCRETE_FIELDS     — list of discrete values; winner-take-all
                                    per list, deferred to phrase boundaries.
        (everything else)         — scalar continuous; linearly blended and
                                    exponentially smoothed every pulse.

    Thread / timing considerations
    --------------------------------
    `update()` is intended to be called once per clock pulse by the scheduler
    (core/scheduler.py).  `get_quantized_state()` should be called exactly at
    phrase-start pulses so discrete changes land on bar/phrase boundaries.
    """

    # ------------------------------------------------------------------
    # Field classification sets
    # ------------------------------------------------------------------

    # Scalar parameters that must not change mid-phrase (e.g. instrument
    # programs that would cause audible clicks or re-triggers).
    _DISCRETE_FIELDS = {
        "melody_program",
        "harmony_layer_mode",
        "scale_mode",
    }

    # List parameters that are safe to interpolate continuously element-wise
    # (e.g. per-layer mix weights).
    _LIST_INTERPOLATED_FIELDS = {
        "harmony_layer_weights",
    }

    # List parameters that are discrete per-element; snapped to the winning
    # preset at phrase boundaries (e.g. MIDI program per harmony layer).
    _LIST_DISCRETE_FIELDS = {
        "harmony_programs",
    }

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        a: Preset,
        b: Preset,
        c: Preset,
        d: Preset,
        smoothing_time: float = 0.25,
    ):
        """
        Initialise the interpolator with four corner presets.

        Args:
            a (Preset): Preset at XY corner (0, 0) — "calm / sparse".
            b (Preset): Preset at XY corner (1, 0) — "tense / sparse".
            c (Preset): Preset at XY corner (0, 1) — "calm / full".
            d (Preset): Preset at XY corner (1, 1) — "tense / full".
            smoothing_time (float): Exponential-lag time constant in seconds.
                Controls how quickly the running state tracks a moving XY
                position.  Clamped to ≥ 0.001 s to prevent division by zero.
        """
        self.a, self.b, self.c, self.d = a, b, c, d

        # Prevent degenerate smoothing (division by zero or negative time).
        self.smoothing_time = max(0.001, smoothing_time)

        # Cache fields to avoid redundant lookups in the main loop.
        self._fields = fields(a)

        # Running interpolated state — starts at preset A.
        # Continuously updated by `update()` toward the blended target.
        self._state = self._copy_preset(a)

        # Holds the most recent *discrete* target values computed by `update()`.
        # These are NOT applied to `_state` immediately; they are held here and
        # only merged into the output by `get_quantized_state()` at phrase
        # boundaries, preventing mid-phrase timbral jumps.
        self._pending_discrete = self._copy_preset(a)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, x: float, y: float, pulse_duration: float) -> Preset:
        """
        Advance the interpolator by one clock pulse.

        Called once per scheduler tick (core/scheduler.py).  Steps:
            1. Compute the *target* Preset via bilinear blend at (x, y).
            2. Derive the smoothing factor alpha from pulse_duration.
            3. Move `_state` one exponential-lag step toward target for all
               continuous and list-interpolated fields.
            4. Snapshot the latest discrete targets into `_pending_discrete`
               so they can be applied at the next phrase boundary.
            5. Return a copy of the updated `_state`.

        Args:
            x (float): Horizontal XY-pad position [0, 1].
                       0 → presets A/C side; 1 → presets B/D side.
            y (float): Vertical XY-pad position [0, 1].
                       0 → presets A/B side; 1 → presets C/D side.
            pulse_duration (float): Wall-clock duration of this pulse in
                       seconds (= 60 / BPM / grain).  Used to compute alpha.

        Returns:
            Preset: A deep copy of the current smoothed state.  Suitable for
                    broadcasting to agents as continuous parameter vectors.
        """
        # Step 1 — bilinear blend at the current XY position.
        target = self._blend(x, y)

        # Step 2 — exponential-lag smoothing factor for this pulse.
        alpha = self._alpha_from_pulse(pulse_duration)

        # Step 3 — smooth every field toward the target.
        self._state = Preset(
            **{
                field.name: self._smooth_value(
                    field.name,
                    getattr(self._state, field.name),
                    getattr(target, field.name),
                    alpha,
                )
                for field in self._fields
            }
        )

        # Step 4 — cache discrete targets for phrase-boundary application.
        # Discrete and list-discrete fields come from `target` (the blend
        # winner); continuous fields mirror `_state` so the snapshot is
        # self-consistent.
        self._pending_discrete = Preset(
            **{
                field.name: self._copy_if_list(getattr(target, field.name))
                if field.name in self._DISCRETE_FIELDS
                or field.name in self._LIST_DISCRETE_FIELDS
                else self._copy_if_list(getattr(self._state, field.name))
                for field in self._fields
            }
        )

        # Step 5 — return a safe copy so callers cannot mutate internal state.
        return self._copy_preset(self._state)

    def get_quantized_state(self, phrase_start: bool = False) -> Preset:
        """
        Return the current state with pending discrete changes applied,
        but only at a phrase boundary.

        Discrete parameters (instrument programs, layer modes) are held in
        `_pending_discrete` and not applied to the running `_state`.  This
        method merges them into a *new* Preset snapshot that is safe to send
        to agents at a phrase-start event, preserving musical form.

        If `phrase_start` is False the method returns None (no-op), signalling
        to callers that no discrete update should be dispatched this pulse.

        Args:
            phrase_start (bool): True only when the scheduler signals the
                beginning of a new phrase/bar.

        Returns:
            Preset | None: Merged Preset at phrase boundaries; None otherwise.
        """
        if phrase_start:
            return Preset(
                **{
                    field.name: self._copy_if_list(
                        getattr(self._pending_discrete, field.name)
                    )
                    if field.name in self._DISCRETE_FIELDS
                    or field.name in self._LIST_DISCRETE_FIELDS
                    else self._copy_if_list(getattr(self._state, field.name))
                    for field in self._fields
                }
            )

    # ------------------------------------------------------------------
    # Internal — spatial blending (XY pad)
    # ------------------------------------------------------------------

    def _blend(self, x: float, y: float) -> Preset:
        """
        Compute the bilinearly blended target Preset for position (x, y).

        Bilinear weights:
            w_A = (1-x)(1-y)    w_B = x(1-y)
            w_C = (1-x) y       w_D = x·y

        These four weights always sum to 1.0, so the result is a convex
        combination of the corner presets.  x and y are clamped to [0, 1]
        before weight computation.

        Args:
            x (float): Horizontal position on the XY pad [0, 1].
            y (float): Vertical position on the XY pad [0, 1].

        Returns:
            Preset: A new Preset instance whose fields are the weighted blend
                    of the four corner presets.
        """
        x = clamp(x)
        y = clamp(y)

        # Bilinear corner weights.
        w00 = (1 - x) * (1 - y)    # weight for preset A
        w10 = x * (1 - y)          # weight for preset B
        w01 = (1 - x) * y          # weight for preset C
        w11 = x * y                # weight for preset D

        weights = (w00, w10, w01, w11)

        logger.debug(
            f"Blending weights: (0,0)={w00:.2f}, (1,0)={w10:.2f}, (0,1)={w01:.2f}, (1,1)={w11:.2f}"
        )

        return Preset(
            **{
                field.name: self._blend_value(field.name, weights)
                for field in self._fields
            }
        )

    # ------------------------------------------------------------------
    # Internal — temporal smoothing
    # ------------------------------------------------------------------

    def _alpha_from_pulse(self, pulse_duration: float) -> float:
        """
        Convert a pulse duration into an exponential-lag smoothing factor α.

        Uses the standard one-pole IIR formula:
            α = 1 − exp(−Δt / τ)

        where Δt = pulse_duration and τ = smoothing_time.

        • α ≈ 0  →  almost no movement toward target (very slow tracking).
        • α ≈ 1  →  almost instant snap to target (no smoothing).

        At steady state a step change reaches ~63 % of its final value after
        one smoothing_time, ~95 % after three smoothing_times.

        Args:
            pulse_duration (float): Duration of the current pulse in seconds.

        Returns:
            float: Smoothing factor α ∈ (0, 1].
        """
        return 1.0 - math.exp(-pulse_duration / self.smoothing_time)

    # ------------------------------------------------------------------
    # Internal — per-field blend and smooth dispatch
    # ------------------------------------------------------------------

    def _blend_value(self, name: str, weights: Iterable[float]) -> Any:
        """
        Dispatch blending strategy for a single Preset field.

        Routes to the correct blending strategy based on field classification:
            • List-interpolated  → element-wise weighted sum (_blend_list).
            • List-discrete / Discrete → winner-take-all  (_select_discrete).
            • Continuous (default) → scalar weighted sum.

        Args:
            name    (str):             Field name from the Preset dataclass.
            weights (Iterable[float]): Bilinear weights (w_A, w_B, w_C, w_D).

        Returns:
            Any: Blended value appropriate for the field's type.
        """
        values = [
            getattr(self.a, name),
            getattr(self.b, name),
            getattr(self.c, name),
            getattr(self.d, name),
        ]

        if name in self._LIST_INTERPOLATED_FIELDS:
            return self._blend_list(name, list(weights), values)

        if name in self._LIST_DISCRETE_FIELDS or name in self._DISCRETE_FIELDS:
            return self._select_discrete(values, list(weights))

        # Default: scalar continuous — straight weighted sum.
        return sum(weight * value for weight, value in zip(weights, values))

    def _smooth_value(
        self,
        name: str,
        current: Any,
        target: Any,
        alpha: float,
    ) -> Any:
        """
        Dispatch smoothing strategy for a single Preset field.

        Routes based on field classification:
            • List-interpolated  → element-wise lerp  (_lerp_list).
            • List-discrete / Discrete → no smoothing; snap to target copy.
            • Continuous (default) → scalar lerp.

        Discrete fields are not smoothed here — they are held in
        `_pending_discrete` and only applied at phrase boundaries via
        `get_quantized_state()`.

        Args:
            name    (str):   Field name from the Preset dataclass.
            current (Any):   Current smoothed value in `_state`.
            target  (Any):   Blended target value from `_blend()`.
            alpha   (float): Smoothing factor from `_alpha_from_pulse()`.

        Returns:
            Any: New smoothed value to store in `_state`.
        """
        if name in self._LIST_INTERPOLATED_FIELDS:
            return self._lerp_list(name, current, target, alpha)

        if name in self._LIST_DISCRETE_FIELDS or name in self._DISCRETE_FIELDS:
            # Discrete fields bypass smoothing entirely; a copy of target is
            # stored separately in `_pending_discrete`. `_state` keeps the
            # prior discrete value until `get_quantized_state()` is called
            # at a phrase boundary.
            return self._copy_if_list(current)

        # Default: scalar continuous — one lerp step.
        return lerp(float(current), float(target), alpha)

    # ------------------------------------------------------------------
    # Internal — discrete selection
    # ------------------------------------------------------------------

    def _select_discrete(self, values: List[Any], weights: List[float]) -> Any:
        """
        Winner-take-all selection for discrete-valued fields.

        Picks the preset with the highest bilinear weight and returns its
        value.  This ensures discrete parameters (MIDI programs, mode enums)
        always take on a valid preset value rather than a nonsensical
        interpolated midpoint.

        Args:
            values  (List[Any]):   Values from presets [A, B, C, D].
            weights (List[float]): Bilinear weights    [w_A, w_B, w_C, w_D].

        Returns:
            Any: Value of the preset with the maximum weight.
        """
        best_index = max(range(len(weights)), key=weights.__getitem__)
        return self._copy_if_list(values[best_index])

    # ------------------------------------------------------------------
    # Internal — list blending and smoothing
    # ------------------------------------------------------------------

    def _blend_list(
        self,
        name: str,
        weights: List[float],
        values: List[List[float]],
    ) -> List[float]:
        """
        Element-wise bilinear blend of four float lists.

        Lists from different presets may have different lengths.  They are
        padded to the longest length before blending using `_pad_list()`.
        The fill value is determined by `_list_fill_value()` (0.0 or 1.0
        depending on the semantic meaning of the field).

        Args:
            name    (str):               Field name (used for fill-value lookup).
            weights (List[float]):       Bilinear weights [w_A, w_B, w_C, w_D].
            values  (List[List[float]]): Lists from presets [A, B, C, D].

        Returns:
            List[float]: Blended list; length = max(len(values[i])).
        """
        lengths = [len(val) for val in values]
        target_len = max(lengths) if lengths else 0
        if target_len == 0:
            return []

        fill_value = self._list_fill_value(name)
        padded = [self._pad_list(val, target_len, fill_value) for val in values]

        blended = []
        for idx in range(target_len):
            blended.append(
                weights[0] * padded[0][idx]
                + weights[1] * padded[1][idx]
                + weights[2] * padded[2][idx]
                + weights[3] * padded[3][idx]
            )
        return blended

    def _lerp_list(
        self,
        name: str,
        current: List[float],
        target: List[float],
        t: float,
    ) -> List[float]:
        """
        Element-wise linear interpolation between two float lists.

        Used by `_smooth_value()` for `_LIST_INTERPOLATED_FIELDS`.
        Both lists are padded to the same length before interpolation.

        Args:
            name    (str):         Field name (used for fill-value lookup).
            current (List[float]): Current smoothed list in `_state`.
            target  (List[float]): Blended target list from `_blend_list()`.
            t       (float):       Smoothing factor α from `_alpha_from_pulse()`.

        Returns:
            List[float]: New list after one lerp step toward target.
        """
        target_len = max(len(current), len(target))
        fill_value = self._list_fill_value(name)

        padded_current = self._pad_list(current, target_len, fill_value)
        padded_target  = self._pad_list(target,  target_len, fill_value)

        return [
            lerp(cur, nxt, t)
            for cur, nxt in zip(padded_current, padded_target)
        ]

    # ------------------------------------------------------------------
    # Internal — list utilities
    # ------------------------------------------------------------------

    def _pad_list(
        self,
        values: Iterable[float],
        length: int,
        fill_value: float,
    ) -> List[float]:
        """
        Pad (or truncate) a list to exactly `length` elements.

        Padding strategy: repeat the *last* element of the original list.
        This avoids abrupt value drops at the tail when lists from different
        presets differ in length.  If the input is empty, `fill_value` is
        used as the sole element before repeating.

        Args:
            values     (Iterable[float]): Source list.
            length     (int):             Desired output length.
            fill_value (float):           Fallback value for empty inputs.

        Returns:
            List[float]: Padded/truncated list of exactly `length` elements.
        """
        padded = list(values)

        if not padded:
            padded = [fill_value]

        if len(padded) < length:
            padded.extend([padded[-1]] * (length - len(padded)))

        return padded[:length]

    def _list_fill_value(self, name: str) -> float:
        """
        Return the neutral/identity fill value for a list field.

        Semantics:
            • "harmony_layer_weights" → 1.0 (full weight = layer present).
            • All other list-interpolated fields → 0.0 (absence / silence).
            • "harmony_programs" is a list-discrete field and must never be
              blended; calling this with that name raises ValueError to guard
              against accidental misuse.

        Args:
            name (str): Field name from the Preset dataclass.

        Returns:
            float: 1.0 for harmony_layer_weights; 0.0 otherwise.

        Raises:
            ValueError: If called for "harmony_programs" (discrete list —
                        blending program numbers is musically invalid).
        """
        if name == "harmony_programs":
            raise ValueError(
                "harmony_programs is a list of discrete values and should "
                "not be blended or smoothed."
            )

        return 1.0 if name == "harmony_layer_weights" else 0.0

    # ------------------------------------------------------------------
    # Internal — deep copy helpers
    # ------------------------------------------------------------------

    def _copy_preset(self, preset: Preset) -> Preset:
        """
        Return a deep copy of a Preset, duplicating any list fields.

        Prevents callers from accidentally mutating internal state through a
        shared list reference.  All scalar fields are immutable (int/float)
        so only list fields need explicit copying.

        Args:
            preset (Preset): Source preset to copy.

        Returns:
            Preset: New Preset instance with independent copies of all fields.
        """
        return Preset(
            **{
                field.name: self._copy_if_list(getattr(preset, field.name))
                for field in self._fields
            }
        )

    def _copy_if_list(self, value: Any) -> Any:
        """
        Shallow-copy a value if it is a list; return scalars unchanged.

        Args:
            value (Any): The value to (possibly) copy.

        Returns:
            Any: A new list with the same elements, or the original scalar.
        """
        if isinstance(value, list):
            return list(value)

        return value