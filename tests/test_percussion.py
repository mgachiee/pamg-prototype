import pytest

from src.modules.percussion_agent import PercussionAgent
from src.models.seed_state import SeedState


def test_percussion_lookahead_and_grid():
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    lookahead = pa.get_lookahead(current_index=0, lookahead_steps=8)
    assert len(lookahead) == 8
    assert all(isinstance(v, bool) for v in lookahead)


def test_percussion_channel_and_events():
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    # Turn probabilities up to guarantee events
    pa.update_params(
        kick_sub_prob=0.0,
        snare_sub_prob=0.0,
        hat_open_prob=1.0,
    )
    events = pa.process_tick(index=0)
    assert len(events) > 0
    for ev in events:
        # Percussion must direct-route to MIDI channel 9 (0-indexed standard for drum channel 10)
        assert ev["channel"] == 9
        assert 0 <= ev["note"] <= 127
        assert 0 <= ev["velocity"] <= 127


def test_percussion_phrase_fill_on_pool_1_entry():
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    # Transition from pool 2 to pool 1
    pa.notify_chord_change(2)
    assert pa._pending_phrase_fill is False
    pa.notify_chord_change(1)
    assert pa._pending_phrase_fill is True


def test_percussion_seed_state_update():
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    state = SeedState(base_seed=100, current_seed=200, rhythm_seed=300)
    changed = pa.update_params(seed_state=state)
    assert changed is True


def test_percussion_baseline_voices_only():
    """Ensure Percussion Agent emits only the 4 baseline rows: Kick, Snare, Toms, Cymbals."""
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa.update_params(pa_ks_plus_minus=0.5, pa_toms_plus_minus=0.5, pa_cymb_plus_minus=0.5)

    allowed_notes = {
        pa.KICK, pa.SNARE, pa.SNARE_ROLL, pa.SIDE_STICK, pa.TOM_LOW, pa.TOM_MID, pa.TOM_HIGH, pa.CYMBAL, pa.CRASH
    }
    forbidden_notes = {46, 51, 53}  # Open hi-hat, ride, ride bell

    all_emitted_notes = set()
    for tick in range(16):
        events = pa.process_tick(tick)
        for ev in events:
            all_emitted_notes.add(ev["note"])

    assert all_emitted_notes.issubset(allowed_notes)
    assert len(all_emitted_notes.intersection(forbidden_notes)) == 0
    assert 42 not in all_emitted_notes  # GM 42 is closed hi-hat, not the orchestral cymbal row


def test_percussion_high_energy_keeps_kick_and_snare_on_template_beats():
    """Positive KS increases intensity without adding a pop/rock backbeat grid."""
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa.update_params(pa_ks_plus_minus=0.8, pa_toms_plus_minus=0.8, pa_cymb_plus_minus=0.8)

    for tick in range(16):
        for event in pa.process_tick(tick):
            if event["note"] in (pa.KICK, pa.SNARE):
                assert tick % pa.grain == 0


def test_percussion_snare_articulation_by_velocity():
    """Verify that pa_vel_perc < 60 selects SIDE_STICK (37) and >= 60 selects SNARE (38)."""
    pa_soft = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa_soft.update_params(pa_vel_perc=45.0, pa_ks_plus_minus=0.5)
    soft_notes = set()
    for tick in range(16):
        for ev in pa_soft.process_tick(tick):
            soft_notes.add(ev["note"])
    assert pa_soft.SIDE_STICK in soft_notes
    assert pa_soft.SNARE not in soft_notes

    pa_loud = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa_loud.update_params(pa_vel_perc=90.0, pa_ks_plus_minus=0.5)
    loud_notes = set()
    for tick in range(16):
        for ev in pa_loud.process_tick(tick):
            loud_notes.add(ev["note"])
    assert pa_loud.SNARE in loud_notes
    assert pa_loud.SIDE_STICK not in loud_notes


def test_percussion_velocity_ranges_scale_with_param():
    """Verify ghost and fill velocity ranges scale dynamically with pa_vel_perc."""
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa.update_params(pa_vel_perc=40.0)
    assert pa.ghost_velocity_range[1] <= 35
    assert pa.tom_fill_velocity_range[0] <= 35

    pa.update_params(pa_vel_perc=110.0)
    assert pa.ghost_velocity_range[1] >= 70
    assert pa.tom_fill_velocity_range[0] >= 75


def test_percussion_velocity_update_preserves_planned_fills():
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    planned = pa.subfills
    before = [event["velocity"] for events in planned.values() for event in events]

    pa.update_params(pa_vel_perc=70.0)
    after = [event["velocity"] for events in pa.subfills.values() for event in events]

    assert pa.subfills is planned
    assert pa.normal_velocity_range[0] == 55
    assert before != after


