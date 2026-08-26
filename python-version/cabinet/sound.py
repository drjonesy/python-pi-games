"""Audio playback (engine.js:3142).

The reference decoded every clip into a Web Audio buffer up front so nothing
decoded mid-game; `pygame.mixer.Sound` does the same thing by construction.

**One mixer for the machine, one namespace per game.** A game's clips are
listed in its own `games/<id>/assets/manifest.json` and loaded when it is first
played, under a prefix - so two games may both ship a `jump` - but they land in
the *same* table, because one master volume and one mute have to cover the whole
cabinet. A game holding a mixer of its own would be a second thing the operator
menu had to know how to silence. `SoundManager.for_game` hands a game a view
that adds its prefix for it, so game code just says `play('jump')`.

Three channel details are deliberate:

* **Ambience gets its own reserved channel**, so a one-shot can never steal the
  looping siren mid-note.
* **A second reserved channel plays queued clips**, which never overlap: a clip
  asked for while that channel is busy waits rather than stacking. Pac-Man's
  dots are what this was written for - they alternate between two clips and a
  fast run of them queues (engine.js:3256) - but nothing about it is Pac-Man's,
  and any game with a rapid-fire sound wants the same treatment.
* **The clip to fall back to while paused is per game** (`pause_ambience`),
  because the manager restores ambience on unmute and has to know what the
  game running at the time calls that clip.
"""

import os

import pygame

from . import settings
from .renderer import read_manifest

# The cabinet's own audio, if it ever ships any. A game's clips live beside the
# game, under `games/<id>/assets/`.
ASSET_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets',
)

AMBIENCE_CHANNEL = 0
QUEUE_CHANNEL = 1
RESERVED_CHANNELS = 2
TOTAL_CHANNELS = 12

SETTINGS_FILE = settings.SETTINGS_FILE


class SoundManager:
    def __init__(self, asset_root=ASSET_ROOT, settings_file=SETTINGS_FILE,
                 enabled=True):
        self.asset_root = asset_root
        self.settings_file = settings_file
        self.enabled = enabled
        self.master_volume = 1
        self.paused = False
        self.cutscene = True
        self.current_ambience = None
        # What to loop while paused, in the running game's namespace. Set by
        # whichever game last started ambience - see `for_game`.
        self.pause_ambience = None
        self.sounds = {}
        self.ambience_channel = None
        self.queue_channel = None
        self._queue = ()        # the clip names being cycled
        self._queue_index = -1
        self._queued = False

    # -- setup ---------------------------------------------------------------

    def load(self):
        """Opens the channels and applies the saved volume.

        Any clips at the cabinet's own asset root are loaded too, though it
        ships none today: a game's audio arrives later, through `add_clips`,
        when that game is first played.
        """
        if not self.enabled:
            return self

        # One definition of what a manifest is, shared with the sprite side: a
        # missing, unparseable or wrongly-shaped one is silence rather than a
        # crash, because the cabinet has to boot.
        self.add_clips(self.asset_root, read_manifest(self.asset_root)['audio'])

        if pygame.mixer.get_init():
            pygame.mixer.set_num_channels(TOTAL_CHANNELS)
            pygame.mixer.set_reserved(RESERVED_CHANNELS)
            self.ambience_channel = pygame.mixer.Channel(AMBIENCE_CHANNEL)
            self.queue_channel = pygame.mixer.Channel(QUEUE_CHANNEL)

        self.set_master_volume(self.load_volume_preference())
        return self

    def for_game(self, prefix, pause_ambience=None):
        """A view of this mixer scoped to one game.

        Everything a game plays goes through it, so game code names its own
        clips and never has to know it is sharing a table. The cabinet-wide
        controls - mute, the master volume, silence-everything - stay on the
        manager, since they are the operator menu's to drive, not a game's.
        """
        return GameSound(self, prefix, pause_ambience)

    def add_clips(self, root, clips, prefix=''):
        """Loads `{name: relative_path}` into the shared clip table.

        How a game brings its own audio. It goes into the *same* table as
        everything else, so one master volume and one mute cover the whole
        cabinet - a game holding its own mixer would be a second thing for the
        operator menu to have to silence.

        `prefix` namespaces the names, because two games may both want a clip
        called `jump`. Returns how many loaded, which is the only sign the
        files are actually usable: a clip that fails to decode is skipped, as
        it always has been (engine.js:3191). A missing sound must never stop a
        game from being playable.
        """
        if not self.enabled or not isinstance(clips, dict):
            return 0

        loaded = 0
        for name, rel_path in clips.items():
            try:
                sound = pygame.mixer.Sound(os.path.join(root, rel_path))
            except (pygame.error, FileNotFoundError, TypeError):
                continue
            sound.set_volume(self.master_volume)
            self.sounds[f'{prefix}{name}'] = sound
            loaded += 1

        return loaded

    def load_volume_preference(self):
        """Stands in for localStorage.getItem('volumePreference')."""
        value = settings.read(self.settings_file).get('volume', 1)
        return 0 if value == 0 else 1

    def save_volume_preference(self, volume):
        """Stands in for localStorage.setItem (engine.js:1335).

        Merges rather than replaces: the controller choice lives in the same
        file, and writing `{"volume": ...}` wholesale would drop it. A
        read-only filesystem is ignored, as it was before.
        """
        settings.update({'volume': volume}, self.settings_file)

    # -- state ---------------------------------------------------------------

    def set_cutscene(self, new_value):
        """Blocks ambience during cutscenes (engine.js:3203)."""
        self.cutscene = new_value

    def set_master_volume(self, new_volume):
        """engine.js:3211 - the sound toggle is on/off, not a fader."""
        self.master_volume = new_volume

        for sound in self.sounds.values():
            sound.set_volume(new_volume)

        if self.master_volume == 0:
            self.stop_ambience()
        else:
            self.resume_ambience(self.paused)

    def toggle_mute(self):
        """engine.js:1332 - the Q key / sound button."""
        new_volume = 0 if self.master_volume == 1 else 1
        self.set_master_volume(new_volume)
        self.save_volume_preference(new_volume)
        return new_volume

    # -- one-shots -----------------------------------------------------------

    def play(self, sound):
        """engine.js:3244."""
        clip = self.sounds.get(sound)
        if clip is None or self.master_volume == 0:
            return
        clip.play()

    def play_queued(self, names):
        """Asks for the next of `names` on the reserved queue channel.

        The clips are cycled in order and never overlap: asking while the
        channel is busy queues one repeat, not a stack of them. Pac-Man's dots
        alternate between two clips this way (engine.js:3256) - eating a row of
        them at speed must not pile fourteen copies on top of each other.

        Only one clip is ever outstanding. A game that asks ten times before
        the channel frees up gets one more sound, which is the whole point: the
        queue is a throttle, not a buffer.
        """
        names = tuple(names)
        if names != self._queue:
            self._queue = names
            self._queue_index = -1
        self._queued = True
        self.service_queue()

    def service_queue(self):
        """Starts the queued clip once the previous one has finished.

        The reference hung this off `source.onended`; pygame has no such
        callback, so the channel is polled from the fixed-step update instead.
        """
        if self.queue_channel is None or self.master_volume == 0:
            self._queued = False
            return
        if not self._queued or not self._queue or self.queue_channel.get_busy():
            return

        self._queued = False
        self._queue_index = (self._queue_index + 1) % len(self._queue)

        clip = self.sounds.get(self._queue[self._queue_index])
        if clip is not None:
            self.queue_channel.play(clip)

    def update(self):
        """Called once per simulation step to service the queue channel."""
        if self.enabled:
            self.service_queue()

    # -- ambience ------------------------------------------------------------

    def set_ambience(self, sound, keep_current_ambience=False):
        """Loops an ambient track (engine.js:3287).

        `keep_current_ambience` plays something over the top (the pause beat)
        without forgetting what to go back to.
        """
        if self.cutscene:
            return

        if keep_current_ambience:
            self.paused = True
        else:
            self.current_ambience = sound
            self.paused = False

        self.stop_ambience()

        clip = self.sounds.get(sound)
        if clip is None or self.master_volume == 0 or self.ambience_channel is None:
            return

        self.ambience_channel.play(clip, loops=-1)

    def resume_ambience(self, paused=False):
        """engine.js:3315.

        `pause_ambience` is the running game's name for its paused loop, set
        when it starts ambience. A game that has none simply falls silent while
        paused rather than borrowing another game's clip.
        """
        if self.current_ambience:
            if paused:
                if self.pause_ambience:
                    self.set_ambience(self.pause_ambience, True)
                else:
                    self.stop_ambience()
            else:
                self.set_ambience(self.current_ambience)

    def stop_ambience(self):
        """engine.js:3330."""
        if self.ambience_channel is not None:
            self.ambience_channel.stop()

    def stop_all(self):
        """Silences everything, used when returning to the menu."""
        self.stop_ambience()
        if pygame.mixer.get_init():
            pygame.mixer.stop()


