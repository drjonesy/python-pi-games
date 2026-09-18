"""Keeps death and sexual words off the high-score boards.

The name-entry keyboard only offers A-Z and space, so there is no leetspeak or
punctuation to see through. That leaves two ways to sneak a word in: spacing it
out ("K I L L") and burying it in a longer name ("IKILLU"). Both are caught by
removing the spaces and searching the result for each word.

Searching inside names also catches innocent ones - EDDIE contains DIE and SKILL
contains KILL. `ALLOWED` lists those. Each allowed word is cut out of the name
before the search, so SKILL passes but SKILLKILL does not.

A few words are too short to search for inside other words without hitting
ordinary ones (TIT is in TITAN, CUM in CUCUMBER). `WHOLE_WORDS` blocks those
only when they are the whole name or one space-separated part of it.

Everything is uppercase because that is all the keyboard can type.
"""

BLOCKED = (
    # Death.
    'KILL', 'DIE', 'DEAD', 'DEATH', 'DYING', 'MURDER', 'SUICIDE', 'HOMICIDE',
    'GENOCIDE', 'CORPSE', 'SLAUGHTER', 'MASSACRE', 'BEHEAD', 'STAB', 'KYS',
    # Sexual.
    'SEX', 'BOOB', 'TITS', 'TITTY', 'TITTIE', 'PENIS', 'VAGINA', 'DICK',
    'COCK', 'PUSSY', 'FUCK', 'PORN', 'NUDE', 'NAKED', 'HORNY', 'BONER',
    'NIPPLE', 'BREAST', 'ANAL', 'RAPE', 'SEMEN', 'SPERM', 'ORGASM', 'ORGY',
    'MILF', 'SLUT', 'WHORE', 'HOOKER', 'JIZZ', 'CLIT', 'DILDO', 'HENTAI',
    'XXX', 'NSFW', 'KINKY', 'FETISH', 'VIBRATOR', 'CONDOM', 'HUMPING',
)

WHOLE_WORDS = ('TIT', 'CUM', 'ANUS', 'HOE', 'HOES', 'THOT')

# Real names and words that happen to contain a blocked one. Longest first, so
# FREDDIE is cut out whole rather than leaving FRED + DIE behind.
ALLOWED = tuple(sorted((
    # DIE
    'EDDIE', 'FREDDIE', 'TEDDIE', 'SADIE', 'MADDIE', 'ADDIE', 'MADIE', 'JODIE',
    'CODIE', 'BRODIE', 'GORDIE', 'DIEGO', 'DIEDRE', 'DIERDRE', 'DIETER',
    'DIESEL', 'BIRDIE', 'INDIE', 'GOODIE', 'FOODIE', 'CANDIE', 'LADIES',
    'BUDDIES', 'GOODIES', 'SOLDIER', 'STUDIES', 'DIET', 'KIDDIE', 'HOODIE',
    'CADDIE', 'NOODIE', 'RUDIE', 'DIEM',
    # KILL
    'SKILL', 'KILLIAN',
    # STAB
    'STABLE', 'STABIL',
    # DICK / COCK
    'DICKENS', 'DICKSON', 'PEACOCK', 'HANCOCK', 'WOODCOCK', 'COCKATOO',
    'COCKPIT', 'COCKATIEL', 'SHUTTLECOCK',
    # ANAL
    'CANAL', 'BANAL', 'ANALOG', 'ANALYS', 'ANALYZ',
    # RAPE
    'GRAPE', 'DRAPE', 'TRAPEZ', 'SCRAPE', 'CRAPE',
    # ORGY / KYS / SEX
    'GEORGY', 'SKY', 'SUSSEX', 'ESSEX', 'MIDDLESEX',
    # NUDE / DEAD
    'DENUDE',
), key=len, reverse=True))


def is_allowed(name):
    """True unless `name` contains a blocked word.

    An empty name is allowed: the leaderboard stores it as the default name.
    """
    upper = str(name if name is not None else '').upper()
    letters = ''.join(ch for ch in upper if ch.isalpha())

    words = upper.split()
    if letters in WHOLE_WORDS or any(word in WHOLE_WORDS for word in words):
        return False

    for word in ALLOWED:
        letters = letters.replace(word, ' ')
    return not any(blocked in letters for blocked in BLOCKED)
