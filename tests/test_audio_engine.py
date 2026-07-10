import importlib
import threading

import numpy as np
import pytest


def audio_api():
    try:
        return importlib.import_module("guitar_fretboard.audio_engine")
    except ImportError as error:
        pytest.fail(f"Audio-engine API is not implemented: {error}")


def test_default_envelope_times_come_from_audio_config():
    module = audio_api()
    from guitar_fretboard import audio_config

    mixer = module.SineMixer()

    assert audio_config.ATTACK_TIME_MS == 10.0
    assert audio_config.RELEASE_TIME_MS == 20.0
    assert mixer.attack_time_ms == audio_config.ATTACK_TIME_MS
    assert mixer.release_time_ms == audio_config.RELEASE_TIME_MS


@pytest.mark.parametrize(
    "value",
    [-1, float("inf"), float("nan"), "10", True, False],
)
def test_envelope_times_must_be_finite_nonnegative_numbers(value):
    module = audio_api()

    with pytest.raises(ValueError, match="attack_time_ms"):
        module.SineMixer(attack_time_ms=value)
    with pytest.raises(ValueError, match="release_time_ms"):
        module.SineMixer(release_time_ms=value)


def test_attack_uses_exact_configured_sample_count():
    module = audio_api()
    mixer = module.SineMixer(
        sample_rate=1_000,
        attack_time_ms=4.0,
        release_time_ms=4.0,
    )
    mixer.set_volume_percent(100)
    mixer.add_source(69, "attack")

    rendered = mixer.render(5)

    phase_step = 2.0 * np.pi * module.midi_to_frequency(69) / 1_000
    sine = np.sin(phase_step * np.arange(5))
    expected_levels = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    assert rendered == pytest.approx(
        (sine * expected_levels).astype(np.float32),
        abs=1e-6,
    )


def test_attack_timing_is_independent_of_block_boundaries():
    module = audio_api()

    split_mixer = module.SineMixer(sample_rate=1_000, attack_time_ms=4.0)
    split_mixer.set_volume_percent(100)
    split_mixer.add_source(69, "attack")
    split = np.concatenate((split_mixer.render(2), split_mixer.render(3)))

    whole_mixer = module.SineMixer(sample_rate=1_000, attack_time_ms=4.0)
    whole_mixer.set_volume_percent(100)
    whole_mixer.add_source(69, "attack")

    assert split == pytest.approx(whole_mixer.render(5), abs=1e-6)


def test_final_source_removal_renders_exact_release_tail():
    module = audio_api()
    mixer = module.SineMixer(
        sample_rate=1_000,
        attack_time_ms=0,
        release_time_ms=4,
    )
    mixer.set_volume_percent(100)
    mixer.add_source(69, "release")
    mixer.render(3)
    mixer.remove_source(69, "release")

    assert mixer.active_midi_notes() == ()
    tail = mixer.render(4)
    after = mixer.render(1)

    phase_step = 2.0 * np.pi * module.midi_to_frequency(69) / 1_000
    phases = phase_step * np.arange(3, 7)
    expected = np.sin(phases) * np.array([1.0, 0.75, 0.5, 0.25])
    assert tail == pytest.approx(expected.astype(np.float32), abs=1e-6)
    assert after == pytest.approx(np.zeros(1, dtype=np.float32))


def test_additional_same_pitch_source_does_not_retrigger_envelope():
    module = audio_api()
    mixer = module.SineMixer(sample_rate=1_000, attack_time_ms=4)
    mixer.add_source(69, "first")
    mixer.render(2)
    level_before = mixer._voices[69].level

    mixer.add_source(69, "second")

    assert mixer._voices[69].level == pytest.approx(level_before)
    assert mixer._voices[69].samples_remaining == 2


def test_retrigger_during_release_preserves_phase_and_attacks_from_current_level():
    module = audio_api()
    mixer = module.SineMixer(
        sample_rate=1_000,
        attack_time_ms=4,
        release_time_ms=4,
    )
    mixer.set_volume_percent(100)
    mixer.add_source(69, "first")
    mixer.render(4)
    mixer.remove_source(69, "first")
    mixer.render(2)
    voice = mixer._voices[69]
    phase_before = voice.phase
    level_before = voice.level

    mixer.add_source(69, "retrigger")

    voice = mixer._voices[69]
    assert voice.phase == pytest.approx(phase_before)
    assert voice.level == pytest.approx(level_before)
    assert voice.samples_remaining == 4
    phase_step = 2.0 * np.pi * module.midi_to_frequency(69) / 1_000
    expected_levels = level_before + (
        (1.0 - level_before) / 4 * np.arange(4)
    )
    rendered = []
    for offset, expected_level in enumerate(expected_levels):
        rendered.append(mixer.render(1)[0])
        assert voice.phase == pytest.approx(
            (phase_before + phase_step * (offset + 1)) % (2.0 * np.pi)
        )
        assert rendered[-1] == pytest.approx(
            np.sin(phase_before + phase_step * offset) * expected_level,
            abs=1e-6,
        )

    assert voice.level == pytest.approx(1.0)
    assert voice.samples_remaining == 0


