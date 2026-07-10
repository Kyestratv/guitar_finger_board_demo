import logging

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from guitar_fretboard.audio_engine import AudioDeviceError, AudioEngine
from guitar_fretboard.fretboard_widget import FretboardWidget
from guitar_fretboard.music_theory import (
    FretPosition,
    LabelMode,
    SCALE_OPTIONS,
    ScaleSelection,
)


LOGGER = logging.getLogger(__name__)


def _source_id(kind: str, position: FretPosition) -> str:
    return f"{kind}:S{position.string_number}:F{position.fret}"


class MainWindow(QMainWindow):
    def __init__(
        self,
        audio_engine: AudioEngine | None = None,
        start_audio: bool = True,
    ) -> None:
        super().__init__()
        self.audio_engine = (
            audio_engine if audio_engine is not None else AudioEngine()
        )
        self._mode = LabelMode.PITCH_NAME
        self._selection = SCALE_OPTIONS[0]
        self._latched: set[tuple[int, int]] = set()
        self._momentary: set[tuple[int, int]] = set()

        self.setWindowTitle("Guitar Fretboard Visualizer")
        self._build_ui()
        self._apply_styles()
        self._connect_audio_error_signal()
        self._set_volume(self.volume_slider.value())

        if start_audio:
            try:
                self.audio_engine.start()
            except AudioDeviceError as error:
                QMessageBox.critical(
                    self,
                    "Audio Output Unavailable",
                    "The default audio output device could not be opened. "
                    "The fretboard remains available for visual learning.\n\n"
                    f"Details: {error}",
                )

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        controls_layout.addWidget(QLabel("Label Mode"))

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons: dict[LabelMode, QRadioButton] = {}
        for mode in LabelMode:
            button = QRadioButton(mode.value)
            button.clicked.connect(
                lambda checked=False, selected_mode=mode: self._change_mode(
                    selected_mode
                )
            )
            self.mode_group.addButton(button)
            self.mode_buttons[mode] = button
            controls_layout.addWidget(button)
        self.mode_buttons[self._mode].setChecked(True)

        controls_layout.addSpacing(12)
        controls_layout.addWidget(QLabel("Key / Scale"))
        self.scale_combo = QComboBox()
        for selection in SCALE_OPTIONS:
            self.scale_combo.addItem(selection.label, selection)
        self.scale_combo.currentIndexChanged.connect(self._change_scale)
        controls_layout.addWidget(self.scale_combo)

        controls_layout.addSpacing(12)
        controls_layout.addWidget(QLabel("Volume"))
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(60)
        self.volume_slider.setMinimumWidth(140)
        self.volume_slider.valueChanged.connect(self._set_volume)
        controls_layout.addWidget(self.volume_slider)
        self.volume_label = QLabel("60%")
        self.volume_label.setMinimumWidth(40)
        controls_layout.addWidget(self.volume_label)

        self.stop_all_button = QPushButton("Stop All")
        self.stop_all_button.clicked.connect(self._stop_all)
        controls_layout.addWidget(self.stop_all_button)
        controls_layout.addStretch()
        root_layout.addLayout(controls_layout)

        self.active_frequencies_label = QLabel("Active Frequencies: None")
        self.active_frequencies_label.setProperty("statusPanel", True)
        root_layout.addWidget(self.active_frequencies_label)

        self.fretboard = FretboardWidget()
        self.fretboard.toggle_requested.connect(self._toggle_latched)
        self.fretboard.momentary_started.connect(self._start_momentary)
        self.fretboard.momentary_stopped.connect(self._stop_momentary)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setWidget(self.fretboard)
        root_layout.addWidget(self.scroll_area, 1)

        self.setCentralWidget(central_widget)
        self.resize(1280, 520)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #111827;
            }
            QWidget {
                color: #e5e7eb;
            }
            QLabel[statusPanel="true"] {
                background-color: #1f2937;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px 10px;
                font-weight: 600;
            }
            QScrollArea {
                background-color: #0f172a;
                border: 1px solid #334155;
                border-radius: 6px;
            }
            QScrollBar:horizontal {
                background-color: #1f2937;
                height: 14px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal {
                background-color: #64748b;
                border-radius: 5px;
                min-width: 32px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
            }
            QPushButton,
            QComboBox {
                background-color: #334155;
                border: 1px solid #64748b;
                border-radius: 5px;
                padding: 6px 10px;
            }
            QPushButton:hover,
            QComboBox:hover {
                background-color: #475569;
                border-color: #94a3b8;
            }
            QPushButton:pressed {
                background-color: #1e293b;
            }
            QComboBox QAbstractItemView {
                background-color: #1f2937;
                color: #e5e7eb;
                selection-background-color: #475569;
            }
            QRadioButton {
                spacing: 6px;
            }
            QRadioButton::indicator {
                width: 14px;
                height: 14px;
                border: 2px solid #94a3b8;
                border-radius: 8px;
                background-color: #1f2937;
            }
            QRadioButton::indicator:checked {
                background-color: #38bdf8;
                border-color: #bae6fd;
            }
            QSlider::groove:horizontal {
                background-color: #334155;
                border-radius: 3px;
                height: 6px;
            }
            QSlider::handle:horizontal {
                background-color: #38bdf8;
                border: 1px solid #bae6fd;
                border-radius: 8px;
                height: 16px;
                width: 16px;
                margin: -5px 0;
            }
            QPushButton[fretboardButton="true"][active="true"] {
                border-color: #f8fafc;
            }
            """
        )

    def _connect_audio_error_signal(self) -> None:
        error_signal = getattr(self.audio_engine, "error_occurred", None)
        if error_signal is not None:
            error_signal.connect(
                self._handle_audio_error,
                Qt.ConnectionType.QueuedConnection,
            )

    @staticmethod
    def _position_key(position: FretPosition) -> tuple[int, int]:
        return position.string_number, position.fret

    def _position_is_active(self, position: FretPosition) -> bool:
        key = self._position_key(position)
        return key in self._latched or key in self._momentary

    @Slot(object)
    def _toggle_latched(self, position: FretPosition) -> None:
        key = self._position_key(position)
        source_id = _source_id("latched", position)
        if key in self._latched:
            self._latched.remove(key)
            self.audio_engine.remove_source(position.midi_note, source_id)
        else:
            self._latched.add(key)
            self.audio_engine.add_source(position.midi_note, source_id)
        self.fretboard.set_position_active(
            position,
            self._position_is_active(position),
        )
        self._refresh_active_frequencies()

    @Slot(object)
    def _start_momentary(self, position: FretPosition) -> None:
        key = self._position_key(position)
        if key in self._momentary:
            return
        self._momentary.add(key)
        self.audio_engine.add_source(
            position.midi_note,
            _source_id("momentary", position),
        )
        self.fretboard.set_position_active(position, True)
        self._refresh_active_frequencies()

    @Slot(object)
    def _stop_momentary(self, position: FretPosition) -> None:
        key = self._position_key(position)
        if key not in self._momentary:
            return
        self._momentary.remove(key)
        self.audio_engine.remove_source(
            position.midi_note,
            _source_id("momentary", position),
        )
        self.fretboard.set_position_active(
            position,
            self._position_is_active(position),
        )
        self._refresh_active_frequencies()

    def _change_mode(self, mode: LabelMode) -> None:
        self._stop_all()
        self._mode = mode
        self.fretboard.set_display(self._mode, self._selection)

    @Slot(int)
    def _change_scale(self, index: int) -> None:
        selection = self.scale_combo.itemData(index)
        if not isinstance(selection, ScaleSelection):
            return
        self._stop_all()
        self._selection = selection
        self.fretboard.set_display(self._mode, self._selection)

    @Slot()
    def _stop_all(self) -> None:
        self._latched.clear()
        self._momentary.clear()
        self.audio_engine.stop_all()
        self.fretboard.clear_active_styles()
        self._refresh_active_frequencies()

    @Slot(int)
    def _set_volume(self, value: int) -> None:
        self.audio_engine.set_volume_percent(value)
        self.volume_label.setText(f"{value}%")

    def _refresh_active_frequencies(self) -> None:
        frequencies = sorted(set(self.audio_engine.active_frequencies()))
        if frequencies:
            formatted = ", ".join(
                f"{frequency:.2f} Hz" for frequency in frequencies
            )
        else:
            formatted = "None"
        self.active_frequencies_label.setText(
            f"Active Frequencies: {formatted}"
        )

    @Slot(str)
    def _handle_audio_error(self, detail: str) -> None:
        self._stop_all()
        QMessageBox.warning(
            self,
            "Audio Playback Error",
            detail,
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self.audio_engine.close()
        except Exception as error:
            LOGGER.warning("Audio shutdown failed: %s", error, exc_info=True)
        finally:
            event.accept()
