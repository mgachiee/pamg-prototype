from src.core.seeded_phrase_generator import SeededPhraseGenerator
from unittest.mock import patch


def test_seeded_phrase_reseeds_only_on_pool_one_reentry():
    generator = SeededPhraseGenerator(base_seed=42)

    initial = generator.process_chord_change(current_chord_pool=1, phrase_length=4)
    assert initial.current_seed == 42

    retained = generator.process_chord_change(current_chord_pool=1, phrase_length=4)
    assert retained == initial

    generator.process_chord_change(current_chord_pool=2, phrase_length=4)
    with patch.object(generator._rng, "randrange", return_value=1), patch.object(
        generator._rhythm_rng, "randrange", return_value=2
    ):
        reentered = generator.process_chord_change(current_chord_pool=1, phrase_length=4)
    assert reentered != retained


def test_zero_seed_changes_on_each_improvisation_tick():
    generator = SeededPhraseGenerator(base_seed=0)

    first = generator.process_chord_change(current_chord_pool=2, phrase_length=4)
    second = generator.process_chord_change(current_chord_pool=2, phrase_length=4)

    assert first.base_seed == second.base_seed == 0
    assert (first.current_seed, first.rhythm_seed) != (
        second.current_seed,
        second.rhythm_seed,
    )
