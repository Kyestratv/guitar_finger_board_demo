from dataclasses import dataclass
from enum import StrEnum


PITCH_NAMES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
SOLFEGE_NAMES = (
    "Do",
    "Do♯",
    "Re",
    "Re♯",
    "Mi",
    "Fa",
    "Fa♯",
    "Sol",
    "Sol♯",
    "La",
    "La♯",
    "Ti",
)
OPEN_STRING_MIDI = (64, 59, 55, 50, 45, 40)
MAJOR_ROOT_LABELS = (
    "C",
    "D♭",
    "D",
    "E♭",
    "E",
    "F",
    "F♯",
    "G",
    "A♭",
    "A",
    "B♭",
    "B",
)
NATURAL_MINOR_ROOT_LABELS = (
    "C",
    "C♯",
    "D",
    "E♭",
    "E",
    "F",
    "F♯",
    "G",
    "G♯",
    "A",
    "B♭",
    "B",
)
MAJOR_INTERVALS = (0, 2, 4, 5, 7, 9, 11)
NATURAL_MINOR_INTERVALS = (0, 2, 3, 5, 7, 8, 10)


class LabelMode(StrEnum):
    PITCH_NAME = "Pitch Name"
    SOLFEGE = "Solfege"
    FREQUENCY = "Frequency"
    SCALE_DEGREE = "Scale Degree"


class ScaleKind(StrEnum):
    MAJOR = "Major"
    NATURAL_MINOR = "Natural Minor"


@dataclass(frozen=True, slots=True)
class ScaleSelection:
    root_pitch_class: int
    kind: ScaleKind

    def __post_init__(self) -> None:
        if not 0 <= self.root_pitch_class <= 11:
            raise ValueError("root_pitch_class must be between 0 and 11")
        if not isinstance(self.kind, ScaleKind):
            raise TypeError("kind must be a ScaleKind")

    @property
    def label(self) -> str:
        if self.kind is ScaleKind.MAJOR:
            root_label = MAJOR_ROOT_LABELS[self.root_pitch_class]
        elif self.kind is ScaleKind.NATURAL_MINOR:
            root_label = NATURAL_MINOR_ROOT_LABELS[self.root_pitch_class]
        else:
            raise ValueError(f"Unsupported scale kind: {self.kind!r}")
        return f"{root_label} {self.kind.value}"


@dataclass(frozen=True, slots=True)
class FretPosition:
    string_number: int
    fret: int
    midi_note: int
    pitch_name: str
    solfege: str
    octave: int
    frequency: float


def midi_to_frequency(midi_note: int) -> float:
    return 440.0 * 2.0 ** ((midi_note - 69) / 12.0)


def midi_to_pitch_name(midi_note: int) -> str:
    return f"{PITCH_NAMES[midi_note % 12]}{midi_note // 12 - 1}"


def midi_to_solfege(midi_note: int) -> str:
    return SOLFEGE_NAMES[midi_note % 12]


def scale_degree(pitch_class: int, selection: ScaleSelection) -> int | None:
    if selection.kind is ScaleKind.MAJOR:
        intervals = MAJOR_INTERVALS
    elif selection.kind is ScaleKind.NATURAL_MINOR:
        intervals = NATURAL_MINOR_INTERVALS
    else:
        raise ValueError(f"Unsupported scale kind: {selection.kind!r}")
    offset = (pitch_class - selection.root_pitch_class) % 12
    return intervals.index(offset) + 1 if offset in intervals else None


def build_fretboard() -> tuple[FretPosition, ...]:
    return tuple(
        FretPosition(
            string_number=string_number,
            fret=fret,
            midi_note=open_midi + fret,
            pitch_name=midi_to_pitch_name(open_midi + fret),
            solfege=midi_to_solfege(open_midi + fret),
            octave=(open_midi + fret) // 12 - 1,
            frequency=midi_to_frequency(open_midi + fret),
        )
        for string_number, open_midi in enumerate(OPEN_STRING_MIDI, start=1)
        for fret in range(23)
    )


SCALE_OPTIONS = tuple(
    ScaleSelection(root, kind)
    for kind in (ScaleKind.MAJOR, ScaleKind.NATURAL_MINOR)
    for root in range(12)
)
