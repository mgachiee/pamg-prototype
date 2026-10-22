import pytest

from src.modules.orchestrator_agent import OrchestratorAgent


def test_orchestrator_melody_lines_gating():
    oa = OrchestratorAgent(
        melody_channels=[0, 1],
        harmony_channels=[2, 3, 4],
        ma_orch_plus_minus=0.2,  # < 0.5 -> single melody channel
    )
    events = oa.process_tick(melody_events=[{"note": 60, "velocity": 100}])
    channels = [e["channel"] for e in events]
    assert channels == [0]

    # Increase ma_orch_plus_minus >= 0.5 -> double melody channels
    oa.update_params(ma_orch_plus_minus=0.8)
    events_doubled = oa.process_tick(melody_events=[{"note": 60, "velocity": 100}])
    channels_doubled = [e["channel"] for e in events_doubled]
    assert channels_doubled == [0, 1]


def test_orchestrator_harmony_instruments_gating():
    oa = OrchestratorAgent(
        melody_channels=[0],
        harmony_channels=[2, 3, 4],
        harmony_layer_weights=[1.0, 1.0, 1.0],
        ha_ins_plus_minus=0.0,  # min count -> 1 channel
    )
    events = oa.process_tick(
        melody_events=[],
        harmony_events=[{"note": 48, "velocity": 90}],
    )
    channels = [e["channel"] for e in events]
    assert channels == [2]

    # Full ha_ins_plus_minus -> all 3 channels
    oa.update_params(ha_ins_plus_minus=1.0)
    events_full = oa.process_tick(
        melody_events=[],
        harmony_events=[{"note": 48, "velocity": 90}],
    )
    channels_full = [e["channel"] for e in events_full]
    assert channels_full == [2, 3, 4]


def test_orchestrator_deduplicates_unchanged_harmony_cc_values():
    oa = OrchestratorAgent(harmony_channels=[2], harmony_layer_weights=[1.0])
    oa.consume_cc_changes()

    oa.update_params(harmony_layer_weights=[1.0])
    assert oa.consume_cc_changes() == []

    oa.update_params(harmony_layer_weights=[0.5])
    assert oa.consume_cc_changes() == [(2, 11, 64)]


def test_orchestrator_range_clamping():
    oa = OrchestratorAgent(
        melody_channels=[0],
        harmony_channels=[2],
        melody_range=(60, 72),
        harmony_range=(40, 55),
    )
    # High melody note clamped to 72
    m_ev = oa.process_tick(melody_events=[{"note": 90, "velocity": 100}])
    assert m_ev[0]["note"] == 72

    # Low harmony note clamped to 40
    h_ev = oa.process_tick(melody_events=[], harmony_events=[{"note": 20, "velocity": 80}])
    assert h_ev[0]["note"] == 40


def test_orchestrator_4x2_melody_doubling():
    """Verify 4x2 matrix melody doubling levels across Strings, Woodwinds, and Brass."""
    oa = OrchestratorAgent(
        melody_channels=[0, 1, 2, 3],  # Strings, Piano, Woodwinds, Brass
        harmony_channels=[4, 5, 6, 7],
        ma_orch_plus_minus=0.2,  # < 0.4 -> Solo Strings
    )
    # Solo Strings (Ch 0)
    ev_solo = oa.process_tick(melody_events=[{"note": 64, "velocity": 90}])
    assert [e["channel"] for e in ev_solo] == [0]

    # Strings + Woodwinds doubling (Ch 0, Ch 2)
    oa.update_params(ma_orch_plus_minus=0.5)
    ev_wood = oa.process_tick(melody_events=[{"note": 64, "velocity": 90}])
    assert [e["channel"] for e in ev_wood] == [0, 2]

    # Strings + Woodwinds + Brass tutti doubling (Ch 0, Ch 2, Ch 3)
    oa.update_params(ma_orch_plus_minus=0.9)
    ev_tutti = oa.process_tick(melody_events=[{"note": 64, "velocity": 90}])
    assert [e["channel"] for e in ev_tutti] == [0, 2, 3]


