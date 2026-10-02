#!/usr/bin/env python3
"""Hand-drawn Aurebesh font pipeline.

  python aurebesh.py template            # make blank drawing sheets
  python aurebesh.py build               # drawings/*.png -> build/ font files
  python aurebesh.py demo                # fake drawings from a system font, to test
"""
import argparse
import base64
import html
import math
import sys
from pathlib import Path

import numpy as np
import pathops
import potrace
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.areaPen import AreaPen
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.reverseContourPen import ReverseContourPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

import glyphs as G

ROOT = Path(__file__).parent
INK_LUMA = 128          # darker than this = ink (template guides are lighter)
ALPHA_MIN = 128         # more opaque than this = ink
SPECKLE_PX = 12         # ignore blobs smaller than this many pixels

GUIDE = (150, 185, 230)
GUIDE_STRONG = (110, 160, 225)
LABEL = (135, 160, 200)


# ------------------------------------------------------------------ layout
def page_geometry(entries, cols):
    rows = math.ceil(len(entries) / cols)
    w = 2 * G.MARGIN_PX + cols * G.CELL_PX + (cols - 1) * G.GUTTER_PX
    h = 2 * G.MARGIN_PX + rows * (G.LABEL_PX + G.CELL_PX) + (rows - 1) * G.GUTTER_PX
    cells = []
    for i, entry in enumerate(entries):
        r, c = divmod(i, cols)
        x = G.MARGIN_PX + c * (G.CELL_PX + G.GUTTER_PX)
        y = G.MARGIN_PX + G.LABEL_PX + r * (G.LABEL_PX + G.CELL_PX + G.GUTTER_PX)
        cells.append((entry, x, y))
    return (w, h), cells


def font_y_to_px(fy):
    return round((G.CELL_TOP - fy) * G.CELL_PX / G.UPM)


def load_label_font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            pass
    return ImageFont.load_default()


# ------------------------------------------------------------------ template
def cmd_template(args):
    out = ROOT / "templates"
    out.mkdir(exist_ok=True)
    font = load_label_font(30)
    small = load_label_font(20)
    for page, entries, cols in G.PAGES:
        (w, h), cells = page_geometry(entries, cols)
        im = Image.new("RGB", (w, h), "white")
        d = ImageDraw.Draw(im)
        d.text((G.MARGIN_PX, 20), f"{G.FAMILY} - sheet {page}", fill=LABEL, font=font)
        for entry, x, y in cells:
            x1, y1 = x + G.CELL_PX, y + G.CELL_PX
            d.rectangle([x, y, x1, y1], outline=GUIDE, width=2)
            for fy, color, width in ((0, GUIDE_STRONG, 4),
                                     (G.CAP_HEIGHT, GUIDE, 2),
                                     (G.X_HEIGHT, GUIDE, 1)):
                py = y + font_y_to_px(fy)
                if fy == G.X_HEIGHT:
                    for sx in range(x, x1, 24):
                        d.line([sx, py, min(sx + 12, x1), py], fill=color, width=width)
                else:
                    d.line([x, py, x1, py], fill=color, width=width)
            label = entry["chars"] + (f"  {entry['label']}" if entry["label"] else "")
            d.text((x + 4, y - G.LABEL_PX + 8), label, fill=LABEL, font=font)
            for fy, name in ((0, "base"), (G.CAP_HEIGHT, "cap"), (G.X_HEIGHT, "x-height")):
                d.text((x1 - 8, y + font_y_to_px(fy) + 4), name, fill=GUIDE, font=small, anchor="ra")
        path = out / f"{page}.png"
        im.save(path, dpi=(300, 300))
        print(f"  {path.relative_to(ROOT)}  {w}x{h}")


# ------------------------------------------------------------------ tracing
def ink_mask(im):
    im = im.convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    luma = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    return (luma < INK_LUMA) & (a[..., 3] > ALPHA_MIN)


def find_drawing(drawings, page, size):
    num = page.split("-")[0]
    matches = sorted(p for p in drawings.glob("*.png")
                     if p.stem == page or p.stem == num or p.stem.startswith(num + "-")
                     or p.stem.startswith(num + " "))
    if not matches:
        return None
    im = Image.open(matches[0])
    if im.size != size:
        if abs(im.size[0] / im.size[1] - size[0] / size[1]) > 0.01:
            sys.exit(f"{matches[0].name}: size {im.size} does not match template {size}")
        im = im.resize(size, Image.LANCZOS)
    return im


