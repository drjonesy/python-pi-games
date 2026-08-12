"""Audio playback (engine.js:3142).

The reference decoded every clip into a Web Audio buffer up front so nothing
decoded mid-game; `pygame.mixer.Sound` does the same thing by construction.

Two details are deliberate:

* **Ambience gets its own reserved channel**, so a one-shot can never steal the
  looping siren mid-note.
* **Dot sounds get their own reserved channel too**, because the reference
  throttles them: dots alternate between two clips but never overlap, so a fast
  run of dots queues rather than stacking (engine.js:3256).
"""

import json
import os

import pygame

from . import settings

ASSET_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets',
)

AMBIENCE_CHANNEL = 0
DOT_CHANNEL = 1
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
        self.dot_sound = 1
        self.queued_dot_sound = False
        self.current_ambience = None
        self.sounds = {}
        self.ambience_channel = None
        self.dot_channel = None

    # -- setup ---------------------------------------------------------------

    def load(self):
        """Loads every clip listed in the asset manifest."""
        if not self.enabled:
            return self

        manifest_path = os.path.join(self.asset_root, 'manifest.json')
        try:
            with open(manifest_path, encoding='utf-8') as handle:
                parsed = json.load(handle)
        except (OSError, ValueError):
            parsed = None

        # Valid JSON is not necessarily the *shape* expected: a manifest that
        # parsed as a list would sail past the except above and then fail on
        # .get. Same rule as everywhere else - a corrupt file is silence, not a
        # crash, because the cabinet has to boot.
        clips = parsed.get('audio') if isinstance(parsed, dict) else None
        if not isinstance(clips, dict):
            clips = {}

        for name, rel_path in clips.items():
            path = os.path.join(self.asset_root, rel_path)
            try:
                self.sounds[name] = pygame.mixer.Sound(path)
            except (pygame.error, FileNotFoundError):
                # A missing or undecodable clip must not block the game
                # (engine.js:3191).
                pass

        if pygame.mixer.get_init():
            pygame.mixer.set_num_channels(TOTAL_CHANNELS)
            pygame.mixer.set_reserved(RESERVED_CHANNELS)
            self.ambience_channel = pygame.mixer.Channel(AMBIENCE_CHANNEL)
            self.dot_channel = pygame.mixer.Channel(DOT_CHANNEL)

        self.set_master_volume(self.load_volume_preference())
        return self

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

    def play_dot_sound(self):
        """Alternates dot_1 / dot_2, but never overlaps them (engine.js:3256)."""
        self.queued_dot_sound = True
        self.service_dot_queue()

    def service_dot_queue(self):
        """Starts the queued dot clip once the previous one has finished.

        The reference hung this off `source.onended`; pygame has no such
        callback, so the channel is polled from the fixed-step update instead.
        """
        if self.dot_channel is None or self.master_volume == 0:
            self.queued_dot_sound = False
            return
        if not self.queued_dot_sound or self.dot_channel.get_busy():
            return

        self.queued_dot_sound = False
        self.dot_sound = 2 if self.dot_sound == 1 else 1

        clip = self.sounds.get(f'dot_{self.dot_sound}')
        if clip is not None:
            self.dot_channel.play(clip)

    def update(self):
        """Called once per simulation step to service the dot queue."""
        if self.enabled:
            self.service_dot_queue()

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
        """engine.js:3315."""
        if self.current_ambience:
            if paused:
                self.set_ambience('pause_beat', True)
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
