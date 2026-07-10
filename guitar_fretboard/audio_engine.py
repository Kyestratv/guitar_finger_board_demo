import math
from dataclasses import dataclass
from enum import Enum
from threading import Lock, RLock

import numpy as np
from PySide6.QtCore import QObject, Signal
import sounddevice

from guitar_fretboard.audio_config import ATTACK_TIME_MS, RELEASE_TIME_MS
from guitar_fretboard.music_theory import midi_to_frequency


class AudioDeviceError(RuntimeError):
    pass


class _EnvelopeStage(Enum):
    ATTACK = "attack"
    SUSTAIN = "sustain"
    RELEASE = "release"


@dataclass(slots=True)
class _VoiceState:
    phase: float = 0.0
    level: float = 0.0
    stage: _EnvelopeStage = _EnvelopeStage.ATTACK
    target_level: float = 1.0
    samples_remaining: int = 0
    level_step: float = 0.0


class SineMixer:
    def __init__(
        self,
        sample_rate=48_000,
        attack_time_ms=None,
        release_time_ms=None,
    ):
        self.sample_rate = sample_rate
        self.attack_time_ms = self._validated_duration(
            "attack_time_ms",
            ATTACK_TIME_MS if attack_time_ms is None else attack_time_ms,
        )
        self.release_time_ms = self._validated_duration(
            "release_time_ms",
            RELEASE_TIME_MS if release_time_ms is None else release_time_ms,
        )
        self._attack_samples = self._duration_samples(self.attack_time_ms)
        self._release_samples = self._duration_samples(self.release_time_ms)
        self._lock = RLock()
        self._sources: dict[int, set[str]] = {}
        self._voices: dict[int, _VoiceState] = {}
        self._gain = 0.5

    @staticmethod
    def _validated_duration(name, value):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"{name} must be a finite nonnegative number")
        return value

    def _duration_samples(self, duration_ms):
        if duration_ms == 0:
            return 0
        return max(1, round(duration_ms * self.sample_rate / 1000.0))

    @staticmethod
    def _begin_transition(
        voice,
        target_level,
        duration_samples,
        stage,
    ):
        voice.stage = stage
        voice.target_level = target_level
        voice.samples_remaining = duration_samples
        if duration_samples == 0:
            voice.level = target_level
            voice.level_step = 0.0
            if target_level == 1.0:
                voice.stage = _EnvelopeStage.SUSTAIN
        else:
            voice.level_step = (target_level - voice.level) / duration_samples

    @staticmethod
    def _render_envelope(voice, frames):
        levels = np.empty(frames, dtype=np.float64)
        cursor = 0
        while cursor < frames:
            if voice.samples_remaining == 0:
                levels[cursor:] = voice.level
                break
            count = min(frames - cursor, voice.samples_remaining)
            levels[cursor : cursor + count] = (
                voice.level
                + voice.level_step * np.arange(count, dtype=np.float64)
            )
            voice.level += voice.level_step * count
            voice.samples_remaining -= count
            cursor += count
            if voice.samples_remaining == 0:
                voice.level = voice.target_level
                voice.level_step = 0.0
                if voice.level == 1.0:
                    voice.stage = _EnvelopeStage.SUSTAIN
        return levels

    @staticmethod
    def _validate_source(midi_note, source_id):
        if not isinstance(midi_note, int) or not 0 <= midi_note <= 127:
            raise ValueError("MIDI note must be an integer between 0 and 127")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("source_id must be a non-empty string")

    def add_source(self, midi_note, source_id):
        self._validate_source(midi_note, source_id)
        with self._lock:
            sources = self._sources.setdefault(midi_note, set())
            was_releasing = not sources and midi_note in self._voices
            sources.add(source_id)
            if midi_note not in self._voices:
                voice = _VoiceState()
                self._begin_transition(
                    voice,
                    1.0,
                    self._attack_samples,
                    _EnvelopeStage.ATTACK,
                )
                self._voices[midi_note] = voice
            elif was_releasing:
                self._begin_transition(
                    self._voices[midi_note],
                    1.0,
                    self._attack_samples,
                    _EnvelopeStage.ATTACK,
                )

    def remove_source(self, midi_note, source_id):
        self._validate_source(midi_note, source_id)
        with self._lock:
            sources = self._sources.get(midi_note)
            if sources is None:
                return
            sources.discard(source_id)
            if not sources:
                del self._sources[midi_note]
                voice = self._voices.get(midi_note)
                if voice is not None:
                    self._begin_transition(
                        voice,
                        0.0,
                        self._release_samples,
                        _EnvelopeStage.RELEASE,
                    )

    def stop_all(self):
        with self._lock:
            self._sources.clear()
            for voice in self._voices.values():
                self._begin_transition(
                    voice,
                    target_level=0.0,
                    duration_samples=self._release_samples,
                    stage=_EnvelopeStage.RELEASE,
                )

    def reset(self):
        with self._lock:
            self._sources.clear()
            self._voices.clear()

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
            if not self._voices:
                return np.zeros(frames, dtype=np.float32)

            sample_positions = np.arange(frames, dtype=np.float64)
            mixed = np.zeros(frames, dtype=np.float64)
            envelope_total = np.zeros(frames, dtype=np.float64)
            released_notes = []
            for note, voice in self._voices.items():
                frequency = midi_to_frequency(note)
                phase_step = 2.0 * math.pi * frequency / self.sample_rate
                sine = np.sin(voice.phase + phase_step * sample_positions)
                voice.phase = (voice.phase + phase_step * frames) % (
                    2.0 * math.pi
                )
                envelope = self._render_envelope(voice, frames)
                mixed += sine * envelope
                envelope_total += envelope
                if voice.stage is _EnvelopeStage.RELEASE and voice.level == 0.0:
                    released_notes.append(note)

            for note in released_notes:
                self._voices.pop(note, None)

            normalizer = np.maximum(1.0, envelope_total)
            output = mixed * self._gain / normalizer
            return output.astype(np.float32)


class AudioEngine(QObject):
    error_occurred = Signal(str)

    def __init__(self, mixer=None, stream_factory=None):
        super().__init__()
        self.mixer = mixer if mixer is not None else SineMixer()
        self._stream_factory = (
            stream_factory
            if stream_factory is not None
            else sounddevice.OutputStream
        )
        self._stream = None
        self.available = False
        self._callback_error_reported = False
        self._callback_error_lock = Lock()

    def _callback(self, outdata, frames, time_info, status):
        del time_info, status
        try:
            outdata[:, 0] = self.mixer.render(frames)
        except Exception as exc:
            outdata.fill(0)
            with self._callback_error_lock:
                report_error = not self._callback_error_reported
                if report_error:
                    self._callback_error_reported = True
            if report_error:
                self.error_occurred.emit(f"Audio rendering failed: {exc}")

    def start(self):
        stream = None
        try:
            stream = self._stream_factory(
                samplerate=self.mixer.sample_rate,
                channels=1,
                dtype="float32",
                callback=self._callback,
            )
            self._stream = stream
            stream.start()
            self.available = True
        except Exception as exc:
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
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
        stream = self._stream
        try:
            self.stop_all()
            if stream is not None:
                try:
                    stream.stop()
                finally:
                    stream.close()
        finally:
            self.mixer.reset()
            self._stream = None
            self.available = False
