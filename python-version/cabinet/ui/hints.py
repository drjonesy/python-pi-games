"""The control reminder shared by the title screen and the score row.

Written as `LABEL = [CONTROL]`, so the thing you press is visually bracketed off
from what it does:

    PAUSE = [SELECT]   🔈 = [□]

The sound row has no word: the speaker *is* the label, and it is struck through
with a diagonal when muted, so the same glyph names the control and reports its
state. That is the only place in the game that shows mute without spelling it
out. The bracketed control is drawn rather than named wherever the mat has a
shape printed on it.

A scheme may have no sound control at all - the pad does not, since the square
panel was unbound for being a corner that feet kept clipping. The speaker then
loses its bracket and stays on as a pure status light, still struck through when
muted; the control itself moved into the operator menu:

    PAUSE = [SELECT]   🔈

The slash is drawn over the glyph rather than being a second glyph of its own: a
diagonal legible at 5x7 needs the whole cell, which would leave nothing
recognisable underneath it.
"""

import pygame

from .. import constants as C
from ..font import CELL_WIDTH, GLYPH_HEIGHT, GLYPH_WIDTH

SPEAKER = '🔈'

# Wide enough to read as two separate hints rather than one run-on line.
SEPARATOR = '   '

# Red so "off" reads at a glance against both the black maze surround and the
# amber title backdrop; the hint text itself is deliberately low-contrast.
SLASH_COLOR = C.ARCADE_RED


def pause_hint(scheme, verb='PAUSE'):
    """`PAUSE = [ESC]`. `verb` is RESUME on the pause overlay."""
    return f'{verb} = [{scheme.pause}]'


def sound_hint(scheme):
    """`🔈 = [Q]`, or a bare `🔈` on a scheme with no sound control.

    The speaker was always doing two jobs - naming the control and, by being
    struck through, reporting whether sound is on. The pad scheme has no control
    to name since the square panel was unbound, but the *state* still matters:
    an operator glancing at a silent cabinet needs to know whether it is muted
    or broken. So the bracketed control drops away and the speaker stays,
    reading as a status light rather than a label. Sound is turned on and off
    from the operator menu under that scheme - see `ui/system_menu.py`.
    """
    if not scheme.sound_icon:
        return SPEAKER
    return f'{SPEAKER} = [{scheme.sound_icon}]'


def control_hints(scheme, verb='PAUSE'):
    """Both hints on one line, the form the title screen and score row use."""
    return f'{pause_hint(scheme, verb)}{SEPARATOR}{sound_hint(scheme)}'


def draw_hint(surface, font, text, x, y, color, align='left', scale=1,
              muted=False):
    """Draws `text`, striking the speaker glyph through when `muted`.

    The speaker is located by index rather than assumed to be last, so the
    wording of the line can change without silently moving the slash onto some
    other character.
    """
    font.draw(surface, text, x, y, color, scale=scale, align=align)

    index = text.find(SPEAKER)
    if not muted or index < 0:
        return

    width = font.measure(text, scale)[0]
    if align == 'right':
        left = x - width
    elif align == 'center':
        left = x - width / 2
    else:
        left = x

    icon_left = round(left + index * CELL_WIDTH * scale)
    top = round(y)

    # Bottom-left to top-right, overshooting the glyph box by a pixel at each
    # end so the ends of the stroke read clear of the icon.
    pygame.draw.line(
        surface, SLASH_COLOR,
        (icon_left - 1, top + GLYPH_HEIGHT * scale),
        (icon_left + GLYPH_WIDTH * scale, top - 1),
        max(1, scale),
    )
