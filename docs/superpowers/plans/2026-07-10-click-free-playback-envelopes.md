# Click-Free Playback Envelopes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate note-start and note-stop clicks with configurable sample-accurate attack/release envelopes while preserving source-aware polyphony and existing UI behavior.

**Architecture:** Add editable audio defaults in one configuration module and replace the mixer's phase-only voice data with per-pitch oscillator/envelope state. Held-source reporting stays separate from internal release tails; envelope-gain-weighted normalization changes continuously and keeps polyphonic output bounded.

**Tech Stack:** Python 3.11+, NumPy, sounddevice, PySide6, pytest, pytest-qt

## Global Constraints

- Default `ATTACK_TIME_MS` is 10.0 and default `RELEASE_TIME_MS` is 20.0.
- Both defaults live only in `guitar_fretboard/audio_config.py` and remain easy to edit.
- Envelope timing is measured in samples and must not depend on sounddevice block size.
- The first attack sample uses gain 0.0; release retains a voice until gain reaches 0.0.
- Additional sources for the same MIDI pitch do not retrigger phase or envelope.
- Re-triggering during release starts attack from the current level without resetting phase.
- `active_midi_notes()` and `active_frequencies()` report held sources, not release tails.
- `stop_all()` begins release for every voice; device shutdown resets voices immediately.
- Normalize each sample by `max(1.0, sum(envelope_gains))`.
- Existing 48 kHz float32 stream, source identifiers, GUI controls, error signals, and professional English copy remain compatible.
- Tests must not require a physical display, audio device, or speaker.

## File Structure

- Create `guitar_fretboard/audio_config.py`: user-editable default transition durations.
- Modify `guitar_fretboard/audio_engine.py`: envelope state, transitions, normalization, reset, and shutdown integration.
- Modify `tests/test_audio_engine.py`: sample-accurate envelope and lifecycle regressions.
- Modify `README.md`: explain where and how to change transition durations.
- Modify `task_plan.md`, `findings.md`, and `progress.md`: record implementation and fresh verification evidence.

---

### Task 1: Configurable Sample-Accurate Voice Envelope

**Files:**
- Create: `guitar_fretboard/audio_config.py`
- Modify: `guitar_fretboard/audio_engine.py`
- Modify: `tests/test_audio_engine.py`

**Interfaces:**
- Consumes: `midi_to_frequency(int) -> float` and the existing `SineMixer(sample_rate=...)` behavior.
- Produces: `ATTACK_TIME_MS`, `RELEASE_TIME_MS`, `SineMixer(sample_rate=48_000, attack_time_ms=None, release_time_ms=None)`, private `_EnvelopeStage` and `_VoiceState`, and unchanged source/volume/query methods.

- [ ] **Step 1: Write failing tests for configuration, validation, and exact attack samples**

Add tests with a 1 kHz sample rate so milliseconds map directly to samples:

~~~python
def test_default_envelope_times_come_from_audio_config():
    module = audio_api()
    from guitar_fretboard import audio_config

    mixer = module.SineMixer()

    assert audio_config.ATTACK_TIME_MS == 10.0
    assert audio_config.RELEASE_TIME_MS == 20.0
    assert mixer.attack_time_ms == audio_config.ATTACK_TIME_MS
    assert mixer.release_time_ms == audio_config.RELEASE_TIME_MS

@pytest.mark.parametrize("value", [-1, float("inf"), float("nan"), "10"])
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
~~~

Also add `test_attack_timing_is_independent_of_block_boundaries`: render 2 then 3 frames and compare the concatenation with a separate mixer rendering 5 frames once.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

~~~powershell
python -m pytest tests/test_audio_engine.py -k "default_envelope or envelope_times or attack_" -v
~~~

Expected: FAIL because `audio_config.py`, constructor duration arguments, and attack behavior do not exist.

- [ ] **Step 3: Create editable defaults and voice-state definitions**

Create:

~~~python
# guitar_fretboard/audio_config.py
ATTACK_TIME_MS = 10.0
RELEASE_TIME_MS = 20.0
~~~

In `audio_engine.py` import those values and add:

~~~python
from dataclasses import dataclass
from enum import Enum
import math

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
~~~