class GameSound:
    """One game's view of the cabinet's mixer.

    Adds the game's prefix to every clip name, and nothing else: there is one
    mixer, one master volume and one mute, and this does not hide any of them.
    A game reads `master_volume` to draw the speaker in its own HUD, and the
    operator menu still silences the machine in one call.

    It is deliberately not a subclass. What a game may do to the cabinet's audio
    is exactly the methods below - a game cannot save a volume preference or
    reload another game's clips through it.
    """

    def __init__(self, manager, prefix='', pause_ambience=None):
        self.manager = manager
        self.prefix = prefix
        # This game's name for its paused loop, if it has one. Pushed onto the
        # manager as soon as ambience starts, because that is the only moment
        # the manager could need it.
        self.pause_ambience = pause_ambience

    def qualified(self, name):
        return f'{self.prefix}{name}' if name else None

    # -- one-shots -----------------------------------------------------------

    def play(self, sound):
        self.manager.play(self.qualified(sound))

    def play_queued(self, names):
        """See `SoundManager.play_queued` - the throttled channel."""
        self.manager.play_queued([self.qualified(name) for name in names])

    # -- ambience ------------------------------------------------------------

    def set_ambience(self, sound, keep_current_ambience=False):
        self.manager.pause_ambience = self.qualified(self.pause_ambience)
        self.manager.set_ambience(self.qualified(sound), keep_current_ambience)

    def resume_ambience(self, paused=False):
        self.manager.resume_ambience(paused)

    def stop_ambience(self):
        self.manager.stop_ambience()

    def stop_all(self):
        self.manager.stop_all()

    # -- state ---------------------------------------------------------------

    def set_cutscene(self, new_value):
        self.manager.set_cutscene(new_value)

    def update(self):
        self.manager.update()

    @property
    def master_volume(self):
        """Cabinet-wide. Read to draw a mute indicator; changed by the menu."""
        return self.manager.master_volume

    @property
    def enabled(self):
        return self.manager.enabled
