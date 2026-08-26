---
name: new-game
description: Scaffold a new game for the pygame arcade cabinet in python-version/games/ — the Game/GameSpec contract, the eight-action input vocabulary, and the DDR dance-mat design rules a title has to obey to be playable with feet. Use when adding a title to the cabinet, porting a game onto it, or asking what a game may assume about the pad.
---

# Adding a game to the cabinet

The cabinet is a platform. **Installing a title is dropping a folder into
`python-version/games/`** — no shared file is edited, because
[`games/registry.py`](../../../python-version/games/registry.py) finds a game by
scanning rather than by being told. A folder is a game if it is an importable
package whose `game.py` (or `__init__.py`) exposes a `SPEC`.

Read [`cabinet/game.py`](../../../python-version/cabinet/game.py) before writing
code — it is the contract, and it is annotated. This skill is the working
summary plus the part that is not written down there: **what a game may assume
about a dance mat.**

## 1. The folder

```
python-version/games/<id>/
  __init__.py         empty
  game.py             a Game subclass + SPEC = GameSpec(...)
  preview.png         112x124, the picker's still            (optional)
  assets/
    manifest.json     {"sprites": {...}, "audio": {...}}     (optional)
    sprites/
    audio/
```

`<id>` is the folder name, the score file's name and what `--game` takes.
`GameSpec.id` **must** match the folder name — the registry refuses the game if
they disagree, because that would file one game's scores under another's.

Start from [`reference/game_template.py`](reference/game_template.py) — copy it
to `games/<id>/game.py` and fill it in. Everything else defaults to convention:
the preview, sprites and clips are found *beside* the module the factory came
from, so a spec names only `id`, `title`, `factory` in the normal case.

## 2. The Game contract

Every method's default is inert, so override only what the game does.

| Member | When it runs | Notes |
|---|---|---|
| `sim_dt_ms` (class attr) | — | Fixed sim step. Omit for the cabinet default (120Hz) |
| `enter()` | picker → game | Refresh the score readout here |
| `leave()` | game → picker | **Must leave nothing running** — no timers, no looping audio |
| `simulating` (property) | every frame | False on your title screen / while paused → sim time freezes |
| `at_attract` (property) | every frame | True *only* on your title screen with nothing in progress |
| `tick_realtime(frame_ms)` | every frame | Wall-clock bookkeeping (blinking prompts, caret) |
| `update(sim_dt_ms)` | fixed step | One simulation step |
| `render(interp)` | every frame | `interp` = fraction between the last two steps |
| `handle_action(action)` | on input | One of the eight actions below |
| `handle_release(action)` | on input | Only if you have a **held** control |

`at_attract` gates two cabinet behaviours: whether the operator menu may open,
and whether Esc backs out to the picker. It must be **False for the whole of a
run, including the end-of-game sequence** — otherwise the machine can drop the
picker on top of a game that is still finishing.

## 3. Input — eight actions, and what a mat can actually do

The shell resolves every keypress and every mat panel into one of eight actions
and routes it. Modals it owns (name entry, operator menu) get first refusal; a
game never sees a raw pygame event, never learns which physical panel was
pressed, and never has to check whether a modal is open.

```
up  down  left  right   select   delete   pause   mute
```

**On the measured mat, only six of these exist**, and that is a design
constraint on your game, not a detail:

| Action | Mat panel | Safe to build on? |
|---|---|---|
| `up` `down` `left` `right` | the four arrows | Yes — the whole vocabulary |
| `select` | START (and ○) | Yes — start / confirm |
| `pause` | SELECT | Yes — pause during play only |
| `delete` | ✕ | Name entry only; treat as absent in gameplay |
| `mute` | *unbound* | **Never fires.** Sound lives in the operator menu |

### Rules that come out of the hardware

* **Build the game on four directions and START.** Anything a run depends on
  must be reachable from an arrow panel or START. If the game cannot be played
  with those, it cannot be played on the cabinet.