def trace_cell(mask, x, y):
    """Trace one cell's ink into a RecordingPen in font units (unspaced)."""
    pad = G.GUTTER_PX // 2
    x0, y0 = max(x - pad, 0), max(y - pad, 0)
    crop = mask[y0:y + G.CELL_PX + pad, x0:x + G.CELL_PX + pad]
    if crop.sum() < SPECKLE_PX:
        return None
    s = G.UPM / G.CELL_PX

    def pt(p):
        return ((p.x + x0 - x) * s, G.CELL_TOP - (p.y + y0 - y) * s)

    # potracer treats False as ink
    curves = potrace.Bitmap(~crop).trace(turdsize=SPECKLE_PX, alphamax=1.0,
                                         opticurve=True, opttolerance=0.2)
    path = pathops.Path()
    pen = path.getPen()
    for curve in curves:
        pen.moveTo(pt(curve.start_point))
        for seg in curve.segments:
            if seg.is_corner:
                pen.lineTo(pt(seg.c))
                pen.lineTo(pt(seg.end_point))
            else:
                pen.curveTo(pt(seg.c1), pt(seg.c2), pt(seg.end_point))
        pen.closePath()
    path.simplify(fix_winding=True)
    rec = RecordingPen()
    path.draw(rec)
    if not rec.value:
        return None
    # normalise so outer contours run counter-clockwise (PostScript/CFF)
    area = AreaPen()
    rec.replay(area)
    if area.value < 0:
        flipped = RecordingPen()
        rec.replay(ReverseContourPen(flipped))
        rec = flipped
    return rec


def space_glyph(rec):
    """Shift outline so it sits SIDE_BEARING from the left; return (rec, advance)."""
    bp = BoundsPen(None)
    rec.replay(bp)
    xmin, _, xmax, _ = bp.bounds
    out = RecordingPen()
    rec.replay(TransformPen(out, (1, 0, 0, 1, G.SIDE_BEARING - xmin, 0)))
    return out, round(xmax - xmin + 2 * G.SIDE_BEARING)


def trace_all(drawings):
    traced, missing = {}, []
    for page, entries, cols in G.PAGES:
        size, cells = page_geometry(entries, cols)
        im = find_drawing(drawings, page, size)
        if im is None:
            print(f"  {page}: no drawing found, skipping")
            missing += [e["chars"] for e in entries]
            continue
        mask = ink_mask(im)
        done = 0
        for entry, x, y in cells:
            rec = trace_cell(mask, x, y)
            if rec is None:
                missing.append(entry["chars"])
                continue
            traced[entry["name"]] = (entry, *space_glyph(rec))
            done += 1
        print(f"  {page}: {done}/{len(entries)} glyphs")
    return traced, missing


# ------------------------------------------------------------------ font
def notdef():
    rec = RecordingPen()
    w, t, b, s = 500, G.CAP_HEIGHT, 0, 50
    for pts in (((50, b), (w - 50, b), (w - 50, t), (50, t)),
                ((50 + s, b + s), (50 + s, t - s), (w - 50 - s, t - s), (w - 50 - s, b + s))):
        rec.moveTo(pts[0])
        for p in pts[1:]:
            rec.lineTo(p)
        rec.closePath()
    return rec, w


def build_maps(traced):
    """cmap + ligature rules, falling back lowercase -> uppercase when undrawn."""
    names = set(traced)
    cmap = {}
    for name, (entry, _, _) in traced.items():
        if len(entry["chars"]) == 1:
            cmap[ord(entry["chars"])] = name
    for ch in map(chr, range(ord("a"), ord("z") + 1)):
        if ord(ch) not in cmap and ch.upper() in names:
            cmap[ord(ch)] = ch.upper()

    rules = []
    for chars, _ in G.DIGRAPHS:
        up, lo = G.glyph_name(chars), G.glyph_name(chars.lower())
        lo_target = lo if lo in names else up
        a, b = chars
        if up in names:
            rules.append((f"{a} {b}", up))
            rules.append((f"{a} {b.lower()}", up))          # Title case: "Th"
        if lo_target in names:
            rules.append((f"{a.lower()} {b.lower()}", lo_target))
    # only substitute sequences whose component glyphs exist in the font
    glyph_for = {chr(k): v for k, v in cmap.items()}
    fea_lines = []
    for seq, target in rules:
        parts = [glyph_for.get(c) for c in seq.split()]
        if all(parts):
            fea_lines.append(f"    sub {' '.join(parts)} by {target};")
    fea = ""
    if fea_lines:
        fea = ("languagesystem DFLT dflt;\nlanguagesystem latn dflt;\n\n"
               "feature liga {\n" + "\n".join(fea_lines) + "\n} liga;\n")
    return cmap, fea