def test_orchestrator_4x2_harmony_registration_and_layering():
    """Verify 4x2 matrix harmony registration (ha_register_ins) and density (ha_ins_plus_minus)."""
    oa = OrchestratorAgent(
        melody_channels=[0, 1, 2, 3],
        harmony_channels=[4, 5, 6, 7],  # Strings, Piano, Woodwinds, Brass
        harmony_layer_weights=[1.0, 1.0, 1.0, 1.0],
        ha_register_ins=1.0,  # Reg level 1: Piano (Ch 5)
        ha_ins_plus_minus=0.0,
    )
    # Preset A/B condition: Solo Piano (Ch 5)
    ev_a = oa.process_tick(melody_events=[], harmony_events=[{"note": 48, "velocity": 80}])
    assert [e["channel"] for e in ev_a] == [5]

    # Reg level 2: Piano + Strings (Ch 5, Ch 4)
    oa.update_params(ha_register_ins=2.0, ha_ins_plus_minus=1.0)
    ev_reg2 = oa.process_tick(melody_events=[], harmony_events=[{"note": 48, "velocity": 80}])
    assert [e["channel"] for e in ev_reg2] == [5, 4]

    # Preset C condition: Reg level 3 (Piano, Strings, Woodwinds) -> Ch 5, 4, 6
    oa.update_params(ha_register_ins=3.0, ha_ins_plus_minus=0.8)
    ev_c = oa.process_tick(melody_events=[], harmony_events=[{"note": 48, "velocity": 80}])
    assert [e["channel"] for e in ev_c] == [5, 4, 6]

    # Preset D condition: Reg level 4, full tutti (Ch 5, 4, 6, 7)
    oa.update_params(ha_register_ins=4.0, ha_ins_plus_minus=1.0)
    ev_d = oa.process_tick(melody_events=[], harmony_events=[{"note": 48, "velocity": 80}])
    assert [e["channel"] for e in ev_d] == [5, 4, 6, 7]


def test_orchestrator_program_changes_and_initialization():
    """Verify program changes for 8 orchestral channels matching REAPER tracks 1-8."""
    from src.core.configs import (
        MELODY_CHANNELS,
        HARMONY_CHANNELS,
        MELODY_PROGRAMS,
        HARMONY_PROGRAMS,
    )

    oa = OrchestratorAgent(
        melody_channels=MELODY_CHANNELS,
        harmony_channels=HARMONY_CHANNELS,
        melody_programs=MELODY_PROGRAMS,
        harmony_programs=HARMONY_PROGRAMS,
    )
    pc = oa.consume_program_changes()
    expected = [
        (0, 48),  # Melody Strings
        (1, 0),   # Melody Piano
        (2, 73),  # Melody Woodwinds (Flute)
        (3, 61),  # Melody Brass
        (4, 48),  # Harmony Strings
        (5, 0),   # Harmony Piano
        (6, 73),  # Harmony Woodwinds
        (7, 61),  # Harmony Brass
    ]
    assert pc == expected


def test_orchestrator_allows_32nd_arpeggio_only_for_solo_piano():
    event = {
        "note": 60,
        "velocity": 80,
        "is_arpeggio": True,
        "arpeggio_rate_denominator": 32,
    }
    oa = OrchestratorAgent(
        melody_channels=[0, 1, 2, 3],
        harmony_channels=[4, 5, 6, 7],
        ha_register_ins=1,
        ha_ins_plus_minus=1.0,
    )
    oa.update_params(
        channel_families={4: "strings", 5: "keys", 6: "woodwinds", 7: "brass"},
    )

    # Registration priority selects Piano as the only active harmony layer.
    assert len(oa.process_tick([], [event])) == 1

    oa.update_params(ha_register_ins=2)
    assert oa.process_tick([], [event]) == []