def test_removing_one_of_two_sources_does_not_begin_release():
    module = audio_api()
    mixer = module.SineMixer(sample_rate=1_000, attack_time_ms=0)
    mixer.add_source(69, "first")
    mixer.add_source(69, "second")

    mixer.remove_source(69, "first")

    assert mixer.active_midi_notes() == (69,)
    assert mixer._voices[69].stage is module._EnvelopeStage.SUSTAIN


def test_stop_all_clears_reporting_and_renders_release_tail_until_reset():
    mixer = audio_api().SineMixer(
        sample_rate=1_000,
        attack_time_ms=0,
        release_time_ms=4,
    )
    mixer.set_volume_percent(100)
    mixer.add_source(69, "stop_all")
    mixer.render(1)

    mixer.stop_all()

    assert mixer.active_frequencies() == ()
    assert np.count_nonzero(mixer.render(4)) > 0
    assert np.count_nonzero(mixer.render(1)) == 0
    mixer.add_source(69, "reset")
    mixer.reset()
    assert np.count_nonzero(mixer.render(1)) == 0


def test_zero_duration_transitions_apply_targets_immediately():
    module = audio_api()
    mixer = module.SineMixer(
        sample_rate=1_000,
        attack_time_ms=0,
        release_time_ms=0,
    )
    mixer.add_source(69, "zero_duration")
    assert mixer._voices[69].level == pytest.approx(1.0)

    mixer.remove_source(69, "zero_duration")

    assert np.count_nonzero(mixer.render(1)) == 0
    assert 69 not in mixer._voices


def test_envelope_weighted_normalization_bounds_output_without_attack_jump():
    module = audio_api()
    mixer = module.SineMixer(sample_rate=1_000, attack_time_ms=4)
    reference = module.SineMixer(sample_rate=1_000, attack_time_ms=4)
    for candidate in (mixer, reference):
        candidate.set_volume_percent(100)
        candidate.add_source(69, "existing")
        candidate.render(5)

    mixer.add_source(72, "new")
    first_with_new_voice = mixer.render(1)
    first_reference = reference.render(1)
    remainder = mixer.render(32)

    assert first_with_new_voice == pytest.approx(first_reference, abs=1e-6)
    complete_output = np.concatenate((first_with_new_voice, remainder))
    assert np.max(np.abs(complete_output)) <= 1.0


def test_simultaneous_intermediate_envelopes_use_exact_weighted_normalization():
    module = audio_api()
    sample_rate = 1_000
    mixer = module.SineMixer(sample_rate=sample_rate, attack_time_ms=8)
    mixer.set_volume_percent(100)
    mixer.add_source(69, "first")
    mixer.render(2)
    mixer.add_source(72, "second")
    mixer.render(2)

    frames = 3
    rendered = mixer.render(frames)

    positions = np.arange(frames)
    first_levels = np.array([0.5, 0.625, 0.75])
    second_levels = np.array([0.25, 0.375, 0.5])
    first = np.sin(
        2.0
        * np.pi
        * module.midi_to_frequency(69)
        * (positions + 4)
        / sample_rate
    )
    second = np.sin(
        2.0
        * np.pi
        * module.midi_to_frequency(72)
        * (positions + 2)
        / sample_rate
    )
    expected = (
        first * first_levels + second * second_levels
    ) / np.maximum(1.0, first_levels + second_levels)

    assert rendered == pytest.approx(expected.astype(np.float32), abs=1e-6)


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
    mixer = audio_api().SineMixer(sample_rate=48_000, attack_time_ms=0)
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
    mixer = module.SineMixer(sample_rate=48_000, attack_time_ms=0)
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
    mixer = audio_api().SineMixer(
        sample_rate=1_000,
        attack_time_ms=0,
        release_time_ms=4,
    )
    assert np.count_nonzero(mixer.render(64)) == 0
    mixer.add_source(69, "a")
    mixer.set_volume_percent(0)
    assert np.count_nonzero(mixer.render(64)) == 0
    mixer.set_volume_percent(100)
    mixer.stop_all()
    assert mixer.active_frequencies() == ()
    assert np.count_nonzero(mixer.render(4)) > 0
    mixer.add_source(69, "reset")
    mixer.reset()
    assert np.count_nonzero(mixer.render(1)) == 0


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


def test_engine_retains_a_supplied_falsey_mixer():
    module = audio_api()

    class FalseyMixer(module.SineMixer):
        def __bool__(self):
            return False

    mixer = FalseyMixer()

    engine = module.AudioEngine(mixer=mixer, stream_factory=FakeStream)

    assert engine.mixer is mixer


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
    assert engine.mixer._voices == {}


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
    assert engine.mixer._voices == {}


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
