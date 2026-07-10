import pytest


def test_standard_tuning_builds_all_138_positions():
    try:
        from guitar_fretboard.music_theory import build_fretboard
    except ImportError as error:
        pytest.fail(f"Music-theory API is not implemented: {error}")

    positions = build_fretboard()
    assert len(positions) == 138
    by_location = {(p.string_number, p.fret): p for p in positions}
    assert by_location[1, 0].midi_note == 64
    assert by_location[2, 0].midi_note == 59
    assert by_location[6, 0].midi_note == 40
    assert by_location[1, 12].pitch_name == "E5"
    assert by_location[6, 22].pitch_name == "D4"


def test_equal_temperament_and_fixed_do_labels():
    try:
        from guitar_fretboard.music_theory import (
            midi_to_frequency,
            midi_to_pitch_name,
            midi_to_solfege,
        )
    except ImportError as error:
        pytest.fail(f"Music-theory API is not implemented: {error}")

    assert midi_to_frequency(69) == pytest.approx(440.0)
    assert midi_to_frequency(60) == pytest.approx(261.625565, rel=1e-6)
    assert midi_to_pitch_name(70) == "A♯4"
    assert midi_to_solfege(60) == "Do"
    assert midi_to_solfege(61) == "Do♯"


def test_c_major_and_a_natural_minor_degrees():
    try:
        from guitar_fretboard.music_theory import (
            ScaleKind,
            ScaleSelection,
            scale_degree,
        )
    except ImportError as error:
        pytest.fail(f"Music-theory API is not implemented: {error}")

    c_major = ScaleSelection(0, ScaleKind.MAJOR)
    a_minor = ScaleSelection(9, ScaleKind.NATURAL_MINOR)
    assert [scale_degree(pc, c_major) for pc in (0, 2, 4, 5, 7, 9, 11)] == list(
        range(1, 8)
    )
    assert [scale_degree(pc, a_minor) for pc in (9, 11, 0, 2, 4, 5, 7)] == list(
        range(1, 8)
    )
    assert scale_degree(1, c_major) is None


def test_scale_selector_contains_12_major_and_12_natural_minor_choices():
    try:
        from guitar_fretboard.music_theory import SCALE_OPTIONS, ScaleKind
    except ImportError as error:
        pytest.fail(f"Music-theory API is not implemented: {error}")

    assert len(SCALE_OPTIONS) == 24
    assert sum(s.kind is ScaleKind.MAJOR for s in SCALE_OPTIONS) == 12
    assert sum(s.kind is ScaleKind.NATURAL_MINOR for s in SCALE_OPTIONS) == 12