Validate a duration with `isinstance(value, (int, float)) and not `bool`, `math.isfinite(value)`, and `value >= 0`. Convert duration to samples with `round(value * sample_rate / 1000.0)` and clamp positive durations to at least one sample; zero remains zero.

- [ ] **Step 4: Implement transition and envelope generation helpers**

Replace `_phases` with `_voices: dict[int, _VoiceState]`. Add:

~~~python
def _begin_transition(self, voice, target_level, duration_samples, stage):
    voice.stage = stage
    voice.target_level = target_level
    voice.samples_remaining = duration_samples
    if duration_samples == 0:
        voice.level = target_level
        voice.level_step = 0.0
    else:
        voice.level_step = (target_level - voice.level) / duration_samples

def _render_envelope(self, voice, frames):
    levels = np.empty(frames, dtype=np.float64)
    cursor = 0
    while cursor < frames:
        if voice.samples_remaining == 0:
            levels[cursor:] = voice.level
            break
        count = min(frames - cursor, voice.samples_remaining)
        levels[cursor:cursor + count] = (
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
~~~

On first source, create a voice at level zero and begin attack. Hold the existing mixer lock during render state mutation so a source event occurs only between coherent callback blocks.

- [ ] **Step 5: Replace integer voice-count normalization**

For each internal voice, render its phase-continuous sine and envelope. Accumulate both weighted samples and per-sample envelope totals:

~~~python
mixed += sine * envelope
envelope_total += envelope
normalizer = np.maximum(1.0, envelope_total)
output = mixed * master_gain / normalizer
~~~

Remove voices whose release reached level zero after their contribution for the block is calculated. Return float32.

- [ ] **Step 6: Verify GREEN and regression state**

Run:

~~~powershell
python -m pytest tests/test_audio_engine.py -k "default_envelope or envelope_times or attack_" -v
python -m pytest tests/test_audio_engine.py -q
python -m pytest -q
~~~

Expected: focused attack tests pass, the complete audio tests pass, and the full suite has zero failures.

- [ ] **Step 7: Commit Task 1**

~~~powershell
git add guitar_fretboard/audio_config.py guitar_fretboard/audio_engine.py tests/test_audio_engine.py
git commit -m "feat: add configurable audio envelopes"
~~~

---

### Task 2: Release, Re-trigger, Stop-All, and Shutdown Semantics

**Files:**
- Modify: `guitar_fretboard/audio_engine.py`
- Modify: `tests/test_audio_engine.py`

**Interfaces:**
- Consumes: `_VoiceState` and transition helpers from Task 1.
- Produces: final-source release tails, smooth re-triggering, `SineMixer.reset() -> None`, fading `stop_all()`, and immediate-reset `AudioEngine.close()`.

- [ ] **Step 1: Write failing release and source-lifetime tests**

Add:

~~~python
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
~~~

Add behavior tests for:

- re-trigger during release starts from the current level, preserves phase, and reaches sustain over the configured attack duration;
- removing one of two sources does not begin release;
- `stop_all()` immediately clears active-frequency reporting but renders release tails;
- zero attack/release applies targets immediately;
- envelope-weighted two-voice normalization stays within [-1, 1] and adding the new voice starts with no discontinuous rescaling of the existing voice.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

~~~powershell
python -m pytest tests/test_audio_engine.py -k "release or retrigger or additional_same_pitch or stop_all or zero_duration or normalization" -v
~~~

Expected: FAIL because final-source removal still deletes state immediately and Stop All/reset semantics are not implemented.

- [ ] **Step 3: Implement source transitions**

`add_source` behavior under the lock:

- New MIDI note: create voice and begin attack.
- Existing held note: add the source only.
- Releasing voice with no held sources: add source and begin attack from its current level without resetting phase.

`remove_source` removes only the specified source. When the final source disappears, begin release from the current level. Keep the voice until its release reaches zero.

- [ ] **Step 4: Implement fading Stop All and immediate reset**

Implement:

~~~python
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
~~~

Update `AudioEngine.close()` so its outer `finally` calls `self.mixer.reset()` and preserves all existing stream/state cleanup guarantees. Do not wait for release samples while destroying the output stream.

- [ ] **Step 5: Update old tests for intentional new behavior**

Change tests that assumed `stop_all()` immediately produced no internal samples. They must assert active frequencies clear immediately, release output exists for the configured duration, and `reset()` produces immediate silence. Keep callback, cleanup, falsey dependency, and stream lifecycle assertions unchanged.

- [ ] **Step 6: Verify GREEN and full regression**

Run:

~~~powershell
python -m pytest tests/test_audio_engine.py -k "release or retrigger or additional_same_pitch or stop_all or zero_duration or normalization" -v
python -m pytest tests/test_audio_engine.py -q
python -m pytest -q
~~~

Expected: all focused lifecycle tests pass, all audio tests pass, and the full suite reports zero failures.

- [ ] **Step 7: Commit Task 2**

~~~powershell
git add guitar_fretboard/audio_engine.py tests/test_audio_engine.py
git commit -m "fix: fade voice start and stop transitions"
~~~

---

### Task 3: Documentation, Evidence, and Final Verification

**Files:**
- Modify: `README.md`
- Modify: `task_plan.md`
- Modify: `findings.md`
- Modify: `progress.md`

**Interfaces:**
- Consumes: completed envelope behavior and configuration from Tasks 1-2.
- Produces: user instructions and final verification record; no new runtime API.

- [ ] **Step 1: Document editable transition settings**

In README `Audio Troubleshooting`, add a subsection named `Adjusting Note Fade Times`. State that `guitar_fretboard/audio_config.py` contains `ATTACK_TIME_MS = 10.0` and `RELEASE_TIME_MS = 20.0`, values are milliseconds, changes take effect after restarting, and overly small values may reintroduce clicks.

- [ ] **Step 2: Run fresh full verification**

Run:

~~~powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q
python -m compileall -q guitar_fretboard main.py tests
python -c "from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication; from guitar_fretboard.audio_engine import AudioEngine; from guitar_fretboard.main_window import MainWindow; app=QApplication([]); window=MainWindow(audio_engine=AudioEngine(), start_audio=False); window.show(); QTimer.singleShot(100, app.quit); raise SystemExit(app.exec())"
git diff --check
~~~

Expected: pytest has zero failures; compileall exits 0; the offscreen window smoke exits 0; `git diff --check` emits no whitespace errors.

- [ ] **Step 3: Update project evidence**

Mark Phase 7 complete in `task_plan.md`. In `findings.md` record the confirmed root cause and chosen envelope/normalization model. In `progress.md` record exact focused/full counts, compile/smoke/diff exit states, changed files, and the physical-speaker limitation if it remains untested.

- [ ] **Step 4: Review the final diff**

Run:

~~~powershell
git status --short
git diff --stat
git diff --check
~~~

Expected: only the planned files are changed and no whitespace errors appear.

- [ ] **Step 5: Commit Task 3**

~~~powershell
git add README.md task_plan.md findings.md progress.md
git commit -m "docs: document configurable note envelopes"
~~~

