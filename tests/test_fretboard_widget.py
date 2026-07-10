from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from guitar_fretboard.fretboard_widget import FretboardWidget
from guitar_fretboard.music_theory import LabelMode, ScaleKind, ScaleSelection


def _label_texts(widget):
    return {label.text() for label in widget.findChildren(QLabel)}


def test_widget_builds_138_positions_with_headers_and_legend(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)

    assert len(widget.position_buttons) == 138
    assert widget.button_for(1, 0).position.pitch_name == "E4"
    assert widget.button_for(6, 22).position.pitch_name == "D4"

    labels = _label_texts(widget)
    assert {str(fret) for fret in range(23)} <= labels
    assert {f"String {string}" for string in range(1, 7)} <= labels
    assert {f"Octave {octave}" for octave in range(2, 7)} <= labels


def test_display_modes_and_scale_visibility(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)
    widget.show()
    c_major = ScaleSelection(0, ScaleKind.MAJOR)

    button = widget.button_for(1, 5)
    original_identity = id(button)
    widget.set_display(LabelMode.PITCH_NAME, c_major)
    assert button.text() == "A4"
    assert widget.button_for(1, 6).isVisible()
    widget.set_display(LabelMode.SOLFEGE, c_major)
    assert button.text() == "La"
    widget.set_display(LabelMode.FREQUENCY, c_major)
    assert button.text() == "440.00 Hz"
    widget.set_display(LabelMode.SCALE_DEGREE, c_major)
    assert button.text() == "6"
    assert not widget.button_for(1, 6).isVisible()
    assert id(widget.button_for(1, 5)) == original_identity


def test_fully_hidden_scale_column_retains_widget_width(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(1)
    width_before = widget.sizeHint().width()

    widget.set_display(
        LabelMode.SCALE_DEGREE,
        ScaleSelection(0, ScaleKind.MAJOR),
    )
    qtbot.wait(1)

    assert all(widget.button_for(string, 11).isHidden() for string in range(1, 7))
    assert widget.sizeHint().width() == width_before


def test_active_property_can_be_set_and_cleared(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)
    first = widget.button_for(1, 5)
    second = widget.button_for(2, 10)

    widget.set_position_active(first.position, True)
    widget.set_position_active(second.position, True)

    assert first.property("active") is True
    assert second.property("active") is True
    widget.set_position_active(first.position, False)
    assert first.property("active") is False
    assert second.property("active") is True
    widget.clear_active_styles()
    assert all(
        button.property("active") is False
        for button in widget.position_buttons.values()
    )


def test_button_tooltip_describes_its_position(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)

    tooltip = widget.button_for(1, 5).toolTip()
    assert "String 1" in tooltip
    assert "Fret 5" in tooltip
    assert "A4" in tooltip
    assert "440.00 Hz" in tooltip


def test_left_click_and_right_press_release_each_forward_one_position(qtbot):
    widget = FretboardWidget()
    qtbot.addWidget(widget)
    widget.show()
    button = widget.button_for(1, 5)
    toggled = []
    started = []
    stopped = []
    widget.toggle_requested.connect(toggled.append)
    widget.momentary_started.connect(started.append)
    widget.momentary_stopped.connect(stopped.append)

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    qtbot.mousePress(button, Qt.MouseButton.RightButton)
    qtbot.mouseRelease(button, Qt.MouseButton.RightButton)

    assert toggled == [button.position]
    assert started == [button.position]
    assert stopped == [button.position]
