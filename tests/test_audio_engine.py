import importlib
import threading

import numpy as np
import pytest


def audio_api():
    try:
        return importlib.import_module("guitar_fretboard.audio_engine")
    except ImportError as error:
        pytest.fail(f"Audio-engine API is not implemented: {error}")


class FakeStream:
    def __init__(
        self,
        *,
        start_error=None,
        stop_error=None,
        close_error=None,
        **kwargs,
    ):
        self.kwargs = kwargs
        self.start_error = start_error
        self.stop_error = stop_error
        self.close_error = close_error
        self.started = False
        self.stopped = False
        self.closed = False

    def start(self):
        if self.start_error is not None:
            raise self.start_error
        self.started = True

    def stop(self):
        self.stopped = True
        if self.stop_error is not None:
            raise self.stop_error

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


def test_pitch_remains_active_until_final_source_is_removed():
    mixer = audio_api().SineMixer(sample_rate=48_000)
    mixer.add_source(69, "latched:S1:F5")
    mixer.add_source(69, "momentary:S2:F10")

    mixer.remove_source(69, "momentary:S2:F10")

    assert mixer.active_midi_notes() == (69,)
    mixer.remove_source(69, "latched:S1:F5")
    assert mixer.active_midi_notes() == ()


def test_render_is_float32_bounded_and_analytically_phase_continuous():
    mixer = audio_api().SineMixer(sample_rate=48_000)
    mixer.set_volume_percent(100)
    mixer.add_source(69, "test")
    frames = 257
    phase_step = 2.0 * np.pi * 440.0 / mixer.sample_rate

    first = mixer.render(frames)
    second = mixer.render(frames)

    assert first.dtype == np.float32
    assert np.max(np.abs(first)) <= 1.0
    assert first == pytest.approx(
        np.sin(phase_step * np.arange(frames)).astype(np.float32),
        abs=1e-6,
    )
    assert second == pytest.approx(
        np.sin(phase_step * np.arange(frames, frames * 2)).astype(np.float32),
        abs=1e-6,
    )


def test_rendered_block_contains_both_simultaneous_voices():
    module = audio_api()
    mixer = module.SineMixer(sample_rate=48_000)
    mixer.set_volume_percent(100)
    mixer.add_source(69, "a4")
    mixer.add_source(72, "c5")
    frames = 96

    rendered = mixer.render(frames)

    positions = np.arange(frames)
    a4 = np.sin(
        2.0 * np.pi * module.midi_to_frequency(69) * positions / 48_000
    )
    c5 = np.sin(
        2.0 * np.pi * module.midi_to_frequency(72) * positions / 48_000
    )
    assert rendered == pytest.approx(
        ((a4 + c5) / 2.0).astype(np.float32),
        abs=1e-6,
    )
    assert not np.allclose(rendered, a4.astype(np.float32))
    assert not np.allclose(rendered, c5.astype(np.float32))


def test_silence_volume_and_stop_all():
    mixer = audio_api().SineMixer()
    assert np.count_nonzero(mixer.render(64)) == 0
    mixer.add_source(69, "a")
    mixer.set_volume_percent(0)
    assert np.count_nonzero(mixer.render(64)) == 0
    mixer.stop_all()
    assert mixer.active_frequencies() == ()


@pytest.mark.parametrize("midi_note", [-1, 128])
def test_midi_notes_must_be_in_range(midi_note):
    mixer = audio_api().SineMixer()

    with pytest.raises(ValueError, match="MIDI note"):
        mixer.add_source(midi_note, "source")


def test_source_ids_must_be_non_empty():
    mixer = audio_api().SineMixer()

    with pytest.raises(ValueError, match="source_id"):
        mixer.add_source(69, "")
    with pytest.raises(ValueError, match="source_id"):
        mixer.remove_source(69, "")


@pytest.mark.parametrize("percent", [-1, 101])
def test_volume_percent_must_be_in_range(percent):
    mixer = audio_api().SineMixer()

    with pytest.raises(ValueError, match="percent"):
        mixer.set_volume_percent(percent)


def test_active_notes_and_frequencies_are_sorted():
    module = audio_api()
    mixer = module.SineMixer()
    mixer.add_source(72, "high")
    mixer.add_source(60, "low")

    assert mixer.active_midi_notes() == (60, 72)
    assert mixer.active_frequencies() == pytest.approx(
        (module.midi_to_frequency(60), module.midi_to_frequency(72))
    )


def test_engine_starts_stream_fills_channel_and_closes():
    module = audio_api()
    streams = []

    def stream_factory(**kwargs):
        stream = FakeStream(**kwargs)
        streams.append(stream)
        return stream

    engine = module.AudioEngine(stream_factory=stream_factory)
    engine.start()

    stream = streams[0]
    assert stream.started
    assert stream.kwargs["samplerate"] == engine.mixer.sample_rate
    assert stream.kwargs["channels"] == 1
    assert stream.kwargs["dtype"] == "float32"

    engine.add_source(69, "adapter-test")
    reference_mixer = module.SineMixer()
    reference_mixer.add_source(69, "adapter-test")
    outdata = np.full((32, 1), np.nan, dtype=np.float32)
    stream.kwargs["callback"](outdata, 32, object(), object())
    assert np.array_equal(outdata[:, 0], reference_mixer.render(32))

    engine.close()
    assert stream.stopped
    assert stream.closed
    assert engine.available is False
    assert engine.active_frequencies() == ()


