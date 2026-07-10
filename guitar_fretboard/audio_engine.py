import math
from threading import RLock

import numpy as np
from PySide6.QtCore import QObject, Signal
import sounddevice

from guitar_fretboard.music_theory import midi_to_frequency


class AudioDeviceError(RuntimeError):
    pass


class SineMixer:
    def __init__(self, sample_rate=48_000):
        self.sample_rate = sample_rate
        self._lock = RLock()
        self._sources: dict[int, set[str]] = {}
        self._phases: dict[int, float] = {}
        self._gain = 0.5

    @staticmethod
    def _validate_source(midi_note, source_id):
        if not isinstance(midi_note, int) or not 0 <= midi_note <= 127:
            raise ValueError("MIDI note must be an integer between 0 and 127")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_id must be a non-empty string")

    def add_source(self, midi_note, source_id):
        self._validate_source(midi_note, source_id)
        with self._lock:
            self._sources.setdefault(midi_note, set()).add(source_id)
            self._phases.setdefault(midi_note, 0.0)

    def remove_source(self, midi_note, source_id):
        self._validate_source(midi_note, source_id)
        with self._lock:
            sources = self._sources.get(midi_note)
            if sources is None:
                return
            sources.discard(source_id)
            if not sources:
                del self._sources[midi_note]
                self._phases.pop(midi_note, None)

    def stop_all(self):
        with self._lock:
            self._sources.clear()
            self._phases.clear()

    def set_volume_percent(self, percent):
        if not 0 <= percent <= 100:
            raise ValueError("percent must be between 0 and 100")
        with self._lock:
            self._gain = percent / 100.0

    def active_midi_notes(self):
        with self._lock:
            return tuple(sorted(self._sources))

    def active_frequencies(self):
        return tuple(midi_to_frequency(note) for note in self.active_midi_notes())

    def render(self, frames):
        with self._lock:
            notes = tuple(sorted(self._sources))
            phases = {note: self._phases[note] for note in notes}
            gain = self._gain

        if not notes:
            return np.zeros(frames, dtype=np.float32)

        sample_positions = np.arange(frames, dtype=np.float64)
        mixed = np.zeros(frames, dtype=np.float64)
        next_phases = {}
        for note in notes:
            frequency = midi_to_frequency(note)
            phase_step = 2.0 * math.pi * frequency / self.sample_rate
            phase = phases[note]
            mixed += np.sin(phase + phase_step * sample_positions)
            next_phases[note] = (phase + phase_step * frames) % (2.0 * math.pi)

        with self._lock:
            for note, phase in next_phases.items():
                if note in self._sources and self._phases.get(note) == phases[note]:
                    self._phases[note] = phase

        mixed *= gain / len(notes)
        return mixed.astype(np.float32)


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
