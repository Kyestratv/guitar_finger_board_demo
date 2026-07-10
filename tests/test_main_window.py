import logging
import threading

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox

from guitar_fretboard.audio_engine import AudioDeviceError
from guitar_fretboard.main_window import MainWindow
from guitar_fretboard.music_theory import LabelMode, SCALE_OPTIONS, midi_to_frequency


class FakeAudioEngine(QObject):
    error_occurred = Signal(str)

    def __init__(self, *, start_error=None):
        super().__init__()
        self.start_error = start_error
        self.available = False
        self.start_count = 0
        self.added = []
        self.removed = []
        self.stop_all_count = 0
        self.volume_updates = []
        self.active_frequency_count = 0
        self.close_count = 0
        self._sources = {}

    def start(self):
        self.start_count += 1
        if self.start_error is not None:
            raise self.start_error
        self.available = True

    def add_source(self, midi_note, source_id):
        if not self.available:
            return
        self.added.append((midi_note, source_id))
        self._sources.setdefault(midi_note, set()).add(source_id)

    def remove_source(self, midi_note, source_id):
        self.removed.append((midi_note, source_id))
        sources = self._sources.get(midi_note)
        if sources is None:
            return
        sources.discard(source_id)
        if not sources:
            del self._sources[midi_note]

    def stop_all(self):
        self.stop_all_count += 1
        self._sources.clear()

    def set_volume_percent(self, percent):
        self.volume_updates.append(percent)

    def active_frequencies(self):
        self.active_frequency_count += 1
        return tuple(midi_to_frequency(note) for note in sorted(self._sources))

    def close(self):
        self.close_count += 1
        self.stop_all()
        self.available = False


@pytest.fixture
def fake_audio():
    return FakeAudioEngine()


def test_window_has_professional_controls(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)

    assert [button.text() for button in window.mode_group.buttons()] == [
        "Pitch Name",
        "Solfege",
        "Frequency",
        "Scale Degree",
    ]
    assert window.mode_group.exclusive()
    assert window.mode_buttons[LabelMode.PITCH_NAME].isChecked()
    assert window.scale_combo.count() == 24
    assert [window.scale_combo.itemData(index) for index in range(24)] == list(
        SCALE_OPTIONS
    )
    assert window.volume_slider.minimum() == 0
    assert window.volume_slider.maximum() == 100
    assert window.volume_slider.value() == 60
    assert window.volume_label.text() == "60%"
    assert window.active_frequencies_label.text() == "Active Frequencies: None"
    assert window.scroll_area.widget() is window.fretboard
    assert window.scroll_area.widgetResizable()
    assert fake_audio.start_count == 1
    assert fake_audio.volume_updates == [60]


def test_start_audio_flag_can_leave_supplied_engine_stopped(qtbot):
    fake_audio = FakeAudioEngine()

    window = MainWindow(audio_engine=fake_audio, start_audio=False)
    qtbot.addWidget(window)

    assert fake_audio.start_count == 0
    assert fake_audio.volume_updates == [60]


def test_window_uses_a_supplied_falsey_audio_engine(qtbot):
    class FalseyAudioEngine(FakeAudioEngine):
        def __bool__(self):
            return False

    falsey_audio = FalseyAudioEngine()

    window = MainWindow(audio_engine=falsey_audio, start_audio=False)
    qtbot.addWidget(window)

    assert window.audio_engine is falsey_audio
    assert falsey_audio.volume_updates == [60]


