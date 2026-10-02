"""Glyph set, template layout and font metrics.

Edit this file to add/remove glyphs or tweak spacing. The template and the
build both read from here, so regenerate templates after changing layout.
"""

FAMILY = "AurebeshFiles Hand"
STYLE = "Regular"
VERSION = "1.000"

# ---------------------------------------------------------------- metrics
# Font units. One template cell maps to one em, top of cell = CELL_TOP,
# bottom of cell = CELL_TOP - UPM.
UPM = 1000
CAP_HEIGHT = 700
X_HEIGHT = 500
CELL_TOP = 800          # ascender line (top edge of each cell)
DESCENDER = -200        # bottom edge of each cell
SIDE_BEARING = 60       # blank space left/right of each drawn glyph
SPACE_WIDTH = 320

# ---------------------------------------------------------------- template
CELL_PX = 500           # drawing box size in pixels (square)
GUTTER_PX = 70          # space between cells
LABEL_PX = 50           # label strip above each cell
MARGIN_PX = 80

# ---------------------------------------------------------------- glyphs
# (characters, label shown in template)
# Single chars map straight to Unicode. Two-char entries become ligatures.
LETTERS = [
    ("A", "Aurek"), ("B", "Besh"), ("C", "Cresh"), ("D", "Dorn"),
    ("E", "Esk"), ("F", "Forn"), ("G", "Grek"), ("H", "Herf"),
    ("I", "Isk"), ("J", "Jenth"), ("K", "Krill"), ("L", "Leth"),
    ("M", "Mern"), ("N", "Nern"), ("O", "Osk"), ("P", "Peth"),
    ("Q", "Qek"), ("R", "Resh"), ("S", "Senth"), ("T", "Trill"),
    ("U", "Usk"), ("V", "Vev"), ("W", "Wesk"), ("X", "Xesh"),
    ("Y", "Yirt"), ("Z", "Zerek"),
]

DIGRAPHS = [
    ("CH", "Cherek"), ("AE", "Enth"), ("EO", "Onith"), ("KH", "Krenth"),
    ("NG", "Nen"), ("OO", "Orenth"), ("SH", "Sen"), ("TH", "Thesh"),
]

DIGITS = [(str(d), "") for d in range(10)]

PUNCTUATION = [
    (".", "period"), (",", "comma"), ("?", "question"), ("!", "exclam"),
    (":", "colon"), (";", "semicolon"), ("'", "quotesingle"),
    ('"', "quotedbl"), ("-", "hyphen"), ("(", "parenleft"),
    (")", "parenright"), ("/", "slash"), ("$", "credit"),
]

SYMBOLS = [
    ("@", "at"), ("#", "numbersign"), ("%", "percent"), ("^", "asciicircum"),
    ("*", "asterisk"), ("+", "plus"), ("=", "equal"), ("_", "underscore"),
    ("[", "bracketleft"), ("]", "bracketright"), ("{", "braceleft"),
    ("}", "braceright"), ("\\", "backslash"), ("|", "bar"),
]

MORE_SYMBOLS = [
    ("&", "ampersand"), ("<", "less"), (">", "greater"),
    ("~", "asciitilde"), ("`", "grave"),
]

# Standard PostScript names for punctuation/digits (fonts want these).
_PS_NAMES = {
    ".": "period", ",": "comma", "?": "question", "!": "exclam",
    ":": "colon", ";": "semicolon", "'": "quotesingle", '"': "quotedbl",
    "-": "hyphen", "(": "parenleft", ")": "parenright", "/": "slash",
    "$": "dollar", "@": "at", "#": "numbersign", "%": "percent",
    "^": "asciicircum", "*": "asterisk", "+": "plus", "=": "equal",
    "_": "underscore", "[": "bracketleft", "]": "bracketright",
    "{": "braceleft", "}": "braceright", "\\": "backslash", "|": "bar",
    "&": "ampersand", "<": "less", ">": "greater", "~": "asciitilde",
    "`": "grave",
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def glyph_name(chars):
    if len(chars) == 1:
        return _PS_NAMES.get(chars, chars)
    return "_".join(chars)          # ligature: T_H, t_h


def _entries(items, lower=False):
    out = []
    for chars, label in items:
        c = chars.lower() if lower else chars
        out.append({"chars": c, "name": glyph_name(c), "label": label})
    return out


# Pages = template sheets. Each page is one PNG you draw on.
# (file name, glyph entries, columns)
PAGES = [
    ("1-uppercase", _entries(LETTERS), 7),
    ("2-lowercase", _entries(LETTERS, lower=True), 7),
    ("3-ligatures", _entries(DIGRAPHS) + _entries(DIGRAPHS, lower=True), 8),
    ("4-digits", _entries(DIGITS), 5),
    ("5-punct-symbols", _entries(PUNCTUATION) + _entries(SYMBOLS) + _entries(MORE_SYMBOLS), 7),
]
