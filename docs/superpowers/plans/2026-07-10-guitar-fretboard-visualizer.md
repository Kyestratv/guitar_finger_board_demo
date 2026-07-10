# Guitar Fretboard Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a professional English-language Python desktop application that displays every note on a standard 6-string, 22-fret guitar and supports four learning modes plus polyphonic sine-wave playback.

**Architecture:** Keep musical calculations in immutable pure-Python models, isolate real-time sample generation from the sounddevice adapter, and place PySide6 interaction logic in focused fretboard and main-window widgets. The GUI communicates with audio through source-aware commands so left-button latches, right-button momentary notes, and duplicate pitches cannot stop one another accidentally.

**Tech Stack:** Python 3.11+, PySide6, NumPy, sounddevice, pytest, pytest-qt

## Global Constraints

- Use standard tuning from string 1 through string 6: E4, B3, G3, D3, A2, E2.
- Display fret 0 through fret 22 and place fret 0 before fret 1.
- Use twelve-tone equal temperament with A4 exactly 440 Hz.
- Solfege is fixed-do and independent of the selected key.
- Support all 12 major keys and all 12 natural minor keys only.
- Visible interface text must be professional English.
- Left click toggles a latched note; right press/release provides momentary playback.
- Audio uses one 48 kHz float32 stream and supports multiple simultaneous unique pitches.
- Changing display mode or scale stops playback before updating the fretboard.
- Tests must not require a physical display or audio device.

## File Structure

- `requirements.txt`: runtime dependencies.
- `requirements-dev.txt`: test dependencies layered on runtime dependencies.
- `pytest.ini`: deterministic pytest discovery.
- `guitar_fretboard/__init__.py`: package metadata.
- `guitar_fretboard/music_theory.py`: immutable fret-position data, labels, frequencies, scales, and degrees.
- `guitar_fretboard/audio_engine.py`: source registry, sine mixer, sounddevice adapter, and audio error type.
- `guitar_fretboard/fretboard_widget.py`: mouse-aware note buttons and fretboard content.
- `guitar_fretboard/main_window.py`: controls, playback coordination, status display, and shutdown.
- `main.py`: application entry point.
- `tests/conftest.py`: force Qt offscreen before PySide6 imports.
- `tests/test_music_theory.py`: music-theory coverage.
- `tests/test_audio_engine.py`: source-state, synthesis, and adapter coverage.
- `tests/test_fretboard_widget.py`: structure, labels, visibility, styling, and mouse signals.
- `tests/test_main_window.py`: control integration, playback, errors, and shutdown.
- `tests/test_main.py`: entry-point smoke coverage.
- `README.md`: setup, operation, testing, and troubleshooting.

---

