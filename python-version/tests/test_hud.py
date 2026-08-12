"""The in-game control reminder.

The pause and sound controls used to be named only on the title screen, so a
player had to have memorised them by the time they were playing. They are now
drawn in the one-tile gap between the score row and the maze, written as
`PAUSE = [SELECT]   🔈 = [□]`.

Two things here are easy to break silently and are pinned as a result:

* **The band it sits in.** That gap is 8px tall and the glyphs are 7px, so
  there is one pixel of slack. Text that drifts up hits the score, down hits
  the maze, and neither fails loudly in a rendered frame.
* **The mute slash.** The speaker is both the label and the on/off indicator,
  so if the strike stops landing on it the game loses its only visible report
  of mute - the separate MUTE readout was removed as redundant once this
  existed.
"""

import pygame
import pytest

from games.pacman import constants as C
from cabinet.controls import KEYBOARD, PAD, SCHEMES, Controls
from cabinet.font import GLYPHS, BitmapFont
from cabinet.ui.hints import (
    SLASH_COLOR, SPEAKER, control_hints, sound_hint,
)
from games.pacman.ui.hud import HINT_Y, LINE_TWO_Y, Hud

pygame.init()


class RecordingFont:
    """Captures what would be drawn, so wording is testable without a display.

    Draws nothing, which also means anything found on the surface afterwards
    must have come from the slash.
    """

    def __init__(self):
        self.texts = []

    def draw(self, surface, text, x, y, color, scale=1, align='left'):
        self.texts.append(text)
        return (0, 7)

    def measure(self, text, scale=1):
        return ((len(text) * 6 - 1) * scale, 7 * scale)


class StubRenderer:
    def __init__(self):
        self.surface = pygame.Surface((C.LOGICAL_WIDTH, C.LOGICAL_HEIGHT))

    def draw_image_at(self, *args, **kwargs):
        pass

    def fill_rect_at(self, *args, **kwargs):
        pass


class StubSound:
    def __init__(self, master_volume=1):
        self.master_volume = master_volume


class StubCoordinator:
    """Only the attributes `Hud.draw` actually reads."""

    def __init__(self, show_fps=False, muted=False):
        self.points = 1234
        self.high_score = 5678
        self.lives = 3
        self.fruit_display = []
        self.pellet_blink_ms = 0
        self.show_fps = show_fps
        self.sound_manager = StubSound(0 if muted else 1)


@pytest.fixture
def hud_for():
    def build(name=KEYBOARD, font=None):
        font = font or RecordingFont()
        controls = Controls(name=name, path=None)
        return Hud(StubRenderer(), font, controls), font
    return build


def slash_pixels(surface):
    """How much of the strike colour is on the screen, in the hint band."""
    return sum(
        surface.get_at((x, y))[:3] == SLASH_COLOR
        for x in range(surface.get_width())
        for y in range(HINT_Y - 2, HINT_Y + 10)
    )


# -- wording -----------------------------------------------------------------

def test_pause_and_sound_are_named_during_play(hud_for):
    hud, font = hud_for(KEYBOARD)
    hud.draw(StubCoordinator(), 60.0)

    assert f'PAUSE = [ESC]   {SPEAKER} = [Q]' in font.texts


def test_the_hint_follows_the_pad_scheme(hud_for):
    """The speaker survives as a state light, but names no control.

    The mat has no sound control since the square panel was unbound - that moved
    to the operator menu - so there is nothing to bracket. Whether sound is on
    still has to be visible, which is the speaker's other job.
    """
    hud, font = hud_for(PAD)
    hud.draw(StubCoordinator(), 60.0)

    assert f'PAUSE = [SELECT]   {SPEAKER}' in font.texts
    assert not any('ESC' in text for text in font.texts)
    # No control is named for it - not the panel, not the word, not the shape.
    assert not any('= [□]' in text for text in font.texts)
    assert not any('SQUARE' in text for text in font.texts)


def test_the_speaker_replaces_the_word_sound(hud_for):
    hud, font = hud_for(KEYBOARD)
    hud.draw(StubCoordinator(), 60.0)

    assert not any('SOUND' in text for text in font.texts)
    assert any(SPEAKER in text for text in font.texts)


def test_the_fps_counter_no_longer_displaces_the_hint(hud_for):
    """It used to share the score row's corner; the gap band is clear of it."""
    hud, font = hud_for(KEYBOARD, font=RecordingFont())
    hud.draw(StubCoordinator(show_fps=True), 60.0)

    assert any('PAUSE = ' in text for text in font.texts)