def test_left_toggle_and_right_momentary_are_independent(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()
    button = window.fretboard.button_for(1, 5)

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert (69, "latched:S1:F5") in fake_audio.added
    qtbot.mousePress(button, Qt.MouseButton.RightButton)
    qtbot.mouseRelease(button, Qt.MouseButton.RightButton)

    assert (69, "momentary:S1:F5") in fake_audio.added
    assert (69, "momentary:S1:F5") in fake_audio.removed
    assert (69, "latched:S1:F5") not in fake_audio.removed
    assert button.property("active") is True
    assert window.active_frequencies_label.text() == (
        "Active Frequencies: 440.00 Hz"
    )


def test_second_left_click_releases_only_latched_source(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()
    button = window.fretboard.button_for(1, 5)

    qtbot.mousePress(button, Qt.MouseButton.RightButton)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert (69, "latched:S1:F5") in fake_audio.removed
    assert (69, "momentary:S1:F5") not in fake_audio.removed
    assert button.property("active") is True

    qtbot.mouseRelease(button, Qt.MouseButton.RightButton)
    assert button.property("active") is False


def test_mode_change_stops_playback(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()
    qtbot.mouseClick(
        window.fretboard.button_for(1, 5),
        Qt.MouseButton.LeftButton,
    )
    stops_before_change = fake_audio.stop_all_count

    window.mode_buttons[LabelMode.SCALE_DEGREE].click()

    assert fake_audio.stop_all_count == stops_before_change + 1
    assert window.active_frequencies_label.text() == "Active Frequencies: None"
    assert all(
        not button.property("active")
        for button in window.fretboard.position_buttons.values()
    )


def test_scale_change_stops_playback_and_updates_scale_display(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()
    window.mode_buttons[LabelMode.SCALE_DEGREE].click()
    button = window.fretboard.button_for(1, 5)
    assert button.text() == "6"
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    stops_before_change = fake_audio.stop_all_count

    window.scale_combo.setCurrentIndex(2)

    assert fake_audio.stop_all_count == stops_before_change + 1
    assert window.scale_combo.currentData() == SCALE_OPTIONS[2]
    assert button.text() == "5"
    assert window.active_frequencies_label.text() == "Active Frequencies: None"
    assert button.property("active") is False


def test_stop_all_button_clears_sources_and_styles(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()
    first = window.fretboard.button_for(1, 5)
    second = window.fretboard.button_for(2, 10)
    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)
    qtbot.mousePress(second, Qt.MouseButton.RightButton)
    stops_before_click = fake_audio.stop_all_count

    qtbot.mouseClick(window.stop_all_button, Qt.MouseButton.LeftButton)

    assert fake_audio.stop_all_count == stops_before_click + 1
    assert window.active_frequencies_label.text() == "Active Frequencies: None"
    assert first.property("active") is False
    assert second.property("active") is False

    qtbot.mouseRelease(second, Qt.MouseButton.RightButton)
    assert (69, "momentary:S2:F10") not in fake_audio.removed


def test_active_frequency_panel_formats_sorted_unique_frequencies(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()

    for string_number, fret in ((1, 0), (6, 0), (2, 5)):
        qtbot.mouseClick(
            window.fretboard.button_for(string_number, fret),
            Qt.MouseButton.LeftButton,
        )

    assert window.active_frequencies_label.text() == (
        "Active Frequencies: 82.41 Hz, 329.63 Hz"
    )
    assert fake_audio.active_frequency_count >= 3


def test_duplicate_pitch_stays_active_until_final_position_is_released(
    qtbot,
    fake_audio,
):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()
    first = window.fretboard.button_for(1, 5)
    second = window.fretboard.button_for(2, 10)

    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(second, Qt.MouseButton.LeftButton)
    assert fake_audio._sources[69] == {"latched:S1:F5", "latched:S2:F10"}

    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)

    assert fake_audio._sources[69] == {"latched:S2:F10"}
    assert first.property("active") is False
    assert second.property("active") is True
    assert window.active_frequencies_label.text() == "Active Frequencies: 440.00 Hz"

    qtbot.mouseClick(second, Qt.MouseButton.LeftButton)

    assert 69 not in fake_audio._sources
    assert second.property("active") is False
    assert window.active_frequencies_label.text() == "Active Frequencies: None"


def test_volume_slider_updates_audio_and_percentage_label(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)

    window.volume_slider.setValue(37)

    assert fake_audio.volume_updates[-1] == 37
    assert window.volume_label.text() == "37%"


def test_audio_start_failure_shows_critical_and_keeps_window_usable(
    qtbot,
    monkeypatch,
):
    fake_audio = FakeAudioEngine(start_error=AudioDeviceError("device busy"))
    critical_calls = []
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        lambda *args: critical_calls.append(args),
    )

    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)

    assert fake_audio.start_count == 1
    assert len(critical_calls) == 1
    assert critical_calls[0][1:] == (
        "Audio Output Unavailable",
        "The default audio output device could not be opened. "
        "The fretboard remains available for visual learning.\n\n"
        "Details: device busy",
    )
    assert window.fretboard.button_for(1, 5).isEnabled()


def test_queued_runtime_audio_error_stops_playback_and_shows_one_warning(
    qtbot,
    fake_audio,
    monkeypatch,
):
    warning_calls = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warning_calls.append(args),
    )
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()
    button = window.fretboard.button_for(1, 5)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    stops_before_error = fake_audio.stop_all_count

    worker = threading.Thread(
        target=fake_audio.error_occurred.emit,
        args=("Audio rendering failed: test failure",),
    )
    worker.start()
    worker.join(timeout=1)

    assert not worker.is_alive()
    qtbot.waitUntil(lambda: len(warning_calls) == 1)
    assert fake_audio.stop_all_count == stops_before_error + 1
    assert warning_calls[0][1:] == (
        "Audio Playback Error",
        "Audio rendering failed: test failure",
    )
    assert window.active_frequencies_label.text() == "Active Frequencies: None"
    assert button.property("active") is False


def test_close_calls_audio_engine_close(qtbot, fake_audio):
    window = MainWindow(audio_engine=fake_audio)
    qtbot.addWidget(window)
    window.show()

    assert window.close()
    qtbot.waitUntil(lambda: fake_audio.close_count == 1)


def test_close_accepts_event_and_logs_nonmodal_warning_when_audio_close_fails(
    qtbot,
    monkeypatch,
    caplog,
):
    class FailingCloseAudioEngine(FakeAudioEngine):
        def close(self):
            super().close()
            raise OSError("device vanished during close")

    warning_calls = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warning_calls.append(args),
    )
    audio_engine = FailingCloseAudioEngine()
    window = MainWindow(audio_engine=audio_engine, start_audio=False)
    qtbot.addWidget(window)
    event = QCloseEvent()

    with caplog.at_level(logging.WARNING):
        window.closeEvent(event)

    assert event.isAccepted()
    assert audio_engine.close_count == 1
    assert "Audio shutdown failed: device vanished during close" in caplog.text
    assert warning_calls == []