def make_font(traced, cmap, fea, flavor):
    order = [".notdef", "space"] + sorted(traced)
    outlines = {".notdef": notdef(), "space": (RecordingPen(), G.SPACE_WIDTH)}
    for name, (_, rec, adv) in traced.items():
        outlines[name] = (rec, adv)
    cmap = {**cmap, 0x20: "space"}

    fb = FontBuilder(G.UPM, isTTF=(flavor == "ttf"))
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    metrics = {}
    if flavor == "ttf":
        glyf = {}
        for name in order:
            rec, adv = outlines[name]
            tt = TTGlyphPen(None)
            # TrueType wants clockwise outer contours: reverse the CFF direction
            rec.replay(ReverseContourPen(Cu2QuPen(tt, max_err=1.0)))
            glyf[name] = tt.glyph()
        fb.setupGlyf(glyf)
        for name in order:
            metrics[name] = (outlines[name][1], getattr(glyf[name], "xMin", 0))
    else:
        charstrings = {}
        for name in order:
            rec, adv = outlines[name]
            pen = T2CharStringPen(adv, None)
            rec.replay(pen)
            charstrings[name] = pen.getCharString()
            bp = BoundsPen(None)
            rec.replay(bp)
            metrics[name] = (adv, round(bp.bounds[0]) if bp.bounds else 0)
        ps = G.FAMILY.replace(" ", "") + "-" + G.STYLE
        fb.setupCFF(ps, {"FullName": f"{G.FAMILY} {G.STYLE}"}, charstrings, {})
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=G.CELL_TOP, descent=G.DESCENDER)
    fb.setupNameTable({
        "familyName": G.FAMILY, "styleName": G.STYLE,
        "uniqueFontIdentifier": f"{G.FAMILY} {G.STYLE} {G.VERSION}",
        "fullName": f"{G.FAMILY} {G.STYLE}",
        "psName": G.FAMILY.replace(" ", "") + "-" + G.STYLE,
        "version": f"Version {G.VERSION}",
    })
    fb.setupOS2(sTypoAscender=G.CELL_TOP, sTypoDescender=G.DESCENDER, sTypoLineGap=200,
                usWinAscent=G.CELL_TOP + 100, usWinDescent=-G.DESCENDER + 100,
                sxHeight=G.X_HEIGHT, sCapHeight=G.CAP_HEIGHT, achVendID="NONE")
    fb.setupPost()
    if fea:
        fb.addOpenTypeFeatures(fea)
    return fb.font


# ------------------------------------------------------------------ preview
PREVIEW = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{family} Preview</title>
<style>
@font-face {{ font-family: "Drawn"; src: url(data:font/woff2;base64,{woff2}) format("woff2"); }}
:root {{ --bg: #f7f7f5; --fg: #1c1c1c; --muted: #777; --card: #fff; --line: #e2e2dd; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: #141414; --fg: #eee; --muted: #999; --card: #1e1e1e; --line: #333; }}
}}
body {{ margin: 0; padding: 24px 16px 60px; background: var(--bg); color: var(--fg);
       font: 15px/1.5 -apple-system, system-ui, sans-serif; }}
main {{ max-width: 1100px; margin: 0 auto; }}
h1 {{ font-size: 20px; margin: 0 0 4px; }}
.muted {{ color: var(--muted); }}
.drawn {{ font-family: "Drawn", monospace; }}
textarea {{ width: 100%; box-sizing: border-box; min-height: 110px; padding: 12px;
           background: var(--card); color: var(--fg); border: 1px solid var(--line);
           border-radius: 8px; font-size: var(--size); line-height: 1.3; }}
.controls {{ display: flex; gap: 12px; align-items: center; margin: 16px 0 8px; }}
.samples p {{ font-size: var(--size); margin: 8px 0; overflow-wrap: anywhere; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 8px; }}
.cell {{ background: var(--card); border: 1px solid var(--line); border-radius: 8px;
        padding: 8px; text-align: center; }}
