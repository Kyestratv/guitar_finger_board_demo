# Final Review Fix

## Scope and outcomes

- Contained `AudioEngine.close()` failures inside `MainWindow.closeEvent`, logged
  them without a modal dialog, and always accepted shutdown.
- Preserved audio-engine cleanup guarantees when stream stop or close raises.
- Changed the reviewed `audio_engine` and `stream_factory` dependency injection
  sites to distinguish `None` from supplied falsey doubles.
- Added scale-kind-specific conventional root spellings while retaining exactly
  12 major and 12 natural-minor choices.
- Enforced `ScaleKind` in `ScaleSelection` and made `scale_degree` exhaustive.
- Strengthened the requested audio, theory, fretboard-coordinate, and
  duplicate-pitch regressions.
- Synchronized `task_plan.md` and `progress.md` at Phase 6 complete.

## RED evidence

Command:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_audio_engine.py::test_engine_uses_a_supplied_falsey_stream_factory tests/test_music_theory.py::test_all_scale_degrees_exclusions_and_conventional_labels tests/test_music_theory.py::test_scale_selection_rejects_non_scale_kind_values tests/test_main_window.py::test_window_uses_a_supplied_falsey_audio_engine tests/test_main_window.py::test_close_accepts_event_and_logs_nonmodal_warning_when_audio_close_fails -vv
```

Result: exit 1 with expected failures showing that a falsey factory and audio
engine were replaced, C♯/G♯ natural-minor roots were flat-spelled, invalid kinds
were accepted, and the injected shutdown exception escaped the close event.

## GREEN and final verification

Focused changed-module suite:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_audio_engine.py tests/test_music_theory.py tests/test_fretboard_widget.py tests/test_main_window.py -q
```

Output: `72 passed in 2.82s` (exit 0).

Full suite:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q
```

Output: `75 passed in 2.62s` (exit 0).

Compile check:

```powershell
python -m compileall -q guitar_fretboard main.py tests
```

Output: none (exit 0).

Offscreen GUI smoke:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -c "from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication; from guitar_fretboard.audio_engine import AudioEngine; from guitar_fretboard.main_window import MainWindow; app=QApplication([]); window=MainWindow(audio_engine=AudioEngine(), start_audio=False); window.show(); QTimer.singleShot(100, app.quit); raise SystemExit(app.exec())"
```

Output: none (exit 0).

Whitespace verification:

```powershell
git diff --check
git diff --cached --check
```

Output: after final staging, both commands exited 0 with no output. The initial
working-tree check also exited 0; it reported only Git for Windows LF-to-CRLF
conversion warnings and no whitespace errors.

## Files

- `guitar_fretboard/audio_engine.py`
- `guitar_fretboard/main_window.py`
- `guitar_fretboard/music_theory.py`
- `tests/test_audio_engine.py`
- `tests/test_fretboard_widget.py`
- `tests/test_main_window.py`
- `tests/test_music_theory.py`
- `task_plan.md`
- `progress.md`
- `.superpowers/sdd/final-fix-report.md`

## Limitations

- No physical audio device or speaker playback was verified. Audio evidence is
  limited to analytic in-memory mixer tests, fake stream-adapter tests, cleanup
  regressions, and an offscreen GUI smoke run with `start_audio=False`.

## Second Final Re-review Fix

### Scope

- Changed the remaining `AudioEngine` mixer injection from a truthiness fallback
  to an explicit `None` check.
- Added a focused falsey-mixer identity regression proving the exact supplied
  mixer object is retained.
- Corrected the final requirement audit to reference the renamed analytic
  phase-continuity test and the simultaneous-voice block test.

### RED evidence

```powershell
python -m pytest tests/test_audio_engine.py::test_engine_retains_a_supplied_falsey_mixer -vv
```

Output: `1 failed in 1.20s` (exit 1). The assertion showed that the supplied
`FalseyMixer` was replaced by a new `SineMixer`.

### GREEN and final verification

```powershell
python -m pytest tests/test_audio_engine.py -q
```

Output: `20 passed in 1.25s` (exit 0).

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q
```

Output: `76 passed in 3.06s` (exit 0).

```powershell
python -m compileall -q guitar_fretboard main.py tests
```

Output: none (exit 0).

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -c "from PySide6.QtCore import QTimer; from PySide6.QtWidgets import QApplication; from guitar_fretboard.audio_engine import AudioEngine; from guitar_fretboard.main_window import MainWindow; app=QApplication([]); window=MainWindow(audio_engine=AudioEngine(), start_audio=False); window.show(); QTimer.singleShot(100, app.quit); raise SystemExit(app.exec())"
```

Output: none (exit 0).

```powershell
git diff --check
git diff --cached --check
```

Output: both commands exited 0 without whitespace errors after final staging.

### Files

- `guitar_fretboard/audio_engine.py`
- `tests/test_audio_engine.py`
- `progress.md`
- `.superpowers/sdd/final-fix-report.md`

### Limitations

- No physical audio device or speaker playback was verified. The second-wave
  audio verification used mixer identity/state tests, the full automated suite,
  and an offscreen GUI smoke with `start_audio=False`.
