import pytest

from src.core.preset_interpolator import MultiParameterPresetInterpolator
from src.core.configs import PRESET_A, PRESET_B, PRESET_C, PRESET_D


def test_interpolator_corner_weights():
    interp = MultiParameterPresetInterpolator(
        a=PRESET_A,
        b=PRESET_B,
        c=PRESET_C,
        d=PRESET_D,
        smoothing_time=0.0,
    )
    # Corner (0.0, 0.0) -> Pure Preset A
    p_a = interp.update(0.0, 0.0, pulse_duration=0.1)
    assert pytest.approx(p_a.seeded_phrase_length, 0.1) == PRESET_A.seeded_phrase_length

    # Corner (1.0, 0.0) -> Pure Preset B
    p_b = interp.update(1.0, 0.0, pulse_duration=0.1)
    assert pytest.approx(p_b.seeded_phrase_length, 0.1) == PRESET_B.seeded_phrase_length


def test_interpolator_quantized_state_phrase_boundary():
    interp = MultiParameterPresetInterpolator(
        a=PRESET_A,
        b=PRESET_B,
        c=PRESET_C,
        d=PRESET_D,
        smoothing_time=0.0,
    )
    # Not phrase start -> returns None
    assert interp.get_quantized_state(phrase_start=False) is None

    # Phrase start -> returns Preset
    quant = interp.get_quantized_state(phrase_start=True)
    assert quant is not None
    assert hasattr(quant, "ma_step")
    assert hasattr(quant, "ha_tension")
    assert hasattr(quant, "pa_vel_perc")


def test_interpolator_exposes_orchestration_fields():
    interp = MultiParameterPresetInterpolator(PRESET_A, PRESET_B, PRESET_C, PRESET_D)
    state = interp.update(0.5, 0.5, 0.1)
    assert len(state.oa_harmony_layer_weights) == 4
    quant = interp.get_quantized_state(phrase_start=True)
    assert quant.oa_harmony_layer_mode in {"deterministic", "probabilistic"}


def test_interpolator_quantizes_harmony_mode_by_corner():
    interp = MultiParameterPresetInterpolator(PRESET_A, PRESET_B, PRESET_C, PRESET_D, smoothing_time=0.0)

    interp.update(0.0, 0.0, pulse_duration=0.1)
    assert interp.get_quantized_state(True).ha_mode == "minor"

    interp.update(1.0, 0.0, pulse_duration=0.1)
    assert interp.get_quantized_state(True).ha_mode == "major"

    interp.update(0.0, 1.0, pulse_duration=0.1)
    assert interp.get_quantized_state(True).ha_mode == "minor"

    interp.update(1.0, 1.0, pulse_duration=0.1)
    assert interp.get_quantized_state(True).ha_mode == "major"


def test_interpolator_harmony_mode_waits_for_phrase_boundary():
    interp = MultiParameterPresetInterpolator(PRESET_A, PRESET_B, PRESET_C, PRESET_D, smoothing_time=0.0)
    interp.update(0.0, 0.0, pulse_duration=0.1)
    assert interp.get_quantized_state(True).ha_mode == "minor"

    interp.update(1.0, 0.0, pulse_duration=0.1)
    assert interp.get_quantized_state(False) is None
    assert interp.get_quantized_state(True).ha_mode == "major"
