# Findings and Decisions

## Requirements
- Python graphical desktop application with a horizontal 6-string guitar fretboard.
- String order is 1 (thinnest) at the top through 6 (thickest) at the bottom, with string numbers at left.
- Display frets 0 through 22 from left to right, with fret 0 positioned before fret 1.
- Each string/fret position is interactive and has one of four mutually exclusive label modes:
  - Pitch Name, such as `A4` or `A#4`
  - Solfege, such as `do`, `re`, or `mi`
  - Frequency, such as `440 Hz`
  - Scale Degree, such as `1` for do and `2` for re; chromatic notes outside the selected major scale are hidden
- Color pitch positions by octave from red at low octaves toward blue at high octaves, with an octave legend above the fretboard.
- Play the position's sine wave through the speaker.
- Volume is controlled by a slider.
- Right-button playback is momentary and stops on release.
- Left-button playback toggles each note, allowing multiple simultaneous notes/chords.
- Show all currently playing frequencies in a compact status panel.
- All visible UI text must be professional English.
- Use standard guitar tuning from string 1 to string 6: E4, B3, G3, D3, A2, E2.
- Calculate frequencies using twelve-tone equal temperament referenced to A4 = 440 Hz.
- Add a Key/Scale selector so Scale Degree mode can switch among different major and minor keys.
- Support all 12 major keys and all 12 natural minor keys; harmonic and melodic minor are out of scope.
- Solfege mode uses fixed-do syllables; the selected key affects Scale Degree mode only.

## Research Findings
- The workspace initially contains only `task.md`; no Python source, tests, dependency file, documentation, or assets exist.
- The workspace is not currently a Git repository.
- `task.md` is UTF-8 without a BOM and must be read explicitly as UTF-8 in the current PowerShell environment.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Third-party dependencies are permitted | Confirmed by the user |
| Propose PySide6 + NumPy + sounddevice | Supports a polished GUI, precise interaction handling, and polyphonic sine-wave playback |
| Standard tuning and A4 = 440 Hz equal temperament | Standard tuning was confirmed by the user; equal temperament provides deterministic note frequencies |
| Key/Scale selector for Scale Degree mode | Requested by the user instead of a fixed C-major scale |
| Natural minor only | Confirmed by the user; avoids the extra rules and controls required for harmonic and melodic minor |
| Fixed-do solfege | Confirmed by the user and keeps Solfege mode independent from Key/Scale selection |
| PySide6 + NumPy + sounddevice | User selected the recommended option for professional UI, precise mouse handling, and low-latency polyphony |
| Four-module architecture | User approved separating music theory, audio engine, fretboard widget, and main window, with `main.py` as the entry point |
| Horizontally scrollable 6x23 fretboard | User approved showing frets 0-22 while keeping each position usable and coloring each note position by its own octave |
| Immutable data for 138 positions | User approved precomputing MIDI pitch, scientific pitch name, fixed-do syllable, octave, and equal-tempered frequency |
| Scale Degree follows selected key | User approved 12 major and 12 natural-minor choices; non-scale positions remain as blank cells |
| Continuous red-to-blue octave mapping | User approved coloring individual note positions across octaves 2-6 with a matching legend |
| Source-aware polyphonic state | User approved left-click toggles, right-button momentary playback, and reference tracking so one source cannot stop another |
| One continuous 48 kHz float32 audio stream | User approved phase-continuous sine mixing, active-voice normalization, and live master-volume updates |
| Graceful audio failure | User approved an English error dialog and a still-browsable UI when the output device cannot be opened |
| Stop All and stop-on-display-change | Resolves the hidden-active-note ambiguity when Scale Degree mode hides non-scale positions |

## Design Specification
- Approved design written to `docs/superpowers/specs/2026-07-10-guitar-fretboard-visualizer-design.md`.
- Self-review found no placeholders or contradictory requirements.
- Scope is focused on standard tuning, major/natural-minor degree display, and sine-wave playback.
- The design specification was committed as Git commit `820fc36`.

## Implementation Plan
- Detailed TDD plan written to `docs/superpowers/plans/2026-07-10-guitar-fretboard-visualizer.md`.
- Work is divided into five independently testable tasks: theory, audio, fretboard, main-window integration, and final delivery verification.
- Every approved design section maps to an explicit task, test command, and interface.
- Placeholder/type/spec-coverage review passed, and the plan was committed as `b2da67e`.

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Default PowerShell decoding corrupted Chinese text | Used explicit UTF-8 decoding |
| No Git history is available for context | Treat the directory as a new project |
| Initial plan patch was rejected because one Markdown line lacked an add-file prefix | Reconstructed the patch programmatically and applied it successfully |

## Resources
- `task.md`

## Visual/Browser Findings
- No browser or image inspection has been needed.
