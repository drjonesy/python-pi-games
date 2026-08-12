"""A built-in 5x7 bitmap font.

The web version set its UI in 'Press Start 2P', loaded from Google Fonts. That
is unavailable offline, and the Pi must not depend on the network to boot into a
game. A TTF would also be the wrong tool: the HUD is 8 logical pixels tall, and
no outline font is legible at that size.

So the glyphs live here as data. Each is 5x7 pixels drawn in a 6x8 cell (one
column of letter spacing, one row of leading), which matches the proportions of
the original arcade text. Rendered surfaces are cached per (text, scale, color).
"""

import pygame

GLYPH_WIDTH = 5
GLYPH_HEIGHT = 7
CELL_WIDTH = 6      # glyph + 1px letter spacing
CELL_HEIGHT = 8     # glyph + 1px leading

# One entry per character: seven rows of five bits, top to bottom.
GLYPHS = {
    'A': ('01110', '10001', '10001', '11111', '10001', '10001', '10001'),
    'B': ('11110', '10001', '10001', '11110', '10001', '10001', '11110'),
    'C': ('01110', '10001', '10000', '10000', '10000', '10001', '01110'),
    'D': ('11110', '10001', '10001', '10001', '10001', '10001', '11110'),
    'E': ('11111', '10000', '10000', '11110', '10000', '10000', '11111'),
    'F': ('11111', '10000', '10000', '11110', '10000', '10000', '10000'),
    'G': ('01110', '10001', '10000', '10111', '10001', '10001', '01110'),
    'H': ('10001', '10001', '10001', '11111', '10001', '10001', '10001'),
    'I': ('11111', '00100', '00100', '00100', '00100', '00100', '11111'),
    'J': ('00111', '00010', '00010', '00010', '00010', '10010', '01100'),
    'K': ('10001', '10010', '10100', '11000', '10100', '10010', '10001'),
    'L': ('10000', '10000', '10000', '10000', '10000', '10000', '11111'),
    'M': ('10001', '11011', '10101', '10101', '10001', '10001', '10001'),
    'N': ('10001', '10001', '11001', '10101', '10011', '10001', '10001'),
    'O': ('01110', '10001', '10001', '10001', '10001', '10001', '01110'),
    'P': ('11110', '10001', '10001', '11110', '10000', '10000', '10000'),
    'Q': ('01110', '10001', '10001', '10001', '10101', '10011', '01101'),
    'R': ('11110', '10001', '10001', '11110', '10100', '10010', '10001'),
    'S': ('01111', '10000', '10000', '01110', '00001', '00001', '11110'),
    'T': ('11111', '00100', '00100', '00100', '00100', '00100', '00100'),
    'U': ('10001', '10001', '10001', '10001', '10001', '10001', '01110'),
    'V': ('10001', '10001', '10001', '10001', '10001', '01010', '00100'),
    'W': ('10001', '10001', '10001', '10101', '10101', '11011', '10001'),
    'X': ('10001', '10001', '01010', '00100', '01010', '10001', '10001'),
    'Y': ('10001', '10001', '01010', '00100', '00100', '00100', '00100'),
    'Z': ('11111', '00001', '00010', '00100', '01000', '10000', '11111'),
    '0': ('01110', '10001', '10011', '10101', '11001', '10001', '01110'),
    '1': ('00100', '01100', '00100', '00100', '00100', '00100', '01110'),
    '2': ('01110', '10001', '00001', '00010', '00100', '01000', '11111'),
    '3': ('11111', '00010', '00100', '00010', '00001', '10001', '01110'),
    '4': ('00010', '00110', '01010', '10010', '11111', '00010', '00010'),
    '5': ('11111', '10000', '11110', '00001', '00001', '10001', '01110'),
    '6': ('00110', '01000', '10000', '11110', '10001', '10001', '01110'),
    '7': ('11111', '00001', '00010', '00100', '01000', '01000', '01000'),
    '8': ('01110', '10001', '10001', '01110', '10001', '10001', '01110'),
    '9': ('01110', '10001', '10001', '01111', '00001', '00010', '01100'),
    ' ': ('00000', '00000', '00000', '00000', '00000', '00000', '00000'),
    '!': ('00100', '00100', '00100', '00100', '00100', '00000', '00100'),
    '-': ('00000', '00000', '00000', '11111', '00000', '00000', '00000'),
    '=': ('00000', '00000', '11111', '00000', '11111', '00000', '00000'),
    '.': ('00000', '00000', '00000', '00000', '00000', '01100', '01100'),
    ',': ('00000', '00000', '00000', '00000', '01100', '01100', '00100'),
    ':': ('00000', '01100', '01100', '00000', '01100', '01100', '00000'),
    '/': ('00001', '00010', '00010', '00100', '01000', '01000', '10000'),
    '_': ('00000', '00000', '00000', '00000', '00000', '00000', '11111'),
    '>': ('10000', '01000', '00100', '00010', '00100', '01000', '10000'),
    '<': ('00001', '00010', '00100', '01000', '00100', '00010', '00001'),
    '(': ('00010', '00100', '01000', '01000', '01000', '00100', '00010'),
    ')': ('01000', '00100', '00010', '00010', '00010', '00100', '01000'),
    # Square brackets enclose the control in every hint (`ui/hints.py`). Their
    # absence was not harmless: an unmapped character falls back to a hollow
    # box, which is indistinguishable from the square-panel icon drawn a few
    # cells away.
    '[': ('01110', '01000', '01000', '01000', '01000', '01000', '01110'),
    ']': ('01110', '00010', '00010', '00010', '00010', '00010', '01110'),
    '+': ('00000', '00100', '00100', '11111', '00100', '00100', '00000'),
    '*': ('00000', '00000', '01110', '01110', '01110', '00000', '00000'),
    "'": ('00100', '00100', '00000', '00000', '00000', '00000', '00000'),
    '?': ('01110', '10001', '00001', '00010', '00100', '00000', '00100'),
    # Icons for the in-game control hint (`ui/hud.py`). Kept here rather than
    # drawn as primitives so they colour, align, measure and cache exactly like
    # the text they sit beside - a hint that is half text and half sprite would
    # need two layout paths.
    #
    # The square is the mat's square panel; the speaker is the sound toggle. The
    # muted state is the same speaker with a diagonal struck through it, drawn
    # over the top rather than kept as a second glyph, because a slash legible
    # at 5x7 needs the whole cell and would leave nothing recognisable beneath.
    '□': ('00000', '11111', '10001', '10001', '10001', '11111', '00000'),
    # Cone on the left, three wave dots on the right. Without the waves the
    # cone alone reads as a plain arrow at this size, not a speaker.
    '🔈': ('00100', '01101', '11100', '11101', '11100', '01101', '00100'),
    # More-above / more-below markers on the game picker's list
    # (`ui/game_select.py`). Solid triangles rather than '^' and 'v': `render`
    # upper-cases everything, so a 'v' would come out as the letter V.
    '▲': ('00000', '00100', '01110', '11111', '00000', '00000', '00000'),
    '▼': ('00000', '00000', '00000', '11111', '01110', '00100', '00000'),
}

