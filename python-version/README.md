# Arcade cabinet — pygame

A native Python + pygame arcade **platform** built to run on a Raspberry Pi 4B+
without Chromium. It boots into a game picker. One title is installed:

| Game | What it is |
|---|---|
| **PAC-MAN** | A port of the React/Vite version in [`../node-version/`](../node-version/) |

Every game gets the same things from the machine: the screen, the 5×7 font, the
mixer, the dance mat, the on-screen control labelling, **its own high-score
table with its own reset**, the name-entry modal and the operator menu. What it
owns privately is its rules, its art and its audio — a sprite pack and a clip
namespace of its own, so two games cannot collide.

**Adding a title is dropping a folder into `games/`**; no shared file is edited,
and a game that will not import costs that one title rather than the machine.
See [Adding a game](#adding-a-game).

Pac-Man's gameplay is a direct port of [`../node-version/src/game/engine.js`](../node-version/src/game/engine.js) —
same ghost AI, same speeds, same timings, same scoring. Every constant is
annotated with the `engine.js` line it came from so the two can be diffed.

## Quick start

```bash
cd python-version
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python main.py                    # fullscreen, opens on the picker
.venv/bin/python main.py --windowed         # windowed, 3x (desktop testing)
.venv/bin/python main.py --game pacman      # skip the picker, boot into one game
```

The only runtime dependency is `pygame-ce`. There is no Node, npm, pnpm, or
`node_modules` anywhere in the runtime path, and no network access is needed.

### Options

| Flag | Effect |
|---|---|
| `--windowed` | Run in a window instead of fullscreen |
| `--scale N` | Integer upscale for `--windowed` (default 3) |
| `--fps` | Show the FPS counter from the start (also `F1` in game) |
| `--no-sound` | Disable audio entirely |
| `--audio-buffer N` | Mixer buffer size (default 512; raise to 1024 if audio underruns) |
| `--game ID` | Boot straight into one game instead of the picker. Also the game `--data-file` and `--reset` act on (default `pacman`) |
| `--list-games` | List installed games and their score files, then exit |
| `--data-file PATH` | High-score JSON for the game named by `--game` |
| `--pad-mapping PATH` | Gamepad / dance-pad binding table (default `data/pad_mapping.json`) |
| `--reset` | Clear one game's high scores and exit (equivalent to `npm run reset`) |
| `--reset-all` | Clear every installed game's high scores and exit |

## The game picker

The first screen. A list of titles on the left, a **preview** of the highlighted
one on the right, and that game's top three underneath — so every board on the
machine is readable from the front of the cabinet without starting anything.

Up and down move, **Enter** (or **START** on the mat) plays. From a game's own
title screen, **Esc** comes back here; on the mat there is no spare panel for
that, so the route back is **CHANGE GAME** in
[the operator menu](#the-operator-menu-select). On the picker itself, Esc quits.

The preview is a **still image file** — `games/<id>/preview.png`, found beside
the game unless `GameSpec.preview_image` names somewhere else. PNG or JPEG,
either works. It is loaded on first sight
and scaled to the panel once, so an idle cabinet parked on this screen costs one
blit a frame. Nothing on the picker animates.

Author it at **112×124**, the panel's exact inner size, and it is blitted 1:1
with no resampling — pixel art survives an integer downscale and very little
else. Anything else is aspect-fitted and centred. A missing or unreadable file
falls back to the game's name on a black panel: the picker must still list a
game whose art did not ship.

Pac-Man's preview is generated rather than hand-drawn, because it is assembled
from art the game already owns — a second copy of the board would be one more
thing to keep in step. Note that a preview is a *composed scene*, not a
screenshot; Pac-Man's happens to be its whole maze at half scale.

```bash
.venv/bin/python tools/make_preview.py                # every game
.venv/bin/python tools/make_preview.py --game pacman
```

The output is committed, like everything under a game's `assets/`, so the Pi never runs
it. Re-run it if the art changes.

## Controls

| Input | Action |
|---|---|
| **WASD** / **arrow keys** | Move (also the picker's list and the name-entry keyboard) |
| **Enter** | Play the highlighted game / start a game / select a key during name entry |
| **Backspace** | Delete a character during name entry |
| **Esc** | Pause during play — back to the picker from a game's title screen — **quit** from the picker |
| **Q** | Toggle sound |
| **F1** | Toggle the FPS counter |
| **F10** / **Ctrl-Q** | Quit from anywhere |
| **Ctrl-R** | Open the operator menu from any title screen (see below) |

Turn buffering is preserved: a direction pressed slightly *before* a junction
still registers when you reach it. It is a large part of how the controls feel.

The pause and sound controls are named on screen **during play** — in the gap
between the score row and the maze, and again on the pause overlay — so nothing
has to be memorised from the title screen:

```
PAUSE = [ESC]   🔈 = [Q]
```

The control is bracketed, and drawn rather than named wherever the mat has a
shape printed on it. The speaker has no accompanying word: it is both the label
and the state, **struck through in red when sound is off**, which is the game's
only visible report of mute. Which controls are named depends on the selected
controller scheme; see the operator menu below.

Under the pad scheme the line is `PAUSE = [SELECT]   🔈`. The mat has no sound
control to name — see [the shape panels](#the-shape-panels-do-nothing-during-play)
— so the speaker loses its bracket and stays on as a pure status light, still
struck through when muted. Audio is switched from
[the operator menu](#sound--audio-on-and-off) under that scheme.

### Dance pad / gamepad / arcade encoder

A USB pad is picked up automatically, including one plugged in *after* launch.
Everything it can do is expressed as **direction + select + delete + pause +
mute**, so a DDR mat, a gamepad and an arcade encoder all use the same code
path. Panels also report when they are **let go** — a game with a held control
needs that, and on a mat that is a foot resting on a panel. `mute` is left unbound on the measured mat — see [the shape
panels](#the-shape-panels-do-nothing-during-play); it lives in
[the operator menu](#sound--audio-on-and-off) instead — but a gamepad, which has
thumb buttons rather than panels underfoot, can safely bind it.

No single panel press can quit, pause the cabinet permanently, or touch the
leaderboard — the destructive things live behind the operator menu below.

#### The operator menu (SELECT)

A cabinet has no keyboard, so turning the sound off, clearing a board or shutting
the machine down used to mean SSHing into the Pi. Press **SELECT on any title
screen** — the picker, or a game's own — and a short list appears:

| Option | Effect |
|---|---|
| **SOUND  ON** / **SOUND  OFF** | Turns audio on and off |
| **CHANGE GAME** | Back to the picker. Only shown over a game |
| **CONTROLLER** | Switches the on-screen hints between keyboard and mat |
| **RESET SCORES** | Wipes **one game's** board — gated behind a passcode, below |
| **EXIT GAME** | Closes the cabinet |
| **CANCEL** | Backs out |

Navigate with the **up/down arrow panels** and choose with **SELECT**. It is only
reachable from a title screen, so it can never interrupt a run, and it closes
itself after 20 seconds of inactivity.

Rows that could not do anything are left out rather than shown dead: SOUND when
there is no mixer, CHANGE GAME when the picker is already what is behind the
menu.

##### SOUND — audio on and off

This is where the mat's sound control lives, because there is no panel it can
safely sit on — see [the shape panels](#the-shape-panels-do-nothing-during-play).
A menu you can only open while standing still cannot be stepped on by accident.

The row **is** the readout: it reads `SOUND  ON` or `SOUND  OFF`, and choosing it
flips it in place. Unlike every other row the menu stays open, so the label
changing under the cursor is the confirmation and one more press is the way back
if a foot landed wrong. It leads the list because it is the only row anyone
touches routinely and the only one a mis-press cannot cost anything.

The setting is written to `data/settings.json` — the same `volume` key the `Q`
key has always used — so it survives a restart. `Q` still works on a keyboard,
and the two stay in step.

##### CONTROLLER — labelling for the mat

The hints were written for a keyboard — PRESS ENTER, PAUSE = [ESC] — none of
which means anything to someone standing on a dance mat. Choose **DDR PAD** and
they become the panel names instead:

| Screen | Keyboard | DDR pad |
|---|---|---|
| Game picker | ENTER PLAYS   🔈 = [Q] | SELECT PLAYS   🔈 |
| Title screen button | PRESS ENTER | PRESS START |
| Title screen hint | ESC = GAMES<br>PAUSE = [ESC]   🔈 = [Q] | PAUSE = [SELECT]   🔈 |
| **In game** (below the score) | PAUSE = [ESC]   🔈 = [Q] | PAUSE = [SELECT]   🔈 |
| **Pause overlay** | RESUME = [ESC]   🔈 = [Q] | RESUME = [SELECT]   🔈 |
| Name entry | ARROWS MOVE  ENTER PICK | ARROWS MOVE  START PICK |
| This menu | ENTER PICKS / ESC CANCELS | SELECT PICKS / SELECT CANCELS |

This is **labelling only** — both input paths stay live under either scheme, so a
wrong choice can never lock anyone out of a machine with no keyboard. The worst
case is misleading text. The cursor opens on whichever scheme is active, so
pressing SELECT straight away is a no-op exit.

The choice is saved in `data/settings.json` and survives a restart. Note that
under the pad scheme, PAUSE is listed as SELECT: on a title screen that panel
opens this operator menu instead, but during play it does pause. The pad rows
show a bare speaker because the mat has no sound control to name — it still
reports whether sound is on, and SOUND above is how you change it.

The pad scheme also drops `ESC = GAMES` from a game's title screen rather than
naming a panel that does not exist: the mat's route back to the picker is
[CHANGE GAME](#the-operator-menu-select).

##### RESET SCORES

**This clears one game's board, not the machine's.** Every game keeps its own top
three, so the board this resets is whichever game the menu was opened over — the
running game's, or the highlighted game's on the picker. The game is named in
yellow under the heading, because "RESET HIGH SCORES" on a machine with several
boards would otherwise be ambiguous at exactly the moment it must not be.

Choosing RESET SCORES asks for a **passcode** entered on the four shape panels,
then **START** to confirm. SELECT backs out at any point, and nothing is written
until START is pressed.

Entry is masked — the slots fill in but never show which panel was pressed — and
nothing is checked until START. A wrong panel is accepted silently and the whole
sequence is compared at the end, which matters: rejecting each press as it came
would leak the code one position at a time, turning a search over every sequence
into four guesses per slot.

##### Setting your own passcode

The built-in default is in `cabinet/ui/system_menu.py`, so it is public — anyone
who can read this repository knows it. To set a real one, create
`data/passcode.json` (gitignored, so it never leaves the Pi):

```json
{ "code": ["circle", "cross", "cross", "triangle", "square"] }
```

Any 3–10 panels from `cross`, `square`, `triangle`, `circle`, repeats allowed.
A missing or unparseable file falls back to the default rather than locking you
out. The file is read once at launch, so restart the game after editing it.

Two details worth knowing if you change this:

* The trigger and the code are read as **physical panels**, not as the eight
  actions the rest of the game uses. `✕` and `○` are still aliased to
  delete/select, so reading actions instead would submit and erase letters while
  the code was being entered — and `□` and `△` would resolve to nothing at all,
  since they drive no action any more. The panel table is `panels` in
  `data/pad_mapping.json`, defaulting to the layout below; it is independent of
  `bindings`, which is why all four shapes still work as code panels.
* SELECT is free to take here because it drives the **`pause`** action, and
  there is nothing to pause on the main menu. Everywhere else it still pauses.
  Note this is *not* the `select` action — that one is driven by START and the
  circle panel, and starts a game. The two vocabularies genuinely disagree about
  the word, which is why panels exist at all.

  An earlier version opened this with SELECT+START together. That needed both
  panels' actions held back for 250ms to see whether a combo was forming, which
  put a delay on starting a game and was too tight a window to hit reliably with
  two feet on a mat. One panel needs none of that.

Without a pad, **Ctrl-R** opens the same menu; inside it the arrow keys
navigate, **X / S / T / C** stand in for cross / square / triangle / circle,
**Enter** for SELECT and START, and **Esc** closes.

#### Calibrating a pad

Pads disagree about which button index is which control, and two mats of the
same model can disagree with each other. So the binding table is data, not code:
it lives in `data/pad_mapping.json` and is written by stepping on each panel.

**On the Pi, with the pad plugged in:**

```bash
.venv/bin/python tools/pad_report.py                 # walk all 11 panels, write a report
.venv/bin/python tools/gamepad_test.py --list        # what SDL can see
.venv/bin/python tools/gamepad_test.py               # live event monitor
.venv/bin/python tools/gamepad_test.py --calibrate   # step on each panel
```

[`tools/pad_report.py`](tools/pad_report.py) is the one to reach for first when
a pad misbehaves. It walks all eleven panels — the ten labelled ones plus the
centre — one at a time, **waiting for ENTER between each** rather than racing
ahead, so there is time to read what a panel recorded; `r` re-records it if the
step did not land. `q` stops early and still writes everything reached;
`--auto` advances unattended.

| At the prompt | |
|---|---|
| `ENTER` | next panel |
| `r` | re-record the panel just done (the old log is kept, marked superseded) |
| `q` | stop here and write the report |

It logs **every raw event** each panel produced with timestamps, and writes
`pad-report.txt` — which is shareable, and shows the things a finished mapping
hides: a panel that bounces and sends one
press three times, a panel that reports on both a hat and an axis, a switch that
latches instead of releasing, and an axis sitting at full deflection while
untouched. It writes a working `data/pad_mapping.json` as it goes, so a clean
run leaves nothing else to do. It imports nothing from `cabinet/` or `games/`, so it can be
copied to a Pi on its own; it needs only pygame.

`gamepad_test.py --calibrate` is the shorter path: it prompts for the eight
controls the game actually uses rather than all ten panels, and writes the same
mapping file without the raw log. For a DDR mat the prompts map to:

| Prompt | Panel | In-game |
|---|---|---|
| up / down / left / right | the four arrows | Move; navigate the name-entry keyboard |
| select | **START** | Start a game; confirm a letter |
| delete | **X** | Delete a letter during name entry |
| pause | **SELECT** | Pause during play |
| mute | *skip it* | Nothing — see below |

Skip the `mute` prompt on a mat. Binding it to a shape panel is what the
committed mapping used to do, and it is the mistake described under [the shape
panels](#the-shape-panels-do-nothing-during-play); binding it to an arrow would
mute the game every time you moved.

It leaves `○`, `△` and the centre unbound — `pad_report.py` is the one that
covers every panel. Press ESC (or wait) at any prompt to skip it. Either way, an action
takes a *list*, so a second button can be added by hand:

```json
{
  "version": 1,
  "device": null,
  "deadzone": 0.5,
  "bindings": {
    "up":     [{ "type": "button", "button": 2 }],
    "select": [{ "type": "button", "button": 9 },
               { "type": "button", "button": 7 }]
  }
}
```

Four binding forms are understood — `button`, `hat`, `axis`, and `key` (for
mats that enumerate as an HID *keyboard* rather than a gamepad). Some mats
report one arrow on **both** a hat and an axis; both tools record both, which is
correct and not a bug.

The file is worth committing once it works — it survives a re-clone onto the Pi.

#### The measured mat

`data/pad_mapping.json` is committed, and the built-in default matches it, so
the cabinet's mat works with no setup. It is a **DragonRise / Microntek
PSX-to-USB board** (USB `0079:0006`, `Name="Microntek USB Joystick"`) wired to a
10-panel mat, and it reports **every panel as a plain button**:

| Button | Panel | Action |
|---|---|---|
| 0 | ← arrow | left |
| 1 | ↓ arrow | down |
| 2 | ↑ arrow | up |
| 3 | → arrow | right |
| 4 | □ | *unbound* |
| 5 | △ | *unbound* |
| 6 | ✕ | delete |
| 7 | ○ | select |
| 8 | SELECT | pause |
| 9 | START | select |

Buttons 10 and 11 exist on the board but nothing on the mat is wired to them.

##### The shape panels do nothing during play

`□` and `△` are deliberately unbound, and `✕` and `○` drive actions that are
no-ops outside the name-entry modal and the main menu. **Nothing that acts
during a run is bound to a shape panel.**

The four shapes are the mat's *corners*, and a corner shares an edge with the
two arrows either side of it. A foot travelling between ← and ↓ clips the corner
between them, so anything bound there fires by accident mid-run. `△` used to be
a second `pause` binding and `□` used to be `mute`, both carried over from the
gamepad layout this table started as, where the shapes are thumb buttons that
nothing else is near.

The pause case read as *random* rather than as a stuck panel, because two things
hid the cause: pause is refused while the READY! text is up, so an early clip
does nothing at all, and the on-screen hint only ever named SELECT. SELECT and
START are edge panels — reaching them takes a deliberate step off the arrows —
so they keep their actions.

The cost is that **the mat has no sound panel**. Audio moved into the operator
menu instead — [SOUND](#sound--audio-on-and-off), the first row — which is
reachable from the mat with no keyboard and only from the main menu, so it cannot
be stepped on mid-run. The pad hint stops *naming* a sound control to match, but
keeps the speaker as a state light.

All four shapes still work as operator-menu passcode panels, which read the
separate `panels` table and are only reachable from the main menu.

**The centre of the mat is an eleventh sensor**, and it is deliberately left
unbound. It does not report as a button — stepping on it sends `axis 1 +1.0`,
and stepping off returns the axis to `0`. That is the neutral spot the player
stands on between moves, so it fires every few seconds during normal play;
anything bound to it would pause, mute or turn constantly. `pad_report.py` walks
it last, calls it out in the summary, and refuses to put that control in a
generated mapping even if another panel also reports it.

Three things about this are worth knowing, because none is what a gamepad
would do:

- **The arrows are buttons, not the hat.** The descriptor advertises a hat and
  four axes, but a PSX controller's d-pad and sticks have nothing soldered to
  them on a mat. On a PlayStation dance pad the arrow panels *are* the face
  buttons, and the corner shape panels take the shoulder indices — which is
  exactly the order above.
- **Nothing is bound to an axis.** Between the centre sensor sitting on axis 1
  and this board's habit of parking unused analogue axes at full deflection,
  an axis binding is a liability here — `axis 1 +` is precisely what a naive
  `down` binding would have picked, and it would have driven Pac-Man downward
  every time the player stood still. Hat bindings are kept so an ordinary
  gamepad or arcade encoder still works; axis bindings are not.
  [`tests/test_gamepad.py`](tests/test_gamepad.py) pins this.

A different mat will differ — calibrating replaces all of this. To confirm the
numbering independently of pygame:

```bash
sudo apt install joystick
jstest /dev/input/js0        # step on each panel and watch which index moves
```

#### When the Pi cannot see the pad at all

If `--list` prints *no devices*, the problem is below SDL. In order:

```bash
lsusb                        # is the mat enumerating at all?
ls -l /dev/input/js* /dev/input/event*
groups                       # your user must be in `input`
sudo usermod -aG input $USER # then log out and back in
sudo apt install evtest && sudo evtest    # does the kernel see the panels?
```

`cat /proc/bus/input/devices` is the quickest single check — a working mat shows
`Handlers=event5 js0` (a joystick node) and an `ABS=` line listing its axes.

Three failure modes are worth knowing:

- **`evtest` shows key presses, not joystick axes.** Some mats are HID
  keyboards — `/proc/bus/input/devices` shows no `js*` handler for them. Run
  `--calibrate` on the Pi's own screen (not over SSH — key events need a
  focused window) and it records `key` bindings instead.
- **`lsusb` shows nothing.** These mats draw little power but are fussy about
  cabling. Try the USB 2.0 ports, and a powered hub before suspecting the mat.
- **Pac-Man drifts one direction on its own.** A PSX adapter with no analogue
  stick attached can park an axis at full deflection instead of centre. Delete
  the `axis` entries from the four directions in `pad_mapping.json`. The
  committed mapping has none for exactly this reason; `pad_report.py` flags a
  stuck axis in its RESTING STATE section and leaves it out of what it
  generates.

Over SSH the tool falls back to SDL's dummy video driver, so joystick
calibration works headless; only keyboard-HID detection needs a real screen.

## Display

The game renders to a **fixed 224×296 logical surface** (28 tiles wide by 37
tall at 8px per tile) and lets `pygame.SCALED` stretch that to the display,
letterboxing as needed. That means:

- Assets rasterize 1:1 from the source SVGs — the art is authored at 8px/tile.
- Every sub-tile offset stays on a whole pixel (dots sit at 3/8 of a tile).
- There is no per-frame scaling blit in fullscreen, and no resize logic.

The 37-tile height is the *whole* UI column — score row (3), gap (1), maze (31),
lives/fruit row (2). Budgeting only the maze picks a scale ~18% too large and
clips the score and lives rows, which is a bug the reference had and fixed.

## Sound

The game prints its audio state at startup, and `run-game.sh` tees that to
`run-game.log`, so a silent cabinet leaves evidence:

```
audio: driver=alsa mixer=(44100, -16, 2)
audio: volume=1, 1 game(s) installed
pacman: 68 sprites, 14/14 clips
```

The first two lines are printed at startup; the third when a game is first
chosen, since a game's art and audio are loaded then rather than at boot. Read
them in that order — each rules something out:

| What you see | What it means |
|---|---|
| `audio: OFF (...)` | The mixer never opened. The reason is in the brackets. |
| `0/14 clips` | The mixer opened but no audio decoded — check `games/<id>/assets/audio/`. |
| `0/0 clips` or `0 sprites` | That game's `manifest.json` lists nothing, or would not parse. |
| `volume=0` | **The game is muted.** SOUND in the operator menu, or `Q`. |
| Looks correct, still silent | Routing — the sound is going somewhere that is not the TV. |

### Before any of the above: does the Pi play *anything*?

```bash
speaker-test -t wav -c 2 -l 1        # Ctrl-C to stop
```

Or just play a YouTube video. **If nothing plays either, the game is not
involved** — the Pi is pointed at the wrong output. That has been the answer
every time so far: the Pi was set to the **AV / 3.5mm jack** rather than
**HDMI**, so all audio was arriving at a socket with nothing plugged into it.
Right-click the speaker icon on the taskbar (or `raspi-config` → System Options
→ Audio, or `wpctl status`) and select the HDMI sink.

This check costs ten seconds and is worth doing *first*, because the game's own
diagnostics cannot see it: from SDL's side a disconnected jack and a TV are
indistinguishable, so the log reports a perfectly healthy audio stack while the
room stays quiet. That is exactly why the table above bottoms out at "routing"
rather than naming a cause — and why "everything else works fine" is worth
confirming rather than assuming, since it is the assumption that decides whether
to debug the game at all.

Only once the Pi itself is audible is it worth suspecting SDL. SDL picks its own
audio driver, and it need not be the one the desktop uses: with system audio
going out over HDMI through PipeWire, SDL can still choose raw ALSA — and raw
ALSA is the headphone jack again. Nothing errors either way.

To find a driver that reaches the TV:

```bash
python tools/audio_check.py
```

It walks every driver SDL was built with, reports which open and what devices
they see, and plays a real clip through each so you can hear which one comes out
of the TV. Then launch with whichever worked:

```bash
./run-game.sh --audio-driver pulseaudio
```

To make it stick, add that flag to the `Exec=` line in `~/Desktop/pacman.desktop`
(and in `~/.local/share/applications/pacman.desktop`), or export
`SDL_AUDIODRIVER` near the top of `run-game.sh`. `--audio-device` forces a
specific output by name if a driver sees several.

If **no** driver produces sound, the game is not the problem — check the desktop
mixer's output device, and `wpctl status` on Bookworm.

## Assets

**Assets belong to a game, not to the machine.** Each one keeps its sprites and
clips in `games/<id>/assets/`, described by a `manifest.json` beside them, and
they are loaded into a pack of that game's own the first time it is played.
Sprite keys and clip names are therefore scoped: a second game may have its own
`player` and its own `jump` without renaming Pac-Man's, and a game that is
installed but never chosen costs nothing at boot. The only thing under the
top-level `assets/` is the desktop shortcut's icon.

Pac-Man's pack is generated and committed. The Pi loads PNG and OGG only — it
needs neither `cairosvg` nor `ffmpeg`.

To regenerate after changing the source art (run on a desktop, not the Pi):

```bash
.venv/bin/pip install -r requirements-dev.txt
brew install ffmpeg
.venv/bin/python tools/convert_assets.py
```

This rasterizes 68 sprites from the reference's ~50 SVGs at their exact final
pixel size, transcodes 14 MP3s to Ogg Vorbis, and writes
`games/pacman/assets/manifest.json` (frame counts and dimensions). Total:
~760 KB. It converts *this* game's art; another game brings its own however it
likes, so long as it ends as a manifest and files beside it.

Ogg Vorbis rather than MP3 because SDL_mixer decodes Vorbis with a bundled
stb_vorbis on every build, so it cannot break on the Pi the way MP3 can — and
because Vorbis stores an exact sample count, so the short ambience loops
(`siren_1` is 0.39s and loops continuously) have no encoder padding to click on.
The script prefers `libvorbis` and falls back to ffmpeg's native `vorbis`
encoder, which is what Homebrew's build ships.

The UI font is a built-in 5×7 bitmap font in [`cabinet/font.py`](cabinet/font.py).
The web version used 'Press Start 2P' from Google Fonts, which is unavailable
offline — and at 8 logical pixels tall no outline font would be legible anyway.

## Architecture

The top-level split is **the machine** and **the games on it**. Everything
cabinet-wide lives in `cabinet/`; a game owns only its own rules and art. Inside
`games/pacman/`, module boundaries still mirror the JS class boundaries, which
makes cross-checking against the reference straightforward.

```
main.py                    boot: args, audio, window — then hands over
cabinet/
  app.py                   the shell: two screens, the modals, the frame loop
  game.py                  the Game / GameSpec / GameContext contract
  constants.py             screen, palette, loop rates, high-score limits
  engine.py                the fixed-timestep loop
  gamepad.py               pad bindings -> actions (dance mat, gamepad, encoder)
  controls.py              on-screen labelling: keyboard vs mat
  renderer.py              blit layer + one sprite pack per game
  font.py                  5x7 bitmap font
  sound.py                 one mixer, one clip namespace per game
  settings.py              data/settings.json (volume, controller)
  leaderboard.py           JSON high scores — one board per game
  ui/game_select.py        the picker: list, preview image, that game's scores
  ui/score_entry.py        name entry, shared by every game
  ui/system_menu.py        the SELECT operator menu
  ui/hints.py              the bracketed control reminders
games/
  registry.py              finds every installed game by scanning this folder
  pacman/
    game.py                the seam: Game subclass + GameSpec
    preview.png            the picker's still (tools/make_preview.py)
    assets/                this game's own sprites, clips and manifest
    constants.py           every literal, annotated with engine.js line numbers
    coordinator.py         GameCoordinator — the game state machine
    character_util.py      grid math, snap_to_grid, turning, tunnel warp
    characters/pacman.py   Pacman
    characters/ghost.py    Ghost (all four, name-parameterized)
    maze.py                maze array, tile queries, integrity assertions
    pickup.py              pacdot | powerPellet | fruit
    timers.py              pausable timers driven by simulation time
    ui/{menu,hud}.py       title screen, score row / lives / pause overlay
assets/icon.png            the desktop shortcut's icon — the cabinet's own
tools/convert_assets.py    build-time SVG->PNG, MP3->OGG (into games/pacman/)
tools/make_preview.py      build-time picker art
tools/gamepad_test.py      pad identification + calibration
tools/pad_report.py        per-panel raw event log (standalone; pygame only)
tests/                     496 tests
```

**The machine holds no art of its own.** Every screen the cabinet draws — the
picker, the name-entry modal, the operator menu — is text and rectangles, so
`assets/` contains only the desktop icon. Sprites and clips belong to a game and
live under `games/<id>/assets/`, which is what makes a second game's art
incapable of colliding with a first game's.

**Input funnels through one place.** Pygame events become the eight actions the
whole machine speaks — four directions plus `select`, `delete`, `pause`,
`mute` — and `Cabinet._handle_action` decides who gets them: a modal if one is
up, otherwise the current screen. That is the only routing table, so a game
cannot be reached by a keypress meant for a dialog and never has to check
whether one is open. The mat is resolved ahead of that, because the operator
menu is driven by *physical panels* rather than by actions — see
[the shape panels](#the-shape-panels-do-nothing-during-play).

**Releases are the one asymmetry.** Nothing the cabinet draws has a held
control — a menu cares when a panel goes down, never when it comes up — so a
let-go action skips the routing table entirely and goes only to a running game,
and is dropped while a modal is up. A game that wants it overrides
`Game.handle_release` — a crouch held down is the shape of thing it exists for.
Because a release can be lost (a modal opening between press and release, a pad
unplugged mid-step), a game must treat it as *"not held any more"* rather than
as an event to count.

The browser's `window.dispatchEvent` messaging is replaced by a small internal
bus ([`games/pacman/events.py`](games/pacman/events.py)), but the event **names**
are kept verbatim (`eatGhost`, `restoreGhost`, `dotEaten`, …) so grepping finds
the same call sites in both codebases.

### Adding a game

**Drop a folder into `games/`.** Nothing shared is edited, so nothing shared can
be forgotten — [`games/registry.py`](games/registry.py) finds a game by looking,
not by being told:

```
games/runner/
  __init__.py
  game.py          a Game subclass, and SPEC = GameSpec(...)
  preview.png      112x124, the picker's still            (optional)
  assets/
    manifest.json  {"sprites": {...}, "audio": {...}}     (optional)
    sprites/
    audio/
```

A directory here is a game if it is an importable package whose `game.py` — or
its `__init__.py`, for a single-file title — exposes a `SPEC`. Everything else
is convention: the preview, the art and the clips are found *beside* the module
the factory came from, so a spec that names nothing but the essentials is the
normal case.

```python
class RunnerGame(Game):
    def render(self, interp):
        self.context.renderer.draw_image_at('player', 20, 40)

SPEC = GameSpec(id='runner', title='RUNNER', tagline='RUN', factory=RunnerGame)
```

The [`Game`](cabinet/game.py) methods are `enter`, `leave`, `update`, `render`,
`handle_action`, `simulating`, `at_attract`, and `handle_release` if it has a
held control. The defaults are inert, so override only what the game does. The
id must match the folder name: it is also the score file's name and what
`--game` takes, and letting the two disagree would file one game's scores under
another's.

The picker, the per-game score file, the name-entry modal and the operator
menu's reset all key off the spec. A game is handed a `GameContext` carrying the
shared services and three hooks — `submit_score`, `exit_to_picker`,
`quit_cabinet` — and is never responsible for anything cabinet-wide, which is
what keeps two games from disagreeing about it.

**A game owns its art and audio, and owns them privately.** `context.assets` is
that game's pack alone and `context.sound_manager` is a view that prefixes its
clip names, so two games may both ship a sprite called `player` and a clip
called `jump` without knowing about each other. Both are read from disk when the
game is first played rather than at boot, so installing a title costs nothing
until someone chooses it — which is what makes the number of games unbounded in
practice and not just on paper.

Audio still lands in the machine's **one** clip table under that prefix, so a
single master volume and a single mute cover everything; a game holding a mixer
of its own would be a second thing the operator menu had to know how to
silence. A game with a loop that should keep playing while paused names it as
`pause_ambience=` on its spec.

**A broken game costs one title, not the machine.** A folder that will not
import is skipped with a line on stdout (`run-game.sh` tees the log) and named
by `--list-games`; the rest of the cabinet boots and plays as usual. That
matters because a cabinet has no keyboard and cannot be recovered from a
traceback at startup.

Games are listed alphabetically by title — the only order that stays stable as
folders come and go — unless a spec sets `order=`, which pins it to the front.
Pac-Man sets `order=0`.

`cabinet/constants.py` holds the screen (224×296, portrait), the palette and the
loop rates. A game lays itself out inside that rather than changing it; Pac-Man
asserts the two still agree.

### The one thing not to change: the 120Hz simulation rate

The simulation runs at a fixed **120 steps/second**, rendering at **60**. They
are not fused, and **the simulation rate must not be lowered.**

The ghost-house handoff matches positions inside windows only 0.2 tiles wide
(`Ghost.entering_ghost_house` / `entered_ghost_house`). An eaten ghost travels
at `pacman_speed * 2`; at 120Hz it steps ~0.183 tiles and lands inside the
window, but at 60Hz it steps ~0.367 tiles and jumps clean over it — after which
the ghost circles the maze forever and never respawns.

[`tests/test_ghost_house.py`](tests/test_ghost_house.py) pins this down: an
eaten ghost must respawn from all four corners, and there is a deliberate test
asserting that a 60Hz timestep *breaks* it. If that test ever starts passing,
the windows have been widened and the constraint can be revisited — until then,
a passing 60Hz test would mean the respawn tests had stopped proving anything.

Related: every position comparison the reference wrote as `position.x === 13.5`
goes through a tolerance helper (`character_util.approx`), so float drift cannot
break respawn. The tolerance is six orders of magnitude below the distance
covered in one step, so it can never merge two genuinely distinct positions.

## Fidelity notes

Ported faithfully even where it differs from the 1980 arcade game:

- `get_position_in_front_of_pacman` offsets a single axis and does **not**
  reproduce the arcade's "Pinky up-target overflow" bug.
- Cruise Elroy survives a death (a plain `reset()` preserves `default_speed`);
  only a level advance or a new game clears it.
- Blinky chases Pacman even during scatter once Elroy is active, and cannot be
  turned around by a mode change.
- Fractional grid lookups deliberately miss (`maze_array[11][13.5]` is
  `undefined` in JS). That is what carries an eaten ghost down into the house,
  so `get_tile` rejects non-integer indices rather than rounding them.
- Out-of-range lookups must read as "not a wall" — a negative Python index
  would wrap to the far side of the row and seal the tunnel shut.
- Text overlays draw *beneath* the characters, matching the reference's order.

### Deliberate deviations

Two, both marked in the code:

1. **New games start at level-1 ghost speeds.** `Ghost.reset` derives speeds
   from the ghost's own `level`, which the reference only ever assigned in
   `resetBoardForNextLevel` (engine.js:2288) — so starting a new game after
   reaching level 5 left the ghosts on level-5 speeds, making level 1 silently
   harder the further the previous run went. One line in
   `GameCoordinator.reset` fixes it; move it back below `reset(True)` to
   restore the original behaviour.
2. **The pause debounce is wall-clock, not a simulation timer.** The reference
   used a bare `setTimeout` here rather than its pausable `Timer`
   (engine.js:1994). Since pausing freezes the simulation in this port, a
   simulation timer would freeze the debounce too and the game could never be
   un-paused.

Dropped as web-only: React/Vite/CSS, the HTTP leaderboard API, asset preloading
and its loading bar, the on-screen d-pad and all touch handling, and
`determineScale`'s viewport/resize logic. The FPS counter was kept as a debug
toggle.

The pause blur uses a downscale/upscale pass instead of CSS `filter: blur(5px)`.

## High scores

**One board per game.** Every game gets its own file, its own top three and its
own reset, and no game can see another's. Pac-Man keeps `data/data.json`;
anything added later gets `data/scores/<id>.json`. `--list-games` prints the
mapping.

Files are read and written directly — no server:

```json
{ "scores": [{ "name": "RYAN", "score": 4200 }] }
```

Pac-Man's format is byte-for-byte compatible with the Node version, which is why
its board was left where it was — the two can share one file:

```bash
.venv/bin/python main.py --game pacman --data-file ../node-version/data/data.json
```

Rules match `../node-version/server/leaderboard.js` exactly: top 3, 12-character
names, ties keep the incumbent ahead of the newcomer, blank names become `AAA`,
and a missing **or corrupt** file is an empty board rather than an error — the
machine must always be playable.

Clearing a board is either `--reset` (one game, `--game` picks it), `--reset-all`
(every game), or [RESET SCORES](#reset-scores) on the cabinet itself.

Writes go to a temp file and are then renamed (`os.replace`, atomic on POSIX)
and fsynced first, so a crash mid-write cannot leave a half-written
`data.json`. This matters more on a Pi, where pulling the power is the normal
way to turn the machine off.

## Testing

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/ -q
```

469 tests, all headless — no display and no audio device required. Coverage is
aimed at what is easy to break and hard to spot: ghost-house respawn at 120Hz
from all four corners, ghost targeting per ghost per mode (including Inky's
mirror math and Clyde's 8-tile flip), the scared-mode distance inversion, the
speed formulas across levels, dot thresholds firing fruit (174/74) and Elroy
(40/20) exactly once, the power-duration and idle-release clamps, timer
pause/resume precedence, maze integrity, the leaderboard's corrupt-file and
atomic-write behaviour, and pad binding resolution (a corrupt mapping file must
degrade to the default, never strand a cabinet whose only input is a mat).

The game loop and rendering are verified by playing, not by unit tests.

## Raspberry Pi deployment

**Not yet validated on hardware** — this was built and tested on macOS. §12
phase 12 of the build instructions is still open. Measured here for reference:

- Peak RSS over 30s of gameplay: **~41 MB** (target was well under 150 MB)
- Exactly 2 simulation steps per rendered frame, i.e. a true 120Hz/60fps split
- Sprite and font caches are bounded and stop growing after a few seconds

On the Pi:

```bash
sudo apt install python3-venv
python3 -m venv .venv
.venv/bin/pip install pygame-ce        # prefer this over apt's python3-pygame,
                                       # which may be an old version
.venv/bin/python main.py --fps
```

Check the FPS counter holds 60 and confirm SDL picked up hardware acceleration.
If audio underruns, raise `--audio-buffer` to 1024 before changing anything
else. If 120Hz simulation will not hold, **do not lower it** — widen the
ghost-house windows into zone tests instead, and update
`tests/test_ghost_house.py` to match.

Kiosk-mode autostart is not included; it was left until after hardware
validation.
