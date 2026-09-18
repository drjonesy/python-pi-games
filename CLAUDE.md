# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A pygame-ce arcade **platform** ("the cabinet") for a Raspberry Pi 4B+ driven by a USB DDR dance mat. It boots into a game picker; Pac-Man is the only installed title. All code lives in `python-version/`. `python-version/README.md` is the long-form reference (pad calibration, audio debugging, fidelity notes) — read the relevant section there before changing pad, audio, or leaderboard behaviour.

The `node-version/` that the README, `REWRITE-INSTRUCTIONS.md`, and Pac-Man's constants refer to (`engine.js` line numbers) has been removed from this repo. Those references are historical; don't go looking for it.

## Commands

Run everything from `python-version/` using the venv (the only runtime dependency is `pygame-ce`; `requirements-dev.txt` adds `pytest` and `cairosvg`).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

.venv/bin/python main.py --windowed              # desktop testing, 3x scale, opens on picker
.venv/bin/python main.py --windowed --game <id>  # boot straight into one game
.venv/bin/python main.py --list-games            # which games registered / which failed to import

.venv/bin/python -m pytest tests/ -q                                  # whole suite, headless
.venv/bin/python -m pytest tests/test_ghost_house.py -q               # one file
.venv/bin/python -m pytest tests/test_games.py -q -k <name>           # one test

.venv/bin/python tools/make_preview.py --game <id>   # regenerate a picker preview.png
.venv/bin/python tools/convert_assets.py             # Pac-Man SVG->PNG, MP3->OGG (desktop only; needs ffmpeg)
.venv/bin/python tools/convert_dino_assets.py        # DINO RUN art + preview from ../_games/dino-run/
```

There is no linter or build step configured. Tests are headless (no display or mixer needed). The game loop and rendering are verified by playing, not by tests.

## Adding a game

Use the **`/new-game`** skill (`.claude/skills/new-game/`). It has the full contract, the dance-mat design rules, a checklist, and a skeleton to copy (`reference/game_template.py`). The short version is: drop a package into `python-version/games/<id>/` with a `game.py` exposing `SPEC = GameSpec(...)`, where `SPEC.id` matches the folder name. Don't edit shared files; `games/registry.py` discovers games by scanning that folder.

## Architecture

The top-level split is **the machine** (`cabinet/`) and **the games on it** (`games/`). The contract between them is `cabinet/game.py`: `Game`, `GameSpec`, `GameContext`.

- **`main.py`** parses args, opens audio and the window, then hands over to `cabinet/app.py` (`Cabinet`). The shell owns two screens (the picker and the current game), the modals (name entry, operator menu) and the frame loop.
- **Fixed timestep** (`cabinet/engine.py`): the simulation runs at 120 Hz and rendering at 60 Hz. **Never lower `SIM_HZ`.** Pac-Man's ghost-house re-entry windows are 0.2 tiles wide, and an eaten ghost skips over them at 60 Hz. `tests/test_ghost_house.py` includes a test that asserts 60 Hz breaks respawn, and it is supposed to stay that way.
- **Input funnels through one place.** Keys and pad buttons become eight actions (`up down left right select delete pause mute`) in `cabinet/gamepad.py`. `Cabinet._handle_action` is the only routing table: a modal gets the action if one is open, otherwise the current screen does. Releases go only to a running game (`handle_release`) and can be lost, so treat one as meaning "not held any more". The operator menu and its passcode read **physical panels** (the `panels` table in `data/pad_mapping.json`), not actions.
- **Dance-mat constraints matter for design.** On the real mat, `mute` is unbound and `delete` only means something during name entry. The shape panels (□ △) sit in the mat's corners and get clipped by feet, so nothing that acts during play may be bound to them. The centre sensor (axis 1) fires constantly and must never be bound. Axis bindings aren't used at all (`tests/test_gamepad.py` checks this). A game has to be playable with four arrows plus START.
- **Per-game isolation.** Each game gets its own sprite pack (`context.assets`, from `games/<id>/assets/manifest.json`, loaded on first play), a sound view that prefixes its clip names (so all clips share one mixer, one volume and one mute), and its own high-score board. Pac-Man's board is `data/data.json` for legacy reasons; other games use `data/scores/<id>.json`. A game that fails to import is skipped with a log line, not a crash, because the cabinet has no keyboard to recover with. Keep it that way: **games must not touch pygame or the display at import time.**
- **Screen:** fixed 224×296 portrait logical surface (`cabinet/constants.py`), stretched by `pygame.SCALED`. Games lay themselves out inside it and use the shared palette and the 5×7 bitmap font (`cabinet/font.py`). The cabinet itself ships no art; its UI is text and rectangles.
- **On-screen control names** come from `context.controls.scheme` (keyboard vs pad labelling, which the operator menu can switch at runtime) and `cabinet/ui/hints.py`. Don't hard-code "ENTER" or "START".
- **Pac-Man** (`games/pacman/`) is a faithful port. `coordinator.py` is the state machine. Event names on the internal bus (`events.py`) were kept verbatim from the JS (`eatGhost`, `dotEaten`, …). Position equality goes through `character_util.approx`. Fractional and out-of-range maze lookups must miss rather than round or wrap, because respawn and the tunnel depend on it. The README's "Fidelity notes" lists the two intentional deviations.

## Data files

`data/pad_mapping.json` is committed on purpose; it's the measured mat. `data/settings.json`, `data/passcode.json` (the score-reset passcode), and score temp files are gitignored. Leaderboard writes are atomic (temp file, fsync, `os.replace`). A missing or corrupt file must degrade to an empty board or default mapping, never to a crash.