# Anything unmapped renders as a hollow box rather than vanishing, so a missing
# glyph is visible instead of silently shortening a string.
FALLBACK = ('11111', '10001', '10001', '10001', '10001', '10001', '11111')

# 'SPACE' is shown in the name-entry keyboard; the caret and the space
# placeholder both reuse '_'.


class BitmapFont:
    def __init__(self):
        self._cache = {}

    def measure(self, text, scale=1):
        """Pixel size of `text`, including inter-letter spacing."""
        if not text:
            return (0, GLYPH_HEIGHT * scale)
        width = (len(text) * CELL_WIDTH - 1) * scale
        return (width, GLYPH_HEIGHT * scale)

    def render(self, text, color, scale=1):
        """Returns a cached transparent Surface holding `text`.

        Every distinct (text, color, scale) is rasterized once. The HUD's score
        changes constantly, so this cache is bounded by clearing it whenever it
        grows past a few hundred entries rather than growing without limit.
        """
        key = (text, color, scale)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        if len(self._cache) > 512:
            self._cache.clear()

        text = text.upper()
        width, height = self.measure(text, scale)
        surface = pygame.Surface((max(1, width), max(1, height)), pygame.SRCALPHA)

        for index, char in enumerate(text):
            glyph = GLYPHS.get(char, FALLBACK)
            origin_x = index * CELL_WIDTH * scale
            for row, bits in enumerate(glyph):
                for column, bit in enumerate(bits):
                    if bit == '1':
                        surface.fill(
                            color,
                            (origin_x + column * scale, row * scale,
                             scale, scale),
                        )

        self._cache[key] = surface
        return surface

    def draw(self, target, text, x, y, color, scale=1, align='left'):
        """Blits `text` onto `target`. `align` is left, center or right."""
        surface = self.render(text, color, scale)
        width = surface.get_width()

        if align == 'center':
            x -= width / 2
        elif align == 'right':
            x -= width

        target.blit(surface, (round(x), round(y)))
        return surface.get_size()
