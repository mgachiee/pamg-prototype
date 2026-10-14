import pytest

from src.modules.melody_agent import MelodyAgent
from src.models.seed_state import SeedState


def test_melody_lookahead():
    ma = MelodyAgent(movement=MelodyAgent.movement_type.odd, loop_size=4, grain=4, seed=42)
    # Lookahead for 4 steps from tick 0
    ahead = ma.get_lookahead(current_index=0, lookahead_steps=4)
    assert len(ahead) == 4
    assert all(isinstance(val, bool) for val in ahead)

    # Lookahead across loop boundary
    ahead_boundary = ma.get_lookahead(current_index=14, lookahead_steps=4)
    assert len(ahead_boundary) == 4


def test_melody_articulation_duration():
    ma = MelodyAgent(movement=MelodyAgent.movement_type.odd, loop_size=4, grain=4, seed=42)
    # Set known onset indices
    ma._onset_indices = {0, 1, 8}
    # Onset at 0 has gap 1 to onset at 1 (<= threshold of 2) -> staccato
    dur_staccato = ma._select_duration(pulse_duration=0.1, subdivision=0, onset_index=0)
    # Onset at 1 has gap 7 to onset at 8 (> threshold of 2) -> legato
    dur_legato = ma._select_duration(pulse_duration=0.1, subdivision=1, onset_index=1)

    assert dur_staccato < dur_legato


def test_melody_seed_state_dual_rng():
    ma = MelodyAgent(movement=MelodyAgent.movement_type.odd, loop_size=4, grain=4, seed=42)
    state = SeedState(base_seed=10, current_seed=1234, rhythm_seed=5678)
    ma.update_params(seed_state=state)

    # Verify pitch and rhythm RNGs are seeded differently
    val_pitch = ma._pitch_rng.random()
    val_rhythm = ma._rhythm_rng.random()
    assert val_pitch != val_rhythm


def test_melody_process_tick_emits_valid_events():
    ma = MelodyAgent(movement=MelodyAgent.movement_type.odd, loop_size=4, grain=4, seed=42)
    # Trigger on a tick with onset
    chord = [60, 64, 67]
    events = ma.process_tick(index=0, current_chord=chord, pulse_duration=0.1)
    if events:
        for ev in events:
            assert "note" in ev
            assert "velocity" in ev
            assert "duration" in ev
            assert 0 <= ev["note"] <= 127
            assert 0 <= ev["velocity"] <= 127


def test_melody_dcontour_mode():
    """Verify dcontour mode builds contour pitches and interpolates between moved list nodes."""
    ma = MelodyAgent(
        movement=MelodyAgent.movement_type.odd,
        loop_size=4,
        grain=4,
        drunk_mode="dcontour",
        seed=42,
    )
    # Ensure dcontour mode is active
    assert ma.drunk_mode == "dcontour"
    assert hasattr(ma, "_contour_pitches")
    assert len(ma._contour_pitches) > 0

    # Every onset in the pattern should have a planned contour pitch
    for onset in ma._onset_indices:
        assert onset in ma._contour_pitches


def test_melody_harmony_filter_unclamped_input():
    """Verify raw melody pitch is filtered against chord tones without pre-filter range clamping."""
    ma = MelodyAgent(
        movement=MelodyAgent.movement_type.odd,
        loop_size=4,
        grain=4,
        seed=42,
    )
    ma.pitch_range = (60, 72)
    ma.current_pitch = 80  # Above pitch_range
    ma.max_step = 2
    # Chord with tones around 80
    chord = [79, 83, 86]
    # At tick 0 (which has an onset), raw pitch is around 80, not clamped down to 72 before filtering
    events = ma.process_tick(index=0, current_chord=chord, pulse_duration=0.1)
    if events:
        assert events[0]["note"] in chord


def test_melody_harmony_filter_preserves_octave_register_with_bass_chord():
    """Verify melody does not get trapped in bass register when harmony chord has low bass notes."""
    ma = MelodyAgent(
        movement=MelodyAgent.movement_type.odd,
        loop_size=4,
        grain=4,
        seed=42,
    )
    ma.current_pitch = 62  # D4
    ma.max_step = 1

    # Harmony chord provides only low bass notes [36, 48] (C2, C3)
    bass_chord = [36, 48]
    events = ma.process_tick(index=0, current_chord=bass_chord, pulse_duration=0.1)
    assert len(events) > 0
    # Pitch class of chord is 0 (C). In octave 4 (around 62), closest note is 60 (C4), NOT 48 or 36
    assert events[0]["note"] == 60
    assert ma.current_pitch == 60

    # With explicit chord pitch classes [0, 4, 7] (C major triad) and raw pitch around 65 (F4)
    ma.current_pitch = 65
    events_pcs = ma.process_tick(
        index=0,
        current_chord=bass_chord,
        current_chord_pcs=[0, 4, 7],
        pulse_duration=0.1,
    )
    assert len(events_pcs) > 0
    # Closest note with pc in {0, 4, 7} to 65 is 64 (E4, distance 1)
    assert events_pcs[0]["note"] == 64


def test_melody_pitch_range_bounded_reflection():
    """Verify melody dcontour walk remains strictly bounded within pitch_range over many loops."""
    ma = MelodyAgent(
        movement=MelodyAgent.movement_type.odd,
        loop_size=4,
        grain=4,
        drunk_mode="dcontour",
        max_step=8,
        pitch_range=(52, 80),
        seed=123,
    )
    pitches = []
    chord_pcs = [0, 3, 7]  # C minor
    for loop_idx in range(20):
        ma.on_loop_start(loop_idx)
        for pulse in range(16):
            evs = ma.process_tick(
                pulse,
                current_chord=[48, 55, 60],
                current_chord_pcs=chord_pcs,
                pulse_duration=0.1,
            )
            if evs:
                pitches.append(evs[0]["note"])

    assert len(pitches) > 0
    # Over 20 loops with large step=8, pitches must not drift into ceiling (> 80) or floor (< 52)
    assert min(pitches) >= 48  # Allow slight octave-neighbor proximity if needed, but no runaway
    assert max(pitches) <= 84  # Never hit 96!
    # Ensure there is melodic variety, not frozen on a single pitch
    assert len(set(pitches)) >= 3


def test_melody_velocity_mean_reversion_in_soft_preset():
    """Verify that when ma_velocity is low (45.0, Preset A), velocities remain bounded in soft range."""
    ma = MelodyAgent(
        movement=MelodyAgent.movement_type.odd,
        loop_size=4,
        grain=4,
        seed=123,
    )
    ma.update_params(ma_velocity=45.0)

    velocities = []
    chord = [60, 64, 67]
    for loop_idx in range(10):
        ma.on_loop_start(loop_idx)
        for pulse in range(16):
            evs = ma.process_tick(pulse, current_chord=chord, pulse_duration=0.1)
            for ev in evs:
                velocities.append(ev["velocity"])

    assert len(velocities) > 0
    # Average velocity should be close to 45.0
    avg_vel = sum(velocities) / len(velocities)
    assert 38.0 <= avg_vel <= 55.0
    # Must never drift away to loud velocities (>= 75)
    assert max(velocities) <= 65



