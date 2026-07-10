from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from guitar_fretboard.music_theory import (
    FretPosition,
    LabelMode,
    ScaleKind,
    ScaleSelection,
    build_fretboard,
    scale_degree,
)


OCTAVE_COLORS = {
    2: "#ef4444",
    3: "#f59e0b",
    4: "#84cc16",
    5: "#06b6d4",
    6: "#3b82f6",
}


def position_label(
    position: FretPosition,
    mode: LabelMode,
    selection: ScaleSelection,
) -> str:
    if mode is LabelMode.PITCH_NAME:
        return position.pitch_name
    if mode is LabelMode.SOLFEGE:
        return position.solfege
    if mode is LabelMode.FREQUENCY:
        return f"{position.frequency:.2f} Hz"
    degree = scale_degree(position.midi_note % 12, selection)
    return "" if degree is None else str(degree)


class FretButton(QPushButton):
    toggle_requested = Signal(object)
    momentary_started = Signal(object)
    momentary_stopped = Signal(object)

    def __init__(self, position: FretPosition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.position = position
        self.clicked.connect(self._request_toggle)

    def _request_toggle(self) -> None:
        self.toggle_requested.emit(self.position)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.grabMouse()
            self.momentary_started.emit(self.position)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.releaseMouse()
            self.momentary_stopped.emit(self.position)
            event.accept()
            return
        super().mouseReleaseEvent(event)


class FretboardWidget(QWidget):
    toggle_requested = Signal(object)
    momentary_started = Signal(object)
    momentary_stopped = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.position_buttons: dict[tuple[int, int], FretButton] = {}
        self._build_layout()
        self._apply_styles()
        self.set_display(
            LabelMode.PITCH_NAME,
            ScaleSelection(0, ScaleKind.MAJOR),
        )

    def _build_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("Octave Colors"))
        for octave, color in OCTAVE_COLORS.items():
            legend = QLabel(f"Octave {octave}")
            legend.setAlignment(Qt.AlignmentFlag.AlignCenter)
            legend.setMinimumWidth(76)
            legend.setStyleSheet(
                f"background-color: {color}; color: #111827; "
                "border-radius: 4px; padding: 4px; font-weight: 600;"
            )
            legend_layout.addWidget(legend)
        legend_layout.addStretch()
        layout.addLayout(legend_layout)

        self.grid_layout = QGridLayout()
        self.grid_layout.setHorizontalSpacing(4)
        self.grid_layout.setVerticalSpacing(4)
        self.grid_layout.addWidget(QLabel("String / Fret"), 0, 0)
        for fret in range(23):
            fret_label = QLabel(str(fret))
            fret_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid_layout.addWidget(fret_label, 0, fret + 1)

        for string_number in range(1, 7):
            string_label = QLabel(f"String {string_number}")
            string_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.grid_layout.addWidget(string_label, string_number, 0)

        for position in build_fretboard():
            button = FretButton(position)
            button.setMinimumSize(76, 40)
            button.setToolTip(
                f"String {position.string_number}, Fret {position.fret}: "
                f"{position.pitch_name} ({position.frequency:.2f} Hz)"
            )
            button.setProperty("fretboardButton", True)
            button.setProperty("octave", position.octave)
            button.setProperty("nut", position.fret == 0)
            button.setProperty("active", False)
            button.toggle_requested.connect(self.toggle_requested.emit)
            button.momentary_started.connect(self.momentary_started.emit)
            button.momentary_stopped.connect(self.momentary_stopped.emit)
            self.position_buttons[position.string_number, position.fret] = button
            self.grid_layout.addWidget(
                button,
                position.string_number,
                position.fret + 1,
            )

        layout.addLayout(self.grid_layout)

    def _apply_styles(self) -> None:
        octave_rules = "\n".join(
            f'QPushButton[fretboardButton="true"][octave="{octave}"] '
            f'{{ background-color: {color}; }}'
            for octave, color in OCTAVE_COLORS.items()
        )
        self.setStyleSheet(
            """
            QPushButton[fretboardButton="true"] {
                color: #111827;
                border: 1px solid #475569;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton[fretboardButton="true"][active="true"] {
                border: 3px solid #111827;
                font-weight: 700;
                padding-top: 6px;
                padding-bottom: 2px;
            }
            QPushButton[fretboardButton="true"][nut="true"] {
                border-right: 5px solid #111827;
            }
            """
            + octave_rules
        )

    def button_for(self, string_number: int, fret: int) -> FretButton:
        return self.position_buttons[string_number, fret]

    def set_display(
        self,
        mode: LabelMode,
        selection: ScaleSelection,
    ) -> None:
        for button in self.position_buttons.values():
            label = position_label(button.position, mode, selection)
            button.setText(label)
            button.setVisible(bool(label))

    def set_position_active(self, position: FretPosition, active: bool) -> None:
        button = self.button_for(position.string_number, position.fret)
        button.setProperty("active", active)
        self._repolish(button)

    def clear_active_styles(self) -> None:
        for button in self.position_buttons.values():
            button.setProperty("active", False)
            self._repolish(button)

    @staticmethod
    def _repolish(button: FretButton) -> None:
        style = button.style()
        style.unpolish(button)
        style.polish(button)
        button.update()
