<img width="1094" height="396" alt="image" src="https://github.com/user-attachments/assets/44dfe0d6-5be5-4691-af4c-4e6884c2ee22" />


# Guitar Fretboard Visualizer

## Overview

Guitar Fretboard Visualizer is a professional desktop learning tool for exploring every note on a standard six-string guitar from the open strings (fret 0) through fret 22. It offers four complementary label modes, octave-based colors, and source-aware polyphonic sine-wave playback for single notes and chords.

## Requirements

- Python 3.11 or newer
- Windows, macOS, or Linux with a PySide6-supported desktop environment
- An audio output device and working system audio drivers for playback
- The Python packages listed in `requirements-dev.txt`

## Installation

From PowerShell in the project directory, create and activate a virtual environment, then install the application and test dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

## Running the Application

With the virtual environment active, launch the application from the project directory:

```powershell
python main.py
```

The fretboard can be scrolled horizontally when the complete 23-position width does not fit in the window.

## Building a Windows Executable

Install the development dependencies and build the windowed single-file executable with PyInstaller:

```powershell
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean GuitarFretboardVisualizer.spec
```

The result is `dist\GuitarFretboardVisualizer.exe`. It can be copied to another Windows machine without installing Python. A working audio output device is still required for sound playback.

## Controls

- **Pitch Name** displays scientific pitch notation, such as `A4` and `A♯4`.
- **Solfege** displays fixed-do syllables, such as `Do`, `Re`, and `Mi`.
- **Frequency** displays each pitch frequency in hertz.
- **Scale Degree** displays degrees 1 through 7 for notes in the selected scale. Positions outside the scale remain blank and unavailable.
- **Key / Scale** selects one of 12 major keys or 12 natural minor keys. It changes fretboard content only in Scale Degree mode.
- **Volume** sets the master playback level from 0% to 100%.
- **Stop All** immediately releases all latched and momentary note sources.
- **Left-click a fret position** to latch its note on; left-click it again to release it. Multiple latched notes can form a chord.
- **Press and hold the right mouse button on a fret position** for momentary playback; release the button to stop that source.
- **Active Frequencies** lists the unique frequencies currently playing in ascending order.

Changing the label mode or key/scale stops all playback before refreshing the fretboard, preventing hidden active notes.

## Music Rules

- Standard tuning is used from string 1 (top, thinnest) through string 6 (bottom, thickest): E4, B3, G3, D3, A2, E2.
- Fret 0 represents the open string and appears immediately before fret 1; frets continue through fret 22.
- Frequencies use twelve-tone equal temperament referenced to A4 = 440 Hz.
- Solfege is fixed-do and does not change with the selected key.
- Scale Degree mode supports all 12 major scales and all 12 natural minor scales.
- Harmonic minor, melodic minor, alternate tunings, and enharmonic respelling are outside the current scope.
- Button colors follow the note's scientific octave, progressing from red in lower octaves toward blue in higher octaves. The `Octave Colors` legend uses the same mapping.

## Testing

Run the complete automated test suite from the project directory:

```powershell
python -m pytest -q
```

GUI tests use Qt's offscreen platform and do not require a display or physical audio device. Audio mixer tests generate samples in memory and do not send sound to speakers.

## Audio Troubleshooting

If the default audio output device cannot be opened, the application displays an `Audio Output Unavailable` message. Confirm that an output device is connected, enabled, and not exclusively locked by another program, then restart the application.

The fretboard, labels, scale selection, and octave visualization remain available after an audio-device failure. Playback requests safely become no-ops, so the application can continue in visual-only mode. Runtime audio-rendering errors are also reported without closing the learning interface.

### Adjusting Note Fade Times

The editable note-transition settings are in `guitar_fretboard/audio_config.py`. `ATTACK_TIME_MS = 10.0` controls the fade-in time and `RELEASE_TIME_MS = 20.0` controls the fade-out time; both values are in milliseconds. Restart the application after changing either value. Overly small fade times may reintroduce audible clicks.
