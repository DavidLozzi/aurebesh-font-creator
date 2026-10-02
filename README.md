# AurebeshFiles Hand

Draw Aurebesh glyphs by hand (Procreate, Illustrator, Photoshop, Krita, or pen and paper plus a scanner) and turn them into a real font: `.otf`, `.ttf` and `.woff2`, plus a preview page.

The script does three things:

1. `template` writes blank drawing sheets with a labelled box for every glyph.
2. You draw on the sheets and export them as PNGs.
3. `build` traces the ink in your PNGs into vector outlines and assembles the font files.

Tested on macOS with Python 3.9. It should work anywhere Python 3 and the packages below install.

## Setup (once)

You need Python 3 and a terminal.

```sh
git clone <this repo> aurebesh-font     # or just download the folder
cd aurebesh-font
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Windows, use `.venv\Scripts\python` and `.venv\Scripts\pip` in place of `.venv/bin/...`.

Dependencies (`requirements.txt`): `pillow`, `numpy`, `fonttools[woff]` (includes `brotli`, needed for `.woff2`), `potracer` (the bitmap tracer) and `skia-pathops` (cleans up overlapping outlines).

## Quick test (no drawing needed)

```sh
.venv/bin/python aurebesh.py demo
.venv/bin/python aurebesh.py build --drawings drawings-demo
```

`demo` fills the sheets with Arial Bold so you can check that the pipeline works. It reads `/System/Library/Fonts/Supplemental/Arial Bold.ttf`, which exists on macOS only. On other systems, edit the path in `cmd_demo` in `aurebesh.py`, or skip this step.

## The workflow

### 1. Make the sheets

```sh
.venv/bin/python aurebesh.py template
```

This writes five PNGs into `templates/` (300 dpi):

| Sheet | Contents | Size (px) |
|---|---|---|
| `1-uppercase` | A–Z | 4080×2570 |
| `2-lowercase` | a–z | 4080×2570 |
| `3-ligatures` | CH AE EO KH NG OO SH TH. Top row uppercase, bottom row lowercase. | 4650×1330 |
| `4-digits` | 0–9 | 2940×1330 |
| `5-punct-symbols` | `. , ? ! : ; ' " - ( ) / $ @ # % ^ * + = _ [ ] { } \ \| & < > ~ \`` | 4080×3190 |

Each glyph has one labelled box. The sheets are regenerated from `glyphs.py`, so regenerate them after changing anything there.

### 2. Draw

Get a sheet into your drawing app **at its exact pixel size**.

- **Procreate:** make a new canvas at the sheet's pixel size, then insert the PNG as a layer. Lock it and set it to about 50% opacity. Draw on a new layer above it.
- **Illustrator iPad / Photoshop / Krita / etc.:** place the PNG, lock that layer, and draw on a layer above it.
- **On paper:** print the sheet at 100% scale, draw in black marker, then scan it flat. The scan has to end up at the template's pixel size or at least its exact aspect ratio (see "Names and sizes" below). A flatbed scan is much safer than a phone photo, because a tilted image won't line up with the boxes.

Drawing rules:

- Use **solid black** and turn pen pressure off, so the stroke is an even weight. Pick one brush size and keep it for every glyph.
- Sit each glyph on the thick **base** line. Capitals reach the **cap** line. Lowercase can use the **x-height** line or anything else you like. Descenders can go below the base line.
- Stay inside the glyph's box. A little overshoot is fine (the tracer also reads about 35 px into the gap around each box), but ink from a neighbouring box inside that gap can bleed in.
- Keep strokes overlapping where shapes should join. Gaps and open shapes trace raggedly.
- Make dots (periods, colons) chunky, because tiny blobs are treated as specks and dropped.

### 3. Export

Export **only the drawing layer** at the full canvas size as a PNG. Hide the template layer and the background first.

Exporting with the template still visible also works, because the pale blue guides are ignored. Only dark pixels count as ink.

Save each file into `drawings/` named by its sheet number: `1.png` to `5.png`. Long names also work (`1-uppercase.png`).

### 4. Build

```sh
.venv/bin/python aurebesh.py build
```

Output goes to `build/`:

- `AurebeshFilesHand.otf`
- `AurebeshFilesHand.ttf`
- `AurebeshFilesHand.woff2`
- `preview.html`: open it in a browser to type with the font and see which glyphs are missing.

The build prints how many glyphs it traced per sheet, and lists any that were missing. For example, `5-punct-symbols: 31/32 glyphs` followed by `Missing (1): _`. A glyph is missing when its box is empty, or its ink is too faint or too small to trace.

Each build overwrites `build/`. Copy finished fonts somewhere safe before building a variation.

