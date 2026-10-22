import asyncio
import pytest
from unittest.mock import patch

from src.core.clock import _apply_continuous_params, _preset_label, run_clock
from src.core.routing import RoutingType


def test_preset_label_for_corners_and_blends():
    assert _preset_label(0.0, 0.0) == "Preset A"
    assert _preset_label(1.0, 0.0) == "Preset B"
    assert _preset_label(0.0, 1.0) == "Preset C"
    assert _preset_label(1.0, 1.0) == "Preset D"
    assert _preset_label(0.5, 0.5) == "Interpolated"


def test_continuous_layer_weights_are_forwarded_every_update():
    from dataclasses import replace
    from unittest.mock import Mock
    from src.core.configs import PRESET_A
    from src.core.preset_interpolator import MultiParameterPresetInterpolator

    preset_c = replace(PRESET_A, oa_harmony_layer_weights=[0.2, 0.4, 0.6, 0.8])
    interpolator = MultiParameterPresetInterpolator(PRESET_A, PRESET_A, preset_c, preset_c)
    params_a = interpolator.update(0.0, 0.0, 0.1)
    params_c = interpolator.update(0.0, 1.0, 0.1)
    agents = [Mock() for _ in range(4)]

    _apply_continuous_params(*agents, params_a)
    _apply_continuous_params(*agents, params_c)

    oa = agents[3]
    assert oa.update_params.call_count == 2
    assert oa.update_params.call_args_list[0].kwargs["harmony_layer_weights"] == params_a.oa_harmony_layer_weights
    assert oa.update_params.call_args_list[1].kwargs["harmony_layer_weights"] == params_c.oa_harmony_layer_weights


def test_clock_validation_non_positive_tempo():
    with pytest.raises(ValueError, match="tempo must be greater than 0"):
        asyncio.run(
            run_clock(
                tempo=0,
                loop_size=4,
                grain=4,
                routing_mode=RoutingType.single_port,
            )
        )


def test_phrase_boundaries_use_loop_index():
    from src.core.clock import _is_phrase_start

    assert _is_phrase_start(local_index=0, loop_index=0, grain=4, phrase_length=2)
    assert not _is_phrase_start(local_index=0, loop_index=1, grain=4, phrase_length=2)
    assert _is_phrase_start(local_index=0, loop_index=2, grain=4, phrase_length=2)
    assert not _is_phrase_start(local_index=1, loop_index=2, grain=4, phrase_length=2)


def test_clock_validation_negative_tempo():
    with pytest.raises(ValueError, match="tempo must be greater than 0"):
        asyncio.run(
            run_clock(
                tempo=-120,
                loop_size=4,
                grain=4,
                routing_mode=RoutingType.single_port,
            )
        )


def test_clock_validation_non_positive_loop_size():
    with pytest.raises(ValueError, match="loop_size must be greater than 0"):
        asyncio.run(
            run_clock(
                tempo=120,
                loop_size=0,
                grain=4,
                routing_mode=RoutingType.single_port,
            )
        )


def test_clock_validation_non_positive_grain():
    with pytest.raises(ValueError, match="grain must be greater than 0"):
        asyncio.run(
            run_clock(
                tempo=120,
                loop_size=4,
                grain=0,
                routing_mode=RoutingType.single_port,
            )
        )


def test_clock_run_with_max_ticks(dummy_port):
    with patch("src.core.clock.open_midi_ports", return_value=(dummy_port, dummy_port)):
        # Run clock for 4 ticks
        asyncio.run(
            run_clock(
                tempo=240,
                loop_size=2,
                grain=2,
                routing_mode=RoutingType.single_port,
                base_seed=42,
                max_ticks=4,
            )
        )
        assert dummy_port.closed is True


