# Click-Free Playback Envelope Design

## Purpose

Remove audible clicks at note start and stop by replacing instantaneous voice gain changes with sample-accurate per-voice attack and release envelopes. Keep both transition durations easy to change without editing mixer algorithms.

## Root Cause

The current mixer inserts a new oscillator at full gain and deletes it immediately when its final source is removed. It also divides every block by the instantaneous unique-voice count. These behaviors create discontinuities at callback boundaries:

- A solo note reaches almost full amplitude within the first 64 samples at 48 kHz.
- Adding a second voice changed the measured block-boundary sample by 0.427682.
- Removing a source can replace an arbitrary nonzero waveform sample with silence.
- Adding or removing one voice instantly changes the amplitude of every existing voice through `gain / len(notes)`.

The click is therefore produced by abrupt amplitude and normalization changes, not by a frequency or phase-calculation error.

## Configuration

Create `guitar_fretboard/audio_config.py`:

~~~python
ATTACK_TIME_MS = 10.0
RELEASE_TIME_MS = 20.0
~~~

These are the only default transition values. A user can edit them and restart the application. `SineMixer` also accepts optional constructor values so tests and future callers can override the defaults without modifying module globals.

Durations must be finite numbers greater than or equal to zero. Zero is supported as an explicit way to disable that transition. Milliseconds are converted to samples with the mixer's sample rate.

## Voice State

The mixer retains one internal voice per unique MIDI note. A voice contains:

- oscillator phase;
- current envelope level from 0.0 to 1.0;
- envelope stage: attack, sustain, or release;
- per-transition level step;
- a state/version marker used for safe mutation under the existing lock.

The external source registry remains a set of source identifiers per MIDI note.

### First source added

Create or reactivate the voice. Start attack from the current envelope level and reach 1.0 over exactly the configured attack sample count. A newly created voice begins at envelope level zero, so its first output sample is zero.

### Additional source for the same pitch

Add the source identifier without restarting phase or envelope. This prevents a second fretboard position or interaction source from retriggering an already sustained pitch.

### Source removed

Removing a non-final source changes only the source set. Removing the final source removes the pitch from the externally active-frequency state immediately but keeps the internal voice in release until its envelope reaches zero.

### Re-trigger during release

If a source is added while a voice is releasing, reverse smoothly into attack from the current envelope level. Do not reset phase and do not jump to zero or one.

### Stop All

Clear the externally active source registry and put every internal voice into release. The short release tails remain audible, but the GUI immediately reports no active frequencies.

### Device shutdown

`AudioEngine.close()` performs best-effort stream cleanup and then clears retained voice/envelope state immediately. It does not wait for a release tail because the output stream is being destroyed.

## Envelope Calculation

Attack and release are linear and sample accurate.

- The first sample of a transition uses the current level.
- The level advances after each sample.
- Attack reaches 1.0 after the configured attack sample count and enters sustain.
- Release reaches 0.0 after the configured release sample count, then the mixer removes the voice.
- Reversing direction calculates a new step from the current level so the newly requested transition still uses the configured duration.

The implementation may vectorize each stage, but behavior must not depend on sounddevice block size.

## Mixing and Normalization

For every sample, calculate each voice's sine value multiplied by its envelope level. Normalize with the sum of current envelope levels rather than the integer voice count:

~~~text
output = sum(sine_i * envelope_i) * master_gain
         -----------------------------------------
         max(1.0, sum(envelope_i))
~~~

This keeps the signal mathematically bounded while allowing the normalization factor to change gradually during attack and release. It avoids nonlinear soft clipping and removes the instantaneous amplitude change imposed on existing voices by `len(notes)`.

Oscillator phases remain continuous across callback blocks and through envelope direction changes.

## Thread Safety

Use the existing mixer lock to keep source mutations, voice stages, phases, and envelope levels consistent. Rendering may hold the lock during the small vectorized state update so GUI source changes take effect at a clean callback boundary. No partially updated voice may be visible to another thread.

## Public Behavior

- `active_midi_notes()` and `active_frequencies()` reflect held sources, not internal release tails.
- `render(frames)` continues returning release samples after the active list becomes empty.
- `stop_all()` initiates release for all voices.
- Add a separate immediate-reset operation for stream shutdown and deterministic cleanup.
- Existing `AudioEngine`, `MainWindow`, left-toggle, right-momentary, and duplicate-source APIs remain compatible.

## Error Handling

Reject nonnumeric, nonfinite, or negative transition durations with a clear `ValueError`. Zero-duration transitions apply their target level immediately and remain safe for rendering.

The audio callback retains its existing behavior: synthesis failures produce silence and emit the runtime error signal once.

## Testing

Follow red-green-refactor. Add focused tests that verify:

- default values come from `audio_config.py`;
- constructor overrides produce exact sample counts;
- attack begins at zero and reaches sustain after the configured duration;
- final-source removal produces a release tail and removes the voice only after zero;
- block boundaries do not change transition timing;
- an additional source for the same pitch does not retrigger attack;
- re-trigger during release is continuous and preserves oscillator phase;
- `stop_all()` starts release while clearing active-frequency reporting;
- envelope-weighted normalization remains bounded and does not instantaneously rescale an existing voice;
- zero duration and invalid duration handling;
- immediate reset used by device close removes all voice state;
- all existing audio, GUI, music-theory, entry-point, and shutdown tests remain green.

Final verification runs the complete pytest suite, `compileall`, the Qt offscreen smoke test, and `git diff --check`.

## Acceptance Criteria

- Start and stop transitions are sample-accurate and controlled by editable attack/release millisecond values.
- No source operation creates the former instantaneous full-scale or voice-count normalization jump.
- Duplicate sources and re-triggering behave continuously.
- Output remains bounded for polyphonic playback.
- Existing UI behavior and active-frequency semantics remain intact.
- Automated verification passes; physical-speaker listening remains a manual hardware check.

