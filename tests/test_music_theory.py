import pytest


SCALE_CASES = (
    (0, "Major", (0, 2, 4, 5, 7, 9, 11), "C Major"),
    (1, "Major", (0, 2, 4, 5, 7, 9, 11), "D♭ Major"),
    (2, "Major", (0, 2, 4, 5, 7, 9, 11), "D Major"),
    (3, "Major", (0, 2, 4, 5, 7, 9, 11), "E♭ Major"),
    (4, "Major", (0, 2, 4, 5, 7, 9, 11), "E Major"),
    (5, "Major", (0, 2, 4, 5, 7, 9, 11), "F Major"),
    (6, "Major", (0, 2, 4, 5, 7, 9, 11), "F♯ Major"),
    (7, "Major", (0, 2, 4, 5, 7, 9, 11), "G Major"),
    (8, "Major", (0, 2, 4, 5, 7, 9, 11), "A♭ Major"),
    (9, "Major", (0, 2, 4, 5, 7, 9, 11), "A Major"),
    (10, "Major", (0, 2, 4, 5, 7, 9, 11), "B♭ Major"),
    (11, "Major", (0, 2, 4, 5, 7, 9, 11), "B Major"),
    (0, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "C Natural Minor"),
    (1, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "C♯ Natural Minor"),
    (2, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "D Natural Minor"),
    (3, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "E♭ Natural Minor"),
    (4, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "E Natural Minor"),
    (5, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "F Natural Minor"),
    (6, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "F♯ Natural Minor"),
    (7, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "G Natural Minor"),
    (8, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "G♯ Natural Minor"),
    (9, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "A Natural Minor"),
    (10, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "B♭ Natural Minor"),
    (11, "Natural Minor", (0, 2, 3, 5, 7, 8, 10), "B Natural Minor"),
)


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


@pytest.mark.parametrize(
    ("root", "kind_value", "intervals", "expected_label"),
    SCALE_CASES,
)
def test_all_scale_degrees_exclusions_and_conventional_labels(
    root,
    kind_value,
    intervals,
    expected_label,
):
    from guitar_fretboard.music_theory import ScaleKind, ScaleSelection, scale_degree

    selection = ScaleSelection(root, ScaleKind(kind_value))
    included_pitch_classes = tuple(
        (root + interval) % 12 for interval in intervals
    )
    excluded_pitch_classes = set(range(12)) - set(included_pitch_classes)

    assert [scale_degree(pc, selection) for pc in included_pitch_classes] == list(
        range(1, 8)
    )
    assert all(
        scale_degree(pc, selection) is None for pc in excluded_pitch_classes
    )
    assert selection.label == expected_label


def test_scale_selector_contains_12_major_and_12_natural_minor_choices():
    try:
        from guitar_fretboard.music_theory import SCALE_OPTIONS, ScaleKind
    except ImportError as error:
        pytest.fail(f"Music-theory API is not implemented: {error}")

    assert len(SCALE_OPTIONS) == 24
    assert sum(s.kind is ScaleKind.MAJOR for s in SCALE_OPTIONS) == 12
    assert sum(s.kind is ScaleKind.NATURAL_MINOR for s in SCALE_OPTIONS) == 12
    assert [selection.label for selection in SCALE_OPTIONS] == [
        case[3] for case in SCALE_CASES
    ]


@pytest.mark.parametrize("invalid_kind", ["Major", None, object()])
def test_scale_selection_rejects_non_scale_kind_values(invalid_kind):
    from guitar_fretboard.music_theory import ScaleSelection

    with pytest.raises(TypeError, match="kind must be a ScaleKind"):
        ScaleSelection(0, invalid_kind)


def test_scale_degree_rejects_an_invalid_kind_defensively():
    from guitar_fretboard.music_theory import ScaleSelection, scale_degree

    invalid_selection = object.__new__(ScaleSelection)
    object.__setattr__(invalid_selection, "root_pitch_class", 0)
    object.__setattr__(invalid_selection, "kind", "Major")

    with pytest.raises(ValueError, match="Unsupported scale kind"):
        scale_degree(0, invalid_selection)