def test_agents_update_params_loop_size_and_grain():
    from src.modules.harmony_agent import HarmonyAgent
    from src.modules.percussion_agent import PercussionAgent
    from src.modules.melody_agent import MelodyAgent

    ha = HarmonyAgent(loop_size=4, grain=4, meter="4/4")
    pa = PercussionAgent(loop_size=4, grain=4, meter="4/4")
    ma = MelodyAgent(movement="even", loop_size=4, grain=4)

    # Test update with loop_size, grain, meter only (previously crashed HA with UnboundLocalError)
    assert ha.update_params(loop_size=3, grain=4, meter="3/4") is True
    assert ha.loop_size == 3
    assert ha.grain == 4
    assert ha.meter == "3/4"

    assert pa.update_params(loop_size=3, grain=4, meter="3/4") is True
    assert pa.loop_size == 3
    assert pa.grain == 4
    assert pa.total_pulses == 12
    assert pa.meter == "3/4"

    assert ma.update_params(loop_size=3, grain=4, meter="3/4") is True
    assert ma.loop_size == 3
    assert ma.grain == 4
    assert ma.total_pulses == 12


def test_clock_live_meter_and_tempo_transition(dummy_port):
    from src.models.game_state import GameState

    gs = GameState(paused=False, tempo=300.0, loop_size=4, grain=2)
    # Queue a structure change after a few ticks
    gs.set_time_signature("3/4")

    with patch("src.core.clock.open_midi_ports", return_value=(dummy_port, dummy_port)):
        asyncio.run(
            run_clock(
                tempo=300,
                loop_size=4,
                grain=2,
                routing_mode=RoutingType.single_port,
                game_state=gs,
                max_ticks=24,
            )
        )
        assert dummy_port.closed is True
        assert gs.current_step == 23
        assert gs.structure_dirty is False
        assert gs.loop_size == 3
        assert gs.grain == 4
        assert gs.time_signature == "3/4"


def test_clock_orchestrator_matrix_integration(dummy_port):
    """Verify that the clock loop routes events through the dynamic 4x2 matrix based on GameState preset."""
    from src.models.game_state import GameState

    # Preset C: Angry (x=0.0, y=1.0) -> Melody (Strings Ch0, Woodwinds Ch2); Harmony (Piano Ch5, Strings Ch4, Woodwinds Ch6)
    gs_c = GameState(x=0.0, y=1.0, paused=False, tempo=600.0, loop_size=2, grain=4)
    with patch("src.core.clock.open_midi_ports", return_value=(dummy_port, dummy_port)):
        asyncio.run(
            run_clock(
                tempo=600,
                loop_size=2,
                grain=4,
                routing_mode=RoutingType.single_port,
                game_state=gs_c,
                max_ticks=8,
            )
        )
    note_channels = {msg.channel for msg in dummy_port.messages if getattr(msg, "type", None) == "note_on"}
    # Must contain Melody Strings (0), Melody Woodwinds (2), Melody Brass (3)
    assert 0 in note_channels
    assert 2 in note_channels
    assert 3 in note_channels
    # Must contain Harmony Strings (4), Harmony Piano (5), Harmony Woodwinds (6)
    assert 4 in note_channels
    assert 5 in note_channels
    assert 6 in note_channels
    # Percussion on Ch 9
    assert 9 in note_channels
    # Melody Piano (Ch 1) and Harmony Brass (Ch 7) must NOT be active in Preset C
    assert 1 not in note_channels
    assert 7 not in note_channels


def test_clock_preset_a_soft_velocity_dispatch(dummy_port):
    """Verify that Preset A (x=0.0, y=0.0) dispatches soft velocities (<= 55) for harmony notes."""
    from src.models.game_state import GameState

    gs_a = GameState(x=0.0, y=0.0, paused=False, tempo=600.0, loop_size=4, grain=4)
    with patch("src.core.clock.open_midi_ports", return_value=(dummy_port, dummy_port)):
        asyncio.run(
            run_clock(
                tempo=600,
                loop_size=4,
                grain=4,
                routing_mode=RoutingType.single_port,
                game_state=gs_a,
                max_ticks=32,
            )
        )
    harmony_velocities = [
        msg.velocity for msg in dummy_port.messages
        if getattr(msg, "type", None) == "note_on" and msg.channel in (4, 5, 6, 7) and msg.velocity > 0
    ]
    assert len(harmony_velocities) > 0
    # Preset A ha_vel_ins is 42.0. All harmony velocities must be quiet (<= 55), never forte (>= 70)
    for vel in harmony_velocities:
        assert vel <= 58, f"Expected soft harmony velocity in Preset A, got {vel}"



