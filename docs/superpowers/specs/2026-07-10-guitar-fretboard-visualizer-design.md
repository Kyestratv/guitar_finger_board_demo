# Guitar Fretboard Visualizer Design

## Purpose

Build a professional English-language Python desktop application that displays every note on a standard six-string guitar from fret 0 through fret 22. The application teaches pitch locations through four label modes and supports low-latency polyphonic sine-wave playback for individual notes and chords.

## Scope

The initial version supports:

- Standard tuning, from string 1 to string 6: E4, B3, G3, D3, A2, E2.
- Frets 0 through 22, including a dedicated open-string column before fret 1.
- Scientific pitch names, fixed-do solfege, frequencies, and scale degrees.
- All 12 major scales and all 12 natural minor scales.
- Mouse-controlled momentary and latched playback.
- Simultaneous playback of multiple pitches.
- A master volume control and an active-frequency display.

Alternate tunings, harmonic minor, melodic minor, waveform selection, recording, and MIDI input are outside the initial scope.

## Technology

- Python 3.11 or newer
- PySide6 for the desktop GUI
- NumPy for audio sample generation and mixing
- sounddevice for the real-time output stream
- pytest and pytest-qt for automated testing

## Architecture

The program separates deterministic music logic, audio processing, and GUI behavior so that most functionality can be tested without a display or audio device.

### `music_theory.py`

This module owns musical calculations and immutable data models. It generates all 138 string/fret positions and calculates each position's MIDI note number, scientific pitch name, fixed-do syllable, octave, frequency, and scale degree for a selected scale.

### `audio_engine.py`

This module contains two layers:

- A hardware-independent sine mixer that tracks active pitch sources, oscillator phases, master volume, and output sample generation.
- A sounddevice stream adapter that sends mixer output to the default audio device.

The split permits sample-level tests without opening a real sound device.

### `fretboard_widget.py`

This module renders the string labels, fret labels, octave legend, and 6-by-23 matrix of note-position buttons. It updates labels, visibility, colors, and active styling without rebuilding the widget tree.

### `main_window.py`

This module composes the mode controls, Key/Scale selector, volume slider, active-frequency panel, and scrollable fretboard. It coordinates GUI events with the audio engine and handles audio-device errors.

### `main.py`

This is the application entry point. It creates the Qt application, applies the application identity and style, opens the main window, and returns the Qt exit code.

## Music Model

### Pitch calculation

Each open string is represented by its MIDI note number. A position's MIDI note is the open-string note plus its fret number. Frequencies use twelve-tone equal temperament:

`frequency = 440 * 2 ** ((midi_note - 69) / 12)`

A4 is therefore exactly 440 Hz. Displayed frequencies use two decimal places and the professional spacing form `440.00 Hz`.

### Pitch names and solfege

Scientific pitch names use deterministic sharp-based chromatic spelling with Unicode accidentals, such as `A4` and `A♯4`. Fixed-do solfege maps pitch classes to `Do`, `Do♯`, `Re`, `Re♯`, `Mi`, `Fa`, `Fa♯`, `Sol`, `Sol♯`, `La`, `La♯`, and `Ti`. Solfege does not change when the selected scale changes.

### Scales and degrees

The Key/Scale selector provides 12 major keys and 12 natural minor keys. Conventional mixed sharp/flat tonic names are used in the control labels where appropriate.

- Major pitch-class offsets: 0, 2, 4, 5, 7, 9, 11
- Natural minor pitch-class offsets: 0, 2, 3, 5, 7, 8, 10

Scale Degree mode maps those offsets to degrees 1 through 7. A position whose pitch class is outside the selected scale retains its grid space but has no visible interactive button.

## User Interface

All visible copy is English. The main window has three vertical regions.

### Control bar

The top control bar contains:

- Four mutually exclusive radio buttons: `Pitch Name`, `Solfege`, `Frequency`, and `Scale Degree`.
- A `Key / Scale` combo box with all supported major and natural minor scales.
- A `Volume` slider ranging from 0 to 100 percent with a numeric percentage label.
- A `Stop All` button that releases every latched and momentary source.

The Key/Scale selector remains available in every label mode, but it changes fretboard content only in Scale Degree mode.

### Active-frequency panel

A compact panel displays unique active frequencies in ascending order. With no active pitches it shows `Active Frequencies: None`. With multiple pitches it uses a comma-separated form such as `Active Frequencies: 329.63 Hz, 392.00 Hz, 493.88 Hz`.