def test_percussion_receives_melody_moved_list_for_accent_following():
    plain = PercussionAgent(loop_size=4, grain=4, seed=42)
    plain.update_params(pa_acc_beat_p=0.0)
    plain.on_loop_start(0)
    plain_event = plain.process_tick(8)[0]

    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa.update_params(pa_acc_beat_p=0.0)
    pa.notify_moved_list([8])
    pa.on_loop_start(0)
    moved_event = pa.process_tick(8)[0]

    assert pa._moved_list == {8}
    assert moved_event["velocity"] > plain_event["velocity"]


def test_percussion_calm_preset_row_gating():
    """Verify that when toms and cymbals delta <= 0, zero toms and cymbals are emitted (§5.3)."""
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa.update_params(pa_ks_plus_minus=-0.5, pa_toms_plus_minus=-1.0, pa_cymb_plus_minus=-1.0)

    tom_notes = {pa.TOM_LOW, pa.TOM_MID, pa.TOM_HIGH}
    for loop_idx in range(5):
        pa.on_loop_start(loop_idx)
        for tick in range(16):
            events = pa.process_tick(tick)
            for ev in events:
                assert ev["note"] not in tom_notes, f"Unexpected tom note in calm state: {ev['note']}"
                assert ev["note"] != pa.CYMBAL, "Unexpected crash cymbal in calm state"


def test_percussion_snare_suppressed_in_negative_ks():
    """Verify that when pa_ks_plus_minus < -0.2, the snare backbeat is completely gated off."""
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa.update_params(pa_ks_plus_minus=-0.5, pa_toms_plus_minus=-1.0, pa_cymb_plus_minus=-1.0)

    for loop_idx in range(5):
        pa.on_loop_start(loop_idx)
        for tick in range(16):
            events = pa.process_tick(tick)
            for ev in events:
                assert ev["note"] != pa.SNARE, "Snare drum backbeat must be silenced in negative KS state"


def test_percussion_dynamic_contrast_across_presets():
    """Verify that calm presets (A, B) have dramatically lower drum density than combat/action (C, D)."""
    from src.core.configs import DEFAULT_PRESETS
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)

    hits_per_preset = []
    for preset in DEFAULT_PRESETS:
        pa.update_params(
            pa_vel_perc=float(preset.pa_vel_perc),
            pa_acc_beat_p=float(preset.pa_acc_beat_p),
            pa_ks_plus_minus=float(preset.pa_ks_plus_minus),
            pa_toms_plus_minus=float(preset.pa_toms_plus_minus),
            pa_cymb_plus_minus=float(preset.pa_cymb_plus_minus),
            phrase_length=int(preset.seeded_phrase_length),
        )
        total_hits = 0
        for loop_idx in range(5):
            pa.on_loop_start(loop_idx)
            for tick in range(16):
                total_hits += len(pa.process_tick(tick))
        hits_per_preset.append(total_hits)

    hits_a, hits_b, hits_c, hits_d = hits_per_preset
    assert 1 <= hits_a <= 15  # Preset A: Somber / Ambient has subtle, sparse orchestral color
    assert 3 <= hits_b <= 25  # Preset B: Calm / Sanctuary has gentle downbeats and side-stick
    assert hits_c >= 50  # Preset C: Danger / Combat has high drum activity
    assert hits_d >= 30  # Preset D: Action / Heroic has driving orchestral activity
    assert hits_c > hits_a * 4


def test_percussion_orchestral_drum_rolls_and_crescendo():
    """Verify that orchestral snare and timpani rolls emit ratchet events with extended durations."""
    pa = PercussionAgent(loop_size=4, grain=4, seed=42)
    pa.update_params(
        pa_vel_perc=90.0,
        pa_ks_plus_minus=0.8,
        pa_toms_plus_minus=0.8,
        pa_cymb_plus_minus=0.5,
        phrase_length=4,
    )
    # Trigger phrase fill
    pa.notify_chord_change(1)

    ratchet_events = []
    for loop_idx in range(8):
        pa.on_loop_start(loop_idx)
        for tick in range(16):
            events = pa.process_tick(tick)
            for ev in events:
                if ev.get("is_ratchet"):
                    ratchet_events.append(ev)

    assert len(ratchet_events) > 0
    for ev in ratchet_events:
        assert ev["ratchet_count"] >= 4
        # Drum rolls must have extended duration (at least 0.35s) for smooth crescendo swells
        assert ev.get("duration", 0.0) >= 0.35


