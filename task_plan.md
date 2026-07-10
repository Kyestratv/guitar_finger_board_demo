# Task Plan: Guitar Fretboard Visualizer

## Goal
Build and verify a professional English-language Python GUI that visualizes a 6-string, 22-fret guitar fretboard, labels pitches in four modes, and supports polyphonic sine-wave playback.

## Current Phase
Phase 3

## Phases

### Phase 1: Requirements and Design
- [x] Read `task.md` and inspect the workspace
- [x] Clarify runtime, dependency, and interaction constraints
- [x] Compare implementation approaches
- [x] Present and validate the design
- [x] Write and self-review the approved design specification
- **Status:** complete

### Phase 2: Implementation Planning
- [x] Create a detailed, test-first implementation plan
- [x] Confirm project structure and dependency strategy
- **Status:** complete

### Phase 3: Test-Driven Implementation
- [ ] Add failing tests for music theory and state behavior
- [ ] Implement the minimal code required to pass each test
- [ ] Implement GUI and audio integration incrementally
- **Status:** in_progress

### Phase 4: Verification
- [ ] Run the complete automated test suite
- [ ] Run static/import checks
- [ ] Launch and inspect the application where the environment permits
- [ ] Check all requirements against `task.md`
- **Status:** pending

### Phase 5: Delivery
- [ ] Review all output files
- [ ] Provide setup and run instructions
- [ ] Summarize verification evidence and any environment limitations
- **Status:** pending

## Key Questions
1. May the project use third-party Python dependencies such as PySide6, NumPy, and sounddevice? **Yes.**
2. How should right-button momentary playback interact with left-button toggle playback? **Track independent sources so releasing a momentary source cannot stop a latched source.**
3. Which scale should Scale Degree mode use? **Add a selector supporting different major and minor keys.**
4. Should standard guitar tuning be used? **Yes: E4, B3, G3, D3, A2, E2 from strings 1 through 6.**
5. Which minor-scale form should be supported? **Natural minor only.**
6. Should Solfege mode use fixed-do or movable-do? **Fixed-do.**

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Treat `task.md` as UTF-8 | Explicit UTF-8 decoding restores the intended Chinese requirements |
| Do not implement before design approval | Required by the brainstorming workflow and avoids choosing the wrong GUI/audio stack |
| Use PySide6, NumPy, and sounddevice as the proposed stack | The user approved third-party dependencies; this stack supports a polished GUI and low-latency polyphonic audio |
| Use standard guitar tuning | Confirmed by the user: strings 1-6 are E4, B3, G3, D3, A2, E2 |
| Use twelve-tone equal temperament with A4 = 440 Hz | Standard basis for calculating the requested note frequencies |
| Add a key/scale selector | The user requested switching Scale Degree mode among different major and minor keys |
| Support natural minor only | Confirmed by the user to keep the initial scope focused |
| Use fixed-do solfege | Confirmed by the user; pitch-class syllables do not change with the selected key |
| Use PySide6 + NumPy + sounddevice | Selected by the user after comparing three implementation approaches |
| Stop playback on mode or scale changes and provide Stop All | Prevents hidden Scale Degree positions from leaving inaccessible latched notes active |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| `task.md` displayed as mojibake under PowerShell default decoding | 1 | Re-read with `Get-Content -Encoding UTF8` |
| Git status/log failed because the directory is not a Git repository | 1 | Record the constraint; decide repository initialization before the design-doc commit step |
| Initial implementation-plan patch failed validation | 1 | Rebuilt the patch by safely prefixing every Markdown line before applying it |
| Worktree safety check tested the absent directory node instead of its target path | 1 | Verified `.worktrees/guitar-fretboard-implementation` with `git check-ignore -v` and then created the worktree |
| Baseline pytest command could not run because pytest is not installed | 1 | Confirmed Task 1 owns dependency installation; retained clean compile and Git baselines |
| Worktree-directory detection command exited 1 when optional directories were absent | 1 | Interpreted the printed Git metadata, then added the default `.worktrees/` ignore rule explicitly |

## Notes
- Re-read this plan before major decisions.
- Log all failures and change the approach instead of repeating them.