### Fretboard

The fretboard is placed in a horizontal scroll area so every position remains large enough to read and operate. String 1 is at the top and string 6 is at the bottom. String numbers appear at the left, and fret numbers 0 through 22 appear above their columns.

Each pitch position has one reusable button. Label-mode changes update button text and visibility in place. The open-string column is visually separated from fret 1 to represent the nut.

Each button is colored according to the note's scientific octave. Octaves 2 through 6 receive colors interpolated from red at the lowest octave through orange, green, and cyan toward blue at the highest octave. A labeled `Octave Colors` legend above the fretboard uses the exact same mapping. Active buttons add a strong border and pressed-state treatment without replacing the octave color.

## Interaction and State Flow

### Left-button toggle playback

A left click toggles a position's latched source. The first click starts playback and highlights the button. The second click releases that source. Multiple positions may remain latched to form a chord.

### Right-button momentary playback

Pressing the right mouse button adds a momentary source for that position. Releasing the right mouse button removes it, including when the pointer has moved outside the button before release. A momentary release never removes a separate latched source.

### Duplicate pitches

The same pitch may occur at several fretboard positions. The state model associates each pitch with a set of source identifiers, such as a latched or momentary source from a particular position. The audio voice remains active until the final source for that pitch is removed. The mixer generates one oscillator per unique pitch, preventing unintended amplitude doubling.

### Mode and scale changes

Changing the label mode or selected scale stops all playback before updating the buttons. This prevents a latched pitch from becoming hidden and impossible to release in Scale Degree mode. The `Stop All` control also provides an explicit recovery action at all times.

### Shutdown

Closing the window releases all active sources, stops the stream, and closes the audio device before the application exits.

## Audio Processing

The engine uses one continuous 48 kHz float32 output stream. The callback asks the mixer for exactly the required frame count.

For every active MIDI pitch, the mixer:

1. Calculates the phase increment from the pitch frequency and sample rate.
2. Generates a sine wave beginning at the voice's saved phase.
3. Saves the wrapped ending phase for the next callback.

All unique voices are summed and divided by the active-voice count to avoid clipping. The master-volume factor is applied after mixing. Silence returns a zero-filled float32 buffer. State shared by the Qt event thread and audio callback is protected through a short-lived lock and callback-safe snapshots.

## Error Handling

If the default audio device cannot be opened or the output stream fails to start, the application shows a professional English error dialog. The fretboard and all learning modes remain usable. Playback requests become safe no-ops rather than crashing the GUI.

Unexpected errors in the real-time callback are converted to silence for that block and reported through a thread-safe signal path rather than raising through the audio thread. Invalid internal scale or pitch data raises explicit Python exceptions during development and testing.

## Testing Strategy

Development follows red-green-refactor: each behavior begins with a focused failing test, receives the minimum implementation required to pass, and is then cleaned up while the complete suite remains green.

### Music-theory tests

- Verify all six open strings and representative fret 12 and fret 22 positions.
- Verify A4 equals 440 Hz and other pitches match equal temperament.
- Verify scientific octave boundaries and fixed-do labels.
- Verify every major and natural-minor interval pattern at every tonic.
- Verify degree mapping and exclusion of non-scale pitch classes.

### Audio tests

- Verify source reference tracking, including duplicate pitches and independent latched/momentary sources.
- Verify phase continuity between successive buffers.
- Verify silence, frequency content, master-volume scaling, voice normalization, float32 output, and bounded output range.
- Verify stopping all sources resets active state safely.

### GUI tests

- Verify the fretboard contains 6 strings and 23 positions per string.
- Verify the four radio buttons are mutually exclusive.
- Verify label text in all four modes.
- Verify Scale Degree visibility for in-scale and out-of-scale positions.
- Verify mode and key changes stop playback and update controls.
- Verify mouse-button event routing and active styles.
- Verify the volume label and active-frequency panel.
- Verify audio initialization failure leaves the main window usable.

Qt GUI tests run with the offscreen platform plugin. Hardware-independent tests do not require a speaker or audio device.

## Acceptance Criteria

The implementation is accepted when:

- Every original requirement in `task.md` and every approved clarification is represented in the program.
- The full pytest suite reports zero failures.
- All Python files compile and import successfully.
- The application constructs and displays its complete main window.
- The visible UI uses professional English wording.
- Installation and launch instructions are documented.
- Any hardware limitation encountered during verification is reported narrowly and accurately.