.cell .g {{ font-size: 48px; line-height: 1.3; }}
.cell small {{ display: block; color: var(--muted); font-size: 12px; }}
.cell.missing {{ opacity: .35; }}
</style></head>
<body style="--size: 40px"><main>
<h1>{family}</h1>
<div class="muted">{count} glyphs drawn, {missing} missing. Ligatures on.</div>
<div class="controls"><label>Size <input id="size" type="range" min="16" max="120" value="40"></label></div>
<textarea class="drawn" id="try">Type here. The ship shook, Chewie ran to the engine.</textarea>
<div class="samples drawn">{samples}</div>
<h2>Glyphs</h2>
<div class="grid">{cells}</div>
</main>
<script>
const s = document.getElementById("size");
s.addEventListener("input", () => document.body.style.setProperty("--size", s.value + "px"));
</script></body></html>
"""

SAMPLES = [
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "CH AE EO KH NG OO SH TH  ch ae eo kh ng oo sh th",
    "0123456789 . , ? ! : ; ' \" - ( ) / $",
    "Help me, Obi-Wan Kenobi. You're my only hope!",
    "THE SHIP SHOOK AS THE ENGINE CHOKED.",
]


def write_preview(woff2, traced, missing, path):
    cells = []
    for page, entries, _ in G.PAGES:
        for e in entries:
            cls = "cell" if e["name"] in traced else "cell missing"
            cells.append(f'<div class="{cls}"><div class="g drawn">{html.escape(e["chars"])}</div>'
                         f'<small>{html.escape(e["chars"])} {html.escape(e["label"])}</small></div>')
    samples = "".join(f"<p>{html.escape(s)}</p>" for s in SAMPLES)
    path.write_text(PREVIEW.format(family=html.escape(G.FAMILY),
                                   woff2=base64.b64encode(woff2).decode(),
                                   count=len(traced), missing=len(missing),
                                   samples=samples, cells="".join(cells)))


# ------------------------------------------------------------------ build
def cmd_build(args):
    drawings = Path(args.drawings)
    print(f"Tracing {drawings}/")
    traced, missing = trace_all(drawings)
    if not traced:
        sys.exit("Nothing traced. Put your exported PNGs in drawings/ (see README).")
    cmap, fea = build_maps(traced)

    out = ROOT / "build"
    out.mkdir(exist_ok=True)
    stem = G.FAMILY.replace(" ", "")
    otf = make_font(traced, cmap, fea, "otf")
    otf.save(out / f"{stem}.otf")
    make_font(traced, cmap, fea, "ttf").save(out / f"{stem}.ttf")
    web = TTFont(out / f"{stem}.otf")
    web.flavor = "woff2"
    web.save(out / f"{stem}.woff2")
    write_preview((out / f"{stem}.woff2").read_bytes(), traced, missing, out / "preview.html")

    print(f"\nBuilt {len(traced)} glyphs, {fea.count('sub ')} ligature rules -> build/")
    for f in (f"{stem}.otf", f"{stem}.ttf", f"{stem}.woff2", "preview.html"):
        print(f"  build/{f}")
    if missing:
        print(f"Missing ({len(missing)}): {' '.join(missing)}")


def cmd_demo(args):
    """Fill the sheets with a system font so the pipeline can be tested."""
    out = ROOT / "drawings-demo"
    out.mkdir(exist_ok=True)
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                              round(G.CAP_HEIGHT / 0.716 * G.CELL_PX / G.UPM))
    for page, entries, cols in G.PAGES:
        size, cells = page_geometry(entries, cols)
        im = Image.new("RGBA", size, (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        for e, x, y in cells:
            d.text((x + 40, y + font_y_to_px(0)), e["chars"], fill="black", font=font, anchor="ls")
        im.save(out / f"{page}.png")
    print(f"Demo drawings in {out.relative_to(ROOT)}/. Run: python aurebesh.py build --drawings drawings-demo")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("template", help="generate blank drawing sheets in templates/")
    b = sub.add_parser("build", help="trace drawings and build the font")
    b.add_argument("--drawings", default=str(ROOT / "drawings"))
    sub.add_parser("demo", help="make fake drawings from a system font for testing")
    args = ap.parse_args()
    {"template": cmd_template, "build": cmd_build, "demo": cmd_demo}[args.cmd](args)


if __name__ == "__main__":
    main()