### Task 1: Project Foundation and Music-Theory Core

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/conftest.py`
- Create: `tests/test_music_theory.py`
- Create: `guitar_fretboard/__init__.py`
- Create: `guitar_fretboard/music_theory.py`

**Interfaces:**
- Consumes: no application interfaces.
- Produces: `LabelMode`, `ScaleKind`, `ScaleSelection`, `FretPosition`, `SCALE_OPTIONS`, `midi_to_frequency(int) -> float`, `midi_to_pitch_name(int) -> str`, `midi_to_solfege(int) -> str`, `scale_degree(int, ScaleSelection) -> int | None`, and `build_fretboard() -> tuple[FretPosition, ...]`.

- [ ] **Step 1: Add dependency/test configuration and failing theory tests**

Create:

~~~text
# requirements.txt
PySide6>=6.8,<7
numpy>=2.1,<3
sounddevice>=0.5,<1
~~~

~~~text
# requirements-dev.txt
-r requirements.txt
pytest>=8.3,<9
pytest-qt>=4.4,<5
~~~

~~~ini
# pytest.ini
[pytest]
testpaths = tests
addopts = -ra
~~~

In `tests/conftest.py`, call `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` before Qt imports. Tests import the desired API inside test functions and convert an initial `ImportError` to `pytest.fail` so RED is a test failure, not a collection error. Cover:

~~~python
def test_standard_tuning_builds_all_138_positions():
    positions = build_fretboard()
    assert len(positions) == 138
    by_location = {(p.string_number, p.fret): p for p in positions}
    assert by_location[1, 0].midi_note == 64
    assert by_location[2, 0].midi_note == 59
    assert by_location[6, 0].midi_note == 40
    assert by_location[1, 12].pitch_name == "E5"
    assert by_location[6, 22].pitch_name == "D4"

def test_equal_temperament_and_fixed_do_labels():
    assert midi_to_frequency(69) == pytest.approx(440.0)
    assert midi_to_frequency(60) == pytest.approx(261.625565, rel=1e-6)
    assert midi_to_pitch_name(70) == "A♯4"
    assert midi_to_solfege(60) == "Do"
    assert midi_to_solfege(61) == "Do♯"

def test_c_major_and_a_natural_minor_degrees():
    c_major = ScaleSelection(0, ScaleKind.MAJOR)
    a_minor = ScaleSelection(9, ScaleKind.NATURAL_MINOR)
    assert [scale_degree(pc, c_major) for pc in (0, 2, 4, 5, 7, 9, 11)] == list(range(1, 8))
    assert [scale_degree(pc, a_minor) for pc in (9, 11, 0, 2, 4, 5, 7)] == list(range(1, 8))
    assert scale_degree(1, c_major) is None

def test_scale_selector_contains_12_major_and_12_natural_minor_choices():
    assert len(SCALE_OPTIONS) == 24
    assert sum(s.kind is ScaleKind.MAJOR for s in SCALE_OPTIONS) == 12
    assert sum(s.kind is ScaleKind.NATURAL_MINOR for s in SCALE_OPTIONS) == 12
~~~

- [ ] **Step 2: Install dependencies and verify RED**

Run:

~~~powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_music_theory.py -v
~~~

Expected: installation succeeds; pytest reports focused failures identifying the missing theory API.

- [ ] **Step 3: Implement the immutable music model**

Create `guitar_fretboard/__init__.py` with `__version__ = "1.0.0"`. Implement:

~~~python
from dataclasses import dataclass
from enum import StrEnum

PITCH_NAMES = ("C", "C♯", "D", "D♯", "E", "F", "F♯", "G", "G♯", "A", "A♯", "B")
SOLFEGE_NAMES = ("Do", "Do♯", "Re", "Re♯", "Mi", "Fa", "Fa♯", "Sol", "Sol♯", "La", "La♯", "Ti")
OPEN_STRING_MIDI = (64, 59, 55, 50, 45, 40)
ROOT_LABELS = ("C", "D♭", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B")
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

    @property
    def label(self) -> str:
        return f"{ROOT_LABELS[self.root_pitch_class]} {self.kind.value}"

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
    intervals = MAJOR_INTERVALS if selection.kind is ScaleKind.MAJOR else NATURAL_MINOR_INTERVALS
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
~~~

- [ ] **Step 4: Verify GREEN and regression state**

Run:

~~~powershell
python -m pytest tests/test_music_theory.py -v
python -m pytest -q
~~~

Expected: all theory tests pass and the full suite has zero failures.

- [ ] **Step 5: Commit Task 1**

~~~powershell
git add requirements.txt requirements-dev.txt pytest.ini tests/conftest.py tests/test_music_theory.py guitar_fretboard/__init__.py guitar_fretboard/music_theory.py
git commit -m "feat: add guitar music theory model"
~~~

---

### Task 2: Source-Aware Polyphonic Audio Engine

**Files:**
- Create: `tests/test_audio_engine.py`
- Create: `guitar_fretboard/audio_engine.py`

**Interfaces:**
- Consumes: `midi_to_frequency(int) -> float`.
- Produces: `AudioDeviceError`, `SineMixer(sample_rate=48000)`, and `AudioEngine(mixer=None, stream_factory=None)` with the Qt signal `error_occurred(str)` plus `start`, `add_source`, `remove_source`, `stop_all`, `set_volume_percent`, `active_frequencies`, and `close`.

- [ ] **Step 1: Write failing source and synthesis tests**

Cover:

~~~python
def test_pitch_remains_active_until_final_source_is_removed():
    mixer = SineMixer(sample_rate=48_000)
    mixer.add_source(69, "latched:S1:F5")
    mixer.add_source(69, "momentary:S2:F10")
    mixer.remove_source(69, "momentary:S2:F10")
    assert mixer.active_midi_notes() == (69,)
    mixer.remove_source(69, "latched:S1:F5")
    assert mixer.active_midi_notes() == ()

def test_render_is_float32_bounded_and_phase_continuous():
    mixer = SineMixer(sample_rate=48_000)
    mixer.set_volume_percent(100)
    mixer.add_source(69, "test")
    first = mixer.render(480)
    second = mixer.render(480)
    assert first.dtype == np.float32
    assert np.max(np.abs(first)) <= 1.0
    assert not np.array_equal(first, second)

def test_silence_volume_and_stop_all():
    mixer = SineMixer()
    assert np.count_nonzero(mixer.render(64)) == 0
    mixer.add_source(69, "a")
    mixer.set_volume_percent(0)
    assert np.count_nonzero(mixer.render(64)) == 0
    mixer.stop_all()
    assert mixer.active_frequencies() == ()
~~~

Use a complete `FakeStream` with start/stop/close flags. Verify the adapter fills `outdata[:, 0]`, closes the stream, translates factory/start errors into `AudioDeviceError`, and emits one `error_occurred` signal while replacing a failed callback block with silence.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_audio_engine.py -v`