* **Never bind gameplay to `mute`, and do not rely on `delete`.** `□` and `△`
  are the mat's *corners*, sharing an edge with the two arrows either side; a
  foot travelling between ← and ↓ clips the corner between them. They are
  deliberately unbound for exactly that reason. See
  [the shape panels](../../../python-version/README.md#the-shape-panels-do-nothing-during-play).
* **No diagonals, no reliable chords.** Two panels under two feet do not arrive
  together, and the cabinet has no combo detection — an earlier SELECT+START
  gesture was removed because a 250ms combo window put a delay on starting a
  game and was still too tight to hit with two feet.
* **Presses are a step, not a tap.** A player is standing on the mat and
  travelling between panels. Expect a slower, coarser input rate than a
  keyboard, expect stray neighbours, and give a mistimed step a way to recover.
  If timing matters, buffer it: Pac-Man registers a direction pressed slightly
  *before* a junction, and that is a large part of how it feels.
* **The mat's centre is an eleventh sensor and is unbound.** It is the neutral
  spot a player stands on between moves — it fires every few seconds during
  normal play. Nothing may be bound there.
* **A release may be lost.** `handle_release` is delivered only to a running
  game and only while no modal is up; a pad unplugged mid-step or a modal
  opening between press and release swallows one. Treat it as *"not held any
  more"* rather than as an event to count, and clear whatever you track in
  `leave()`.

The keyboard path stays live at all times (WASD/arrows, Enter, Backspace, Esc,
Q), so a game is developed at a desk and only *designed* for the mat.

### Labelling

Don't spell out control names yourself. `context.controls.scheme` is the active
scheme ([`cabinet/controls.py`](../../../python-version/cabinet/controls.py)) —
`scheme.start` is `ENTER` or `START`, `scheme.pause` is `ESC` or `SELECT`, and
`scheme.sound` is `None` under the pad because the mat has no sound control to
name. Use [`cabinet/ui/hints.py`](../../../python-version/cabinet/ui/hints.py)
for the bracketed reminders so a new game reads like the rest of the machine.
Hold the reference — the operator menu can switch scheme while your game is
loaded, and the next frame has to say the new thing.

## 4. What the cabinet lends you — `GameContext`

| Field | What it is |
|---|---|
| `renderer` | Blit layer over the logical surface. `draw_image_at`, `draw_frame`, `fill_rect_at` |
| `assets` | **Your** sprite pack alone — your keys, no collisions |
| `font` | The shared 5×7 bitmap font: `draw(target, text, x, y, color, scale, align)` |
| `sound_manager` | A view of the one mixer that prefixes your clip names |
| `controls` | Active labelling scheme (above) |
| `leaderboard` | **Your** board — `get_top_scores()`, `high_score`, `qualifies(score)` |
| `submit_score(score, on_close=)` | Offers a final score to the shared name-entry modal. Opens only if it places; `on_close` fires either way |
| `exit_to_picker()` | Hand control back to the picker |
| `quit_cabinet()` | Shut down. Deliberately unreachable from a mat panel |
| `show_fps` / `fps` | Cabinet-wide; F1 means the same thing on every screen |

You own your rules, art and audio — privately. Two games may both ship a sprite
called `player` and a clip called `jump`. You own nothing cabinet-wide: no
mixer, no window, no score file location, no mute.

A loop that should keep playing while paused is named as `pause_ambience=` on
the spec, not managed by hand — the mixer restores ambience on unmute and has to
be told which clip is yours.

## 5. The screen

224×296, **portrait**, from
[`cabinet/constants.py`](../../../python-version/cabinet/constants.py). SDL
stretches it to the display. A game lays itself out inside that rather than
changing it, and uses the shared palette (`ARCADE_YELLOW`, `MAZE_BLUE`,
`ARCADE_RED`, …) so titles look like one machine.

Text is the 5×7 font: a cell is 6px wide, which is where the ~32-character
tagline limit comes from (the picker panel is 208 logical px).

## 6. Assets

`assets/manifest.json`, read on first play rather than at boot — an installed
title costs nothing until someone chooses it.

```json
{
  "sprites": {
    "player": { "file": "sprites/player.png",
                "width": 16, "height": 16, "frame_width": 16, "frames": 4 }
  },
  "audio": { "jump": "audio/jump.ogg" }
}
```

OGG for audio, PNG for sprites. `tools/convert_assets.py` is the build-time
SVG→PNG / MP3→OGG step; its output is committed so the Pi never runs it.

The preview is a still image, `preview.png` beside the game, authored at
**112×124** so it blits 1:1 (pixel art survives an integer downscale and very
little else). Anything else is aspect-fitted. A missing file falls back to the
title on a black panel — the picker must still list a game whose art did not
ship.

## 7. Checklist

```bash
cd python-version
.venv/bin/python main.py --list-games          # is it found? is it broken?
.venv/bin/python main.py --windowed --game <id>
.venv/bin/python -m pytest tests/ -q           # test_games.py covers installation
```

- [ ] `SPEC.id` == the folder name
- [ ] Playable with four arrows + START alone
- [ ] Nothing in a run depends on `mute` or `delete`
- [ ] `at_attract` is False for the entire run, end-of-game sequence included
- [ ] `leave()` stops every timer and every looping clip
- [ ] Nothing touches pygame or the display at **import** time — the registry
      imports the module before the display exists
- [ ] Final score offered via `context.submit_score`, score readout refreshed in
      `on_close`
- [ ] Lays out inside 224×296 portrait

A game that will not import is skipped with a line on stdout and named by
`--list-games`; it costs that title rather than the machine. Keep it that way —
a cabinet has no keyboard and cannot be recovered from a traceback at boot.