To build from another folder: `.venv/bin/python aurebesh.py build --drawings path/to/folder`.

### 5. Iterate

Redraw a glyph, re-export that sheet, and run `build` again. It only takes a few seconds.

You can build as you go. Empty boxes are skipped, a sheet with no PNG is skipped, and undrawn lowercase letters fall back to the uppercase glyph.

### 6. Install

Double-click the `.otf` (or `.ttf`) to install it on macOS or Windows. For websites, use the `.woff2`:

```css
@font-face {
  font-family: "AurebeshFiles Hand";
  src: url("AurebeshFilesHand.woff2") format("woff2");
}
```

## How it works

You don't need this to use the script, but it explains most surprises.

- **Ink detection.** A pixel is ink if it is darker than mid-grey (luminance below 128) and mostly opaque. Pale grey, light pencil and a 50%-opacity stroke can vanish or break up. Use pure black.
- **Tracing.** Each box is cropped out and traced to smooth curves with potrace. Specks smaller than 12 pixels are discarded. Very thin or shaky strokes get smoothed.
- **Vertical position follows the box.** Each 500 px box maps to 1000 font units. There is no auto-scaling, so where you sit a glyph relative to the base and cap lines is where it lands in the font.
- **Horizontal position follows the ink.** Each outline is shifted so its left edge sits one side bearing from the origin. The advance width is the ink width plus a margin on both sides. Where you draw left to right inside the box does not matter, and narrow glyphs get narrow slots.
- **Ligatures.** Typing a digraph swaps in its single Aurebesh glyph, using the OpenType `liga` feature, which browsers and most apps enable by default: `TH` and `Th` give uppercase Thesh, `th` gives lowercase Thesh. The same goes for CH, AE, EO, KH, NG, OO and SH. If you turn ligatures off in your app or CSS (`font-variant-ligatures: none`), you lose them.

## Names and sizes

- **File matching.** For sheet `4-digits`, the build accepts `4.png`, `4-digits.png`, or any PNG starting with `4-` or `4 `.
- **Size check.** If your PNG's size differs from the template, the build resizes it when the aspect ratio matches within 1%. Otherwise it stops with `size ... does not match template`. Resizing works, but blurs the edges slightly, so export at the exact size.
- **Changing the layout breaks old drawings.** Cells are located by position, so changing a sheet's column count, order or contents (in `glyphs.py`) invalidates PNGs drawn on the old template. Regenerate the templates and redraw.

## Tweaks: `glyphs.py`

- `FAMILY` sets the font name. Output files follow it with spaces removed (`AurebeshFiles Hand` becomes `AurebeshFilesHand.otf`). Change it for each variation, for example `"AurebeshFiles Bold"`.
- `STYLE` and `VERSION` set the style name and version string.
- `SIDE_BEARING` sets the blank space on each side of a glyph (letter spacing). `SPACE_WIDTH` sets the width of the space character.
- `CAP_HEIGHT` and `X_HEIGHT` set where the cap and x-height guides appear. `CELL_TOP` and `DESCENDER` set the top and bottom of each box in font units.
- `LETTERS`, `DIGRAPHS`, `DIGITS`, `PUNCTUATION`, `SYMBOLS` and `MORE_SYMBOLS` list the glyphs, and `PAGES` decides which sheet each one lands on and how many columns it uses. Add or remove glyphs there, then regenerate the templates.
- New punctuation needs an entry in `_PS_NAMES` (its standard PostScript glyph name, such as `ampersand`).

Pixel sizes (`CELL_PX`, `GUTTER_PX`, `LABEL_PX`, `MARGIN_PX`) control the template layout. Changing them changes the sheet sizes, which has the same effect as a layout change (see above).

## Troubleshooting

| Problem | Likely cause |
|---|---|
| `Nothing traced` | No PNGs in `drawings/`, or they're named wrongly. |
| `size (...) does not match template` | Wrong aspect ratio. Export at the template's full canvas size. |
| A glyph is listed as missing | Empty box, ink too light (below the 128 threshold), or a blob under 12 px. |
| Letters bounce up and down when typed | Glyphs aren't sitting on the base line. |
| Glyphs land in the wrong boxes or look cut off | Canvas wasn't the template's size, or the layout changed after you drew. Regenerate the templates and redraw. |
| `.woff2` fails to save | `brotli` isn't installed. Re-run `pip install -r requirements.txt`. |
| Ligatures don't appear | The app or CSS has ligatures turned off. |

## Files

```
aurebesh.py       the script: template, build, demo
glyphs.py         glyph list, sheet layout, font metrics
requirements.txt  Python dependencies
templates/        blank sheets (generated)
drawings/         your exported PNGs go here
build/            output fonts and preview (generated, git-ignored)
```