def test_engine_uses_a_supplied_falsey_stream_factory():
    module = audio_api()

    class FalseyStreamFactory:
        def __init__(self):
            self.calls = []

        def __bool__(self):
            return False

        def __call__(self, **kwargs):
            self.calls.append(kwargs)
            return FakeStream(**kwargs)

    factory = FalseyStreamFactory()
    engine = module.AudioEngine(stream_factory=factory)

    engine.start()

    assert engine._stream_factory is factory
    assert len(factory.calls) == 1
    engine.close()


def test_engine_ignores_new_sources_until_stream_is_available():
    module = audio_api()
    engine = module.AudioEngine(stream_factory=FakeStream)

    engine.add_source(69, "before-start")

    assert engine.active_frequencies() == ()


def test_factory_error_is_translated_to_audio_device_error():
    module = audio_api()

    def failing_factory(**kwargs):
        del kwargs
        raise OSError("no output device")

    engine = module.AudioEngine(stream_factory=failing_factory)

    with pytest.raises(
        module.AudioDeviceError,
        match="Unable to open the default audio output device: no output device",
    ):
        engine.start()
    assert engine.available is False


def test_stream_start_error_is_translated_to_audio_device_error():
    module = audio_api()
    streams = []

    def stream_factory(**kwargs):
        stream = FakeStream(start_error=OSError("start failed"), **kwargs)
        streams.append(stream)
        return stream

    engine = module.AudioEngine(stream_factory=stream_factory)

    with pytest.raises(module.AudioDeviceError, match="start failed"):
        engine.start()
    assert engine.available is False
    assert streams[0].closed


def test_close_closes_stream_and_clears_state_when_stop_fails():
    module = audio_api()
    streams = []

    def stream_factory(**kwargs):
        stream = FakeStream(stop_error=OSError("stop failed"), **kwargs)
        streams.append(stream)
        return stream

    engine = module.AudioEngine(stream_factory=stream_factory)
    engine.start()

    with pytest.raises(OSError, match="stop failed"):
        engine.close()

    assert streams[0].stopped
    assert streams[0].closed
    assert engine._stream is None
    assert engine.available is False


def test_close_clears_engine_state_when_stream_close_fails():
    module = audio_api()

    def stream_factory(**kwargs):
        return FakeStream(close_error=OSError("close failed"), **kwargs)

    engine = module.AudioEngine(stream_factory=stream_factory)
    engine.start()

    with pytest.raises(OSError, match="close failed"):
        engine.close()

    assert engine._stream is None
    assert engine.available is False


def test_callback_failure_writes_silence_and_emits_only_once(qtbot):
    module = audio_api()

    class FailingMixer(module.SineMixer):
        def render(self, frames):
            del frames
            raise RuntimeError("synthesis exploded")

    engine = module.AudioEngine(mixer=FailingMixer(), stream_factory=FakeStream)
    errors = []
    engine.error_occurred.connect(errors.append)
    outdata = np.ones((16, 1), dtype=np.float32)

    engine._callback(outdata, 16, object(), object())
    engine._callback(outdata, 16, object(), object())

    assert np.count_nonzero(outdata) == 0
    assert errors == ["Audio rendering failed: synthesis exploded"]


def test_concurrent_callback_failures_emit_only_once(qtbot):
    module = audio_api()
    worker_count = 4

    class FailingMixer(module.SineMixer):
        def render(self, frames):
            del frames
            raise RuntimeError("concurrent failure")

    class RaceAmplifyingAudioEngine(module.AudioEngine):
        def __init__(self, *args, **kwargs):
            self._report_read_barrier = threading.Barrier(worker_count)
            super().__init__(*args, **kwargs)

        def __getattribute__(self, name):
            value = super().__getattribute__(name)
            if (
                name == "_callback_error_reported"
                and value is False
                and threading.current_thread() is not threading.main_thread()
            ):
                try:
                    self._report_read_barrier.wait(timeout=0.2)
                except threading.BrokenBarrierError:
                    pass
            return value

    engine = RaceAmplifyingAudioEngine(
        mixer=FailingMixer(),
        stream_factory=FakeStream,
    )
    errors = []
    engine.error_occurred.connect(errors.append)

    threads = [
        threading.Thread(
            target=engine._callback,
            args=(np.ones((16, 1), dtype=np.float32), 16, object(), object()),
        )
        for _ in range(worker_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)

    assert all(not thread.is_alive() for thread in threads)
    qtbot.waitUntil(lambda: len(errors) >= 1)
    qtbot.wait(50)
    assert errors == ["Audio rendering failed: concurrent failure"]
