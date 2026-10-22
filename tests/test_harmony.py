import pytest

from src.core.chord_dictionary import (
    create_chord_dictionary,
    get_voiced_pitch_classes,
    build_ordered_pitch_classes,
    query_pitch_class_set,
)
from src.core.harmony_grammar import HarmonicProgressionSelector
from src.modules.harmony_agent import HarmonyAgent
from src.models.harmony_types import ChordPoolLevel
from src.models.seed_state import SeedState


def test_chord_dictionary_tension_levels():
    chords = create_chord_dictionary(tonic_semitone=0)
    assert "I" in chords
    chord_i = chords["I"]
    # 12 ordered pitch classes
    assert len(chord_i.ordered_pitch_classes) == 12

    # Tension level 1 should yield 1 pitch class, tension 3 yields triad (3 pitch classes)
    voiced_1 = get_voiced_pitch_classes(chord_i, tension_level=1, voice_count=1)
    assert len(voiced_1) == 1

    voiced_triad = get_voiced_pitch_classes(chord_i, tension_level=3, voice_count=3)
    assert len(voiced_triad) == 3


def test_chord_dictionary_explicit_symbol_tension_query():
    assert query_pitch_class_set("I", 3) == [0, 7, 4]
    assert query_pitch_class_set("I", 7) == [0, 7, 4, 11, 2, 5, 9]


def test_harmonic_progression_selector_transitions():
    selector = HarmonicProgressionSelector(tonic_semitone=0, complexity_progression=0.5, seed=42)
    assert selector.current_roman == "I"

    # Step transition
    next_chord = selector.advance_progression()
    assert next_chord.roman in ["IV", "V", "ii", "vi", "V/V", "V/IV"]


def test_chord_pools_reachability():
    # Complexity 0.0 -> max pool 1
    sel_low = HarmonicProgressionSelector(complexity_progression=0.0)
    assert sel_low.get_max_reachable_pool() == ChordPoolLevel.POOL_1

    # Complexity 1.0 -> max pool 4
    sel_high = HarmonicProgressionSelector(complexity_progression=1.0)
    assert sel_high.get_max_reachable_pool() == ChordPoolLevel.POOL_4


def test_harmony_agent_process_tick_and_articulation():
    ha = HarmonyAgent(loop_size=4, grain=4, seed=100)
    # Tick at downbeat (subdivision 0, beat 0)
    events = ha.process_tick(index=0, pulse_duration=0.1)
    assert len(events) > 0
    for ev in events:
        assert "note" in ev
        assert "velocity" in ev
        assert "duration" in ev
        assert "articulation" in ev
        assert ev["articulation"] in ["staccato", "legato"]
        assert ev["source"] == "harmony"


def test_harmony_agent_seed_state_update():
    ha = HarmonyAgent(loop_size=4, grain=4, seed=100)
    state = SeedState(base_seed=50, current_seed=500, rhythm_seed=600)
    changed = ha.update_params(seed_state=state)
    assert changed is True


def test_harmony_natural_minor_mode_changes_diatonic_qualities():
    major = HarmonyAgent(loop_size=4, grain=4, key_root=60, mode="major")
    minor = HarmonyAgent(loop_size=4, grain=4, key_root=60, mode="minor")

    assert major._progression_selector.dictionary["I"].quality == "major"
    assert minor._progression_selector.dictionary["I"].quality == "minor"
    assert minor._progression_selector.dictionary["ii"].quality == "diminished"
    assert minor._progression_selector.dictionary["iii"].quality == "major"
    assert minor._progression_selector.dictionary["vi"].quality == "major"


def test_harmony_minor_mode_reports_documented_roman_labels():
    harmony = HarmonyAgent(loop_size=4, grain=4, key_root=60, mode="minor")
    harmony._current_chord_def = harmony._progression_selector.dictionary["I"]
    assert harmony.get_roman_numeral() == "i"

    harmony._current_chord_def = harmony._progression_selector.dictionary["ii"]
    assert harmony.get_roman_numeral() == "ii°"


def test_harmony_mode_update_rebuilds_current_chord():
    harmony = HarmonyAgent(loop_size=4, grain=4, key_root=60, mode="major")
    assert harmony._current_chord_def.quality == "major"

    assert harmony.update_params(ha_mode="minor") is True
    assert harmony.mode == "minor"
    assert harmony._current_chord_def.quality == "minor"


def test_harmony_post_filter_with_no_overlap_is_silent():
    harmony = HarmonyAgent(loop_size=4, grain=4, key_root=60, mode="major")
    harmony.set_post_filter([1])

    assert harmony.get_chord_pitch_classes() == []
    assert harmony.process_tick(index=0, pulse_duration=0.1) == []


def test_harmony_agent_get_chord_pitch_classes():
    ha = HarmonyAgent(loop_size=4, grain=4, key_root=60, tension=1.0)
    pcs_1 = ha.get_chord_pitch_classes()
    assert len(pcs_1) == 1
    assert pcs_1 == [0]

    # Tension 3: root triad (root, 5th, 3rd)
    ha.update_params(tension=3.0)
    pcs_3 = ha.get_chord_pitch_classes()
    assert len(pcs_3) == 3
    assert set(pcs_3) == {0, 7, 4}

    # Tension 10: includes upper tertian extensions and borrowed parallel-minor tones (3, 10, 8)
    ha.update_params(tension=10.0)
    pcs_10 = ha.get_chord_pitch_classes()
    assert len(pcs_10) == 10
    # Level 8-10 borrowed minor tones (Eb=3, Bb=10, Ab=8)
    for minor_pc in (3, 10, 8):
        assert minor_pc in pcs_10


def test_harmony_agent_dynamic_velocity_scaling():
    """Verify ha_vel_ins updates normal and accent velocity ranges dynamically (§3.2, §4.4, §4.5)."""
    ha = HarmonyAgent(loop_size=4, grain=4, seed=100)
    # Preset A (Somber / Subdued): vel 42.0 (pianissimo)
    ha.update_params(ha_vel_ins=42.0)
    assert ha.velocity == 42.0
    assert ha._normal_velocity_range == (36, 48)
    assert ha._accent_velocity_range == (48, 58)

    # Preset C (Tense / Combat): vel 105.0 (fortissimo)
    ha.update_params(ha_vel_ins=105.0)
    assert ha.velocity == 105.0
    assert ha._normal_velocity_range == (99, 111)
    assert ha._accent_velocity_range == (111, 121)


def test_harmony_agent_low_tension_arpeggiator_gating():
    """Verify that low tension (<= 3.0) gates off broken arpeggiation and voices sustained block chords."""
    ha = HarmonyAgent(loop_size=4, grain=4, seed=100, tension=1.0)
    assert ha._should_arpeggiate() is False

    ha.update_params(tension=3.0)
    assert ha._should_arpeggiate() is False

    # Intermediate tension (e.g. 5.0) activates arpeggiation
    ha.on_phrase_start()
    ha.update_params(tension=5.0)
    assert ha._should_arpeggiate() is True

    # High tension (e.g. 11.5) switches back to full block chords
    ha.update_params(tension=11.5)
    assert ha._should_arpeggiate() is False


