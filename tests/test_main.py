from PySide6.QtWidgets import QApplication

from guitar_fretboard.audio_engine import AudioEngine
from guitar_fretboard.main_window import MainWindow


def test_configure_application_sets_identity(qapp):
    from main import configure_application

    configure_application(qapp)

    assert qapp.applicationName() == "Guitar Fretboard Visualizer"
    assert qapp.organizationName() == "Music Learning Tools"


def test_main_shows_one_window_and_returns_qt_exit_code(qapp, monkeypatch):
    import main as application_entry

    show_calls = []
    monkeypatch.setattr(
        AudioEngine,
        "start",
        lambda self: None,
    )
    monkeypatch.setattr(
        application_entry.MainWindow,
        "show",
        lambda self: show_calls.append(self),
    )
    monkeypatch.setattr(QApplication, "exec", lambda self: 23)

    exit_code = application_entry.main([])

    assert len(show_calls) == 1
    assert exit_code == 23


def test_window_applies_cohesive_styles_without_replacing_octave_rules(qtbot):
    window = MainWindow(audio_engine=AudioEngine(), start_audio=False)
    qtbot.addWidget(window)

    window_styles = window.styleSheet()
    for selector in (
        'QLabel[statusPanel="true"]',
        "QScrollArea",
        "QPushButton",
        "QRadioButton",
        "QComboBox",
        "QSlider::groove:horizontal",
    ):
        assert selector in window_styles

    fretboard_styles = window.fretboard.styleSheet()
    assert 'QPushButton[fretboardButton="true"][active="true"]' in (
        fretboard_styles
    )
    assert fretboard_styles.index('QPushButton[fretboardButton="true"]') < (
        fretboard_styles.index(
            'QPushButton[fretboardButton="true"][octave="2"]'
        )
    )