def test_the_score_row_still_draws(hud_for):
    """The hint must be an addition, not a replacement."""
    hud, font = hud_for(KEYBOARD)
    hud.draw(StubCoordinator(), 60.0)

    assert 'HIGH SCORE' in font.texts
    assert '1234' in font.texts
    assert '5678' in font.texts


def test_the_one_up_blink_is_unaffected(hud_for):
    """1UP is dark for the first half of its cycle - easy to mistake for a
    regression when reading a single frame."""
    hud, font = hud_for(KEYBOARD)
    dark = StubCoordinator()
    dark.pellet_blink_ms = 0
    hud.draw(dark, 60.0)
    assert '1UP' not in font.texts

    hud, font = hud_for(KEYBOARD)
    lit = StubCoordinator()
    lit.pellet_blink_ms = C.ONE_UP_BLINK_PERIOD_MS * 0.75
    hud.draw(lit, 60.0)
    assert '1UP' in font.texts


def test_the_pause_overlay_says_resume(hud_for):
    hud, font = hud_for(PAD)
    hud.draw_pause_overlay()

    assert 'PAUSED' in font.texts
    assert any('RESUME = [SELECT]' in text for text in font.texts)


# -- mute --------------------------------------------------------------------

def test_muting_strikes_the_speaker(hud_for):
    hud, _ = hud_for(KEYBOARD)
    hud.draw(StubCoordinator(muted=True), 60.0)

    assert slash_pixels(hud.renderer.surface) > 0


def test_unmuted_draws_no_slash(hud_for):
    hud, _ = hud_for(KEYBOARD)
    hud.draw(StubCoordinator(muted=False), 60.0)

    assert slash_pixels(hud.renderer.surface) == 0


def test_the_pad_speaker_names_no_control():
    """A bare glyph, not `🔈 = [□]` - the panel it used to name does nothing."""
    assert sound_hint(SCHEMES[PAD]) == SPEAKER
    assert SPEAKER in control_hints(SCHEMES[PAD])
    assert '[' not in sound_hint(SCHEMES[PAD])


@pytest.mark.parametrize('name', [KEYBOARD, PAD])
def test_the_slash_lands_on_the_speaker_not_a_neighbour(name):
    """The speaker is no longer the last character, so its index is looked up.

    Drawn with the real font: the slash must overlap the speaker's own cell and
    not stray into the bracket beside it.
    """
    font = BitmapFont()
    text = control_hints(SCHEMES[name])
    index = text.index(SPEAKER)

    surface = pygame.Surface((C.LOGICAL_WIDTH, 20))
    from cabinet.ui.hints import draw_hint
    draw_hint(surface, font, text, C.LOGICAL_WIDTH / 2, 5, C.WHITE,
              align='center', muted=True)

    width = font.measure(text)[0]
    left = C.LOGICAL_WIDTH / 2 - width / 2
    cell_left = left + index * 6

    struck = [x for x in range(surface.get_width())
              for y in range(surface.get_height())
              if surface.get_at((x, y))[:3] == SLASH_COLOR]
    assert struck, 'nothing was struck'
    # Allow the one-pixel overshoot the stroke deliberately has at each end.
    assert min(struck) >= cell_left - 2
    assert max(struck) <= cell_left + 5 + 2


# -- layout ------------------------------------------------------------------

@pytest.mark.parametrize('name', [KEYBOARD, PAD])
def test_the_hint_fits_the_screen(name):
    font = BitmapFont()
    assert font.measure(control_hints(SCHEMES[name]))[0] <= C.LOGICAL_WIDTH


@pytest.mark.parametrize('name', [KEYBOARD, PAD])
def test_the_hint_sits_between_the_score_row_and_the_maze(name):
    """One pixel of slack in an 8px band - worth pinning both edges."""
    font = BitmapFont()
    height = font.measure(control_hints(SCHEMES[name]))[1]

    assert HINT_Y >= LINE_TWO_Y + 7, 'overlaps the score row'
    assert HINT_Y + height <= C.MAZE_ORIGIN_Y, 'overlaps the maze'


@pytest.mark.parametrize('name', [KEYBOARD, PAD])
def test_the_pause_overlay_line_fits(name):
    font = BitmapFont()
    text = control_hints(SCHEMES[name], verb='RESUME')
    assert font.measure(text)[0] <= C.LOGICAL_WIDTH


def test_the_icon_glyphs_exist():
    """These were deleted once already, when the passcode stopped using them.

    A missing glyph renders as the fallback box rather than failing, so nothing
    else here would catch it.
    """
    assert SPEAKER in GLYPHS
    for scheme in SCHEMES.values():
        for text in (control_hints(scheme),
                     control_hints(scheme, verb='RESUME'),
                     sound_hint(scheme)):
            for char in text:
                assert char == ' ' or char in GLYPHS, f'{char!r} has no glyph'