Expected: focused failures because the audio API is absent.

- [ ] **Step 3: Implement the mixer**

`SineMixer` owns an `RLock`, `dict[int, set[str]]` sources, `dict[int, float]` phases, sample rate, and 0.0–1.0 master gain. Mutations validate MIDI range 0–127 and non-empty source IDs. `render(frames)` snapshots state under lock, uses `np.arange(frames, dtype=np.float64)`, advances each phase by `2*pi*frequency/sample_rate`, divides the sum by unique voice count, applies volume, saves wrapped phases, and returns float32. Silence returns `np.zeros(frames, dtype=np.float32)`.

- [ ] **Step 4: Implement the sounddevice adapter**

Use:

~~~python
class AudioDeviceError(RuntimeError):
    pass

class AudioEngine(QObject):
    error_occurred = Signal(str)

    def __init__(self, mixer=None, stream_factory=None):
        super().__init__()
        self.mixer = mixer or SineMixer()
        self._stream_factory = stream_factory or sounddevice.OutputStream
        self._stream = None
        self.available = False
        self._callback_error_reported = False

    def _callback(self, outdata, frames, time_info, status):
        del time_info, status
        try:
            outdata[:, 0] = self.mixer.render(frames)
        except Exception as exc:
            outdata.fill(0)
            if not self._callback_error_reported:
                self._callback_error_reported = True
                self.error_occurred.emit(f"Audio rendering failed: {exc}")

    def start(self):
        try:
            self._stream = self._stream_factory(
                samplerate=self.mixer.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            self.available = True
        except Exception as exc:
            self.available = False
            self._stream = None
            raise AudioDeviceError(
                f"Unable to open the default audio output device: {exc}"
            ) from exc

    def add_source(self, midi_note, source_id):
        if self.available:
            self.mixer.add_source(midi_note, source_id)

    def remove_source(self, midi_note, source_id):
        self.mixer.remove_source(midi_note, source_id)

    def stop_all(self):
        self.mixer.stop_all()

    def set_volume_percent(self, percent):
        self.mixer.set_volume_percent(percent)

    def active_frequencies(self):
        return self.mixer.active_frequencies()

    def close(self):
        self.stop_all()
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
        self._stream = None
        self.available = False
~~~

- [ ] **Step 5: Verify GREEN and commit**

~~~powershell
python -m pytest tests/test_audio_engine.py -v
python -m pytest -q
git add tests/test_audio_engine.py guitar_fretboard/audio_engine.py
git commit -m "feat: add polyphonic sine audio engine"
~~~

Expected: all tests pass before the commit.

---

### Task 3: Interactive Fretboard Widget

**Files:**
- Create: `tests/test_fretboard_widget.py`
- Create: `guitar_fretboard/fretboard_widget.py`

**Interfaces:**
- Consumes: theory types and functions from Task 1.
- Produces: `FretButton` signals `toggle_requested`, `momentary_started`, `momentary_stopped`; `FretboardWidget` forwarding those signals and methods `button_for`, `set_display`, `set_position_active`, `clear_active_styles`.

- [ ] **Step 1: Write failing offscreen widget tests**

Cover:

~~~python
def test_widget_builds_138_positions(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)
    assert len(widget.position_buttons) == 138
    assert widget.button_for(1, 0).position.pitch_name == "E4"
    assert widget.button_for(6, 22).position.pitch_name == "D4"

def test_display_modes_and_scale_visibility(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)
    widget.show()
    c_major = ScaleSelection(0, ScaleKind.MAJOR)
    widget.set_display(LabelMode.PITCH_NAME, c_major)
    assert widget.button_for(1, 5).text() == "A4"
    widget.set_display(LabelMode.SOLFEGE, c_major)
    assert widget.button_for(1, 5).text() == "La"
    widget.set_display(LabelMode.FREQUENCY, c_major)
    assert widget.button_for(1, 5).text() == "440.00 Hz"
    widget.set_display(LabelMode.SCALE_DEGREE, c_major)
    assert widget.button_for(1, 5).text() == "6"
    assert not widget.button_for(1, 6).isVisible()
~~~

Also verify fret/string headers, legend labels `Octave 2` through `Octave 6`, the `active` dynamic property, and one emitted position per left click/right press/right release.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_fretboard_widget.py -v`

Expected: focused failures because the widget API is absent.

- [ ] **Step 3: Implement the mouse-aware note button**

`FretButton` subclasses `QPushButton`, stores one `FretPosition`, connects normal `clicked` to `toggle_requested`, and overrides only right-button press/release. Right press grabs the mouse and emits `momentary_started`. Right release releases the mouse and emits `momentary_stopped`. Other events delegate to `QPushButton`.

- [ ] **Step 4: Implement the fretboard and labels**

Use:

~~~python
OCTAVE_COLORS = {
    2: "#ef4444",
    3: "#f59e0b",
    4: "#84cc16",
    5: "#06b6d4",
    6: "#3b82f6",
}

def position_label(position, mode, selection):
    if mode is LabelMode.PITCH_NAME:
        return position.pitch_name
    if mode is LabelMode.SOLFEGE:
        return position.solfege
    if mode is LabelMode.FREQUENCY:
        return f"{position.frequency:.2f} Hz"
    degree = scale_degree(position.midi_note % 12, selection)
    return "" if degree is None else str(degree)
~~~

Build a `QGridLayout` with fret headers in row 0, string labels at column 0, fret 0 at column 1, and 138 reusable buttons. Store them in `dict[(string, fret), button]`. Add a visually stronger nut after fret 0. `set_display` changes text and visibility in place. `set_position_active` sets the dynamic `active` property and repolishes. Buttons have readable minimum dimensions and tooltips containing string, fret, pitch, and frequency.

- [ ] **Step 5: Verify GREEN and commit**

~~~powershell
python -m pytest tests/test_fretboard_widget.py -v
python -m pytest -q
git add tests/test_fretboard_widget.py guitar_fretboard/fretboard_widget.py
git commit -m "feat: add interactive guitar fretboard widget"
~~~

Expected: all tests pass under Qt offscreen mode.

---

### Task 4: Main Window and Playback Coordination

**Files:**
- Create: `tests/test_main_window.py`
- Create: `guitar_fretboard/main_window.py`

**Interfaces:**
- Consumes: `AudioEngine`, `AudioDeviceError`, `FretboardWidget`, and theory types/options.
- Produces: `MainWindow(audio_engine: AudioEngine | None = None, start_audio: bool = True)` with stable control attributes.

- [ ] **Step 1: Write failing integration tests**

Create a `FakeAudioEngine` that records start, add/remove source, stop-all, volume, frequency, and close behavior. Cover:

~~~python
def test_window_has_professional_controls(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    assert [b.text() for b in window.mode_group.buttons()] == [
        "Pitch Name", "Solfege", "Frequency", "Scale Degree"
    ]
    assert window.mode_group.exclusive()
    assert window.scale_combo.count() == 24
    assert window.volume_slider.minimum() == 0
    assert window.volume_slider.maximum() == 100
    assert window.active_frequencies_label.text() == "Active Frequencies: None"

def test_left_toggle_and_right_momentary_are_independent(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    button = window.fretboard.button_for(1, 5)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert (69, "latched:S1:F5") in fake_audio.added
    qtbot.mousePress(button, Qt.MouseButton.RightButton)
    qtbot.mouseRelease(button, Qt.MouseButton.RightButton)
    assert (69, "momentary:S1:F5") in fake_audio.removed
    assert (69, "latched:S1:F5") not in fake_audio.removed

def test_mode_change_stops_playback(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    qtbot.mouseClick(window.fretboard.button_for(1, 5), Qt.MouseButton.LeftButton)
    window.mode_buttons[LabelMode.SCALE_DEGREE].click()
    assert fake_audio.stop_all_count >= 1
    assert window.active_frequencies_label.text() == "Active Frequencies: None"
~~~

Also test scale changes, Stop All, sorted unique frequency formatting, volume updates, patched `QMessageBox.critical` on `AudioDeviceError`, a queued runtime-audio-error signal showing one warning, and close calling `audio_engine.close()`.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_main_window.py -v`

Expected: focused failures because `MainWindow` is absent.

- [ ] **Step 3: Implement layout and state handlers**

Create a central vertical layout with:

- exclusive `QButtonGroup` radio buttons from `LabelMode`;
- `QComboBox` containing `(selection.label, selection)` for all `SCALE_OPTIONS`;
- Volume slider 0–100 initialized to 60 and a percentage label;
- `Stop All` button;
- `Active Frequencies: None` status panel;
- `FretboardWidget` inside a resizable horizontal `QScrollArea`.

Use:

~~~python
def _source_id(kind: str, position: FretPosition) -> str:
    return f"{kind}:S{position.string_number}:F{position.fret}"
~~~

Maintain `_latched` and `_momentary` sets of `(string, fret)`. Each handler changes only its own source kind, updates the affected active style, and refreshes unique sorted frequencies. Mode and scale handlers call `_stop_all()` before `fretboard.set_display(...)`. `_stop_all` clears both sets, calls audio stop, clears styles, and refreshes status. Volume calls audio and displays `f"{value}%"`.

Catch audio start failure with:

~~~python
QMessageBox.critical(
    self,
    "Audio Output Unavailable",
    "The default audio output device could not be opened. "
    "The fretboard remains available for visual learning.\n\n"
    f"Details: {error}",
)
~~~

If the supplied audio engine exposes `error_occurred`, connect it to a main-thread slot that stops all playback and shows `QMessageBox.warning` with title `Audio Playback Error` and the emitted detail. Qt's queued cross-thread signal delivery keeps dialogs out of the real-time callback thread.

`closeEvent` closes audio in `try/finally` and accepts the event.

- [ ] **Step 4: Verify GREEN and commit**

~~~powershell
python -m pytest tests/test_main_window.py -v
python -m pytest -q
git add tests/test_main_window.py guitar_fretboard/main_window.py
git commit -m "feat: integrate fretboard controls and playback"
~~~

Expected: the accumulated suite passes.

---

### Task 5: Entry Point, Styling, Documentation, and Final Verification

**Files:**
- Create: `tests/test_main.py`
- Create: `main.py`
- Create: `README.md`
- Modify: `guitar_fretboard/main_window.py`

**Interfaces:**
- Consumes: `MainWindow`.
- Produces: `configure_application(QApplication) -> None` and `main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: Write failing entry-point tests**

Cover:

~~~python
def test_configure_application_sets_identity(qapp):
    from main import configure_application
    configure_application(qapp)
    assert qapp.applicationName() == "Guitar Fretboard Visualizer"
    assert qapp.organizationName() == "Music Learning Tools"
~~~

Monkeypatch `MainWindow.show` and `QApplication.exec`, call `main([])`, verify one show call, and assert the patched exit code.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_main.py -v`

Expected: focused failures because `main.py` lacks the API.

- [ ] **Step 3: Implement entry point and cohesive styling**

Implement:

~~~python
import sys
from PySide6.QtWidgets import QApplication
from guitar_fretboard.main_window import MainWindow

def configure_application(app: QApplication) -> None:
    app.setApplicationName("Guitar Fretboard Visualizer")
    app.setOrganizationName("Music Learning Tools")
    app.setStyle("Fusion")

def main(argv: list[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    configure_application(app)
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
~~~

Add a cohesive dark-neutral stylesheet for controls, status panel, scroll area, buttons, and `[active="true"]`. Preserve individual octave backgrounds after shared rules.

- [ ] **Step 4: Write user documentation**

Create `README.md` with sections `Overview`, `Requirements`, `Installation`, `Running the Application`, `Controls`, `Music Rules`, `Testing`, and `Audio Troubleshooting`. Include:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python main.py
python -m pytest -q
~~~

Document every control, standard tuning, fixed-do, A4=440 Hz, major/natural-minor scope, and visual-only fallback after audio-device failure.

- [ ] **Step 5: Run fresh verification**

~~~powershell
python -m pytest -q
python -m compileall -q guitar_fretboard main.py tests
$env:QT_QPA_PLATFORM='offscreen'
python -c "from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication; from guitar_fretboard.audio_engine import AudioEngine; from guitar_fretboard.main_window import MainWindow; app=QApplication([]); window=MainWindow(audio_engine=AudioEngine(), start_audio=False); window.show(); QTimer.singleShot(100, app.quit); raise SystemExit(app.exec())"
git diff --check
~~~

Expected: zero pytest failures; compileall exit 0; offscreen smoke exit 0; no `git diff --check` output.

- [ ] **Step 6: Audit requirements and record evidence**

Read `task.md` and the approved design. Map all 12 original requirements plus major/natural-minor selection to code/tests. Record commands, counts, and any real-audio limitation in `progress.md`.

- [ ] **Step 7: Commit the completed application**

~~~powershell
git add main.py README.md tests/test_main.py guitar_fretboard/main_window.py task_plan.md findings.md progress.md
git commit -m "feat: complete guitar fretboard visualizer"
~~~

