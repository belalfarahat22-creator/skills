#!/usr/bin/env python3
"""etisalat brand helper.

  python3 brand.py tokens                 # print the palette and type stack
  python3 brand.py contrast FG BG         # WCAG contrast ratio of two hex colours
  python3 brand.py audit FILE [FILE ...]  # colours and fonts used in a .pptx/.docx/.xlsx/.html/.css/.svg,
                                          # flagged when they are not brand tokens

audit exit codes: 0 every colour and font is on-brand, 3 something to review.
Colours are compared exactly; pure black/white and Office's automatic colours are ignored.
"""
import collections
import json
import re
import sys
import zipfile
from pathlib import Path

TOKENS = json.loads((Path(__file__).resolve().parent.parent / "assets" / "brand.json").read_text(encoding="utf-8"))


def palette():
    out = {}
    for group in ("core", "neutrals", "status"):
        for name, v in TOKENS[group].items():
            out.setdefault(v["hex"].upper(), f"{group}.{name}")
    return out


def brand_fonts():
    t = TOKENS["type"]
    names = {t["brand_latin"], t["brand_arabic"], t["office_latin"], t["office_arabic"],
             *t["fallback_latin"], *t["fallback_arabic"]}
    return {n.lower() for n in names}


def luminance(hexcol):
    h = hexcol.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    rgb = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def verdict(ratio):
    if ratio >= 7:
        return "AAA - any text"
    if ratio >= 4.5:
        return "AA - any text"
    if ratio >= 3:
        return "large text (18pt+, or 14pt bold) and graphics only"
    return "FAIL - do not use for text"


IGNORE = {"000000", "FFFFFF"}
HEX6 = re.compile(r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b")


def scan_text(text, colours, fonts, xml):
    if xml:
        for m in re.finditer(r'(?:srgbClr val|w:color w:val|w:fill|rgb)="([0-9A-Fa-f]{6,8})"', text):
            colours[m.group(1)[-6:].upper()] += 1
        for m in re.finditer(r'(?:typeface|w:ascii|w:cs|w:hAnsi|<name val)="([^"]+)"', text):
            fonts[m.group(1)] += 1
        for m in re.finditer(r'<(?:x:)?name val="([^"]+)"', text):
            fonts[m.group(1)] += 1
    else:
        for m in HEX6.finditer(text):
            h = m.group(1).upper()
            colours[h if len(h) == 6 else "".join(c * 2 for c in h)] += 1
        for m in re.finditer(r"font-family\s*:\s*([^;}<]+)", text):
            for f in m.group(1).split(","):
                f = f.strip().strip("'\"")
                if f and not f.startswith("var("):
                    fonts[f] += 1


def used_word_styles(z, styles_xml):
    """Word templates ship a large library of unused styles; keep the defaults plus the styles
    the document body, headers and footers actually apply (and the styles those are based on)."""
    used = set()
    for n in z.namelist():
        if re.match(r"word/(document|header\d*|footer\d*)\.xml$", n):
            used.update(re.findall(r'<w:(?:pStyle|rStyle|tblStyle) w:val="([^"]+)"', z.read(n).decode("utf-8", "ignore")))
    blocks = {sid: blk for blk, sid in re.findall(r'(<w:style\b[^>]*w:styleId="([^"]+)".*?</w:style>)', styles_xml, re.S)}
    for blk in blocks.values():  # default paragraph / table styles apply without being named
        if 'w:default="1"' in blk.split(">", 1)[0]:
            used.add(re.search(r'w:styleId="([^"]+)"', blk).group(1))
    todo = list(used)
    while todo:
        b = blocks.get(todo.pop(), "")
        for base in re.findall(r'<w:(?:basedOn|link) w:val="([^"]+)"', b):
            if base not in used:
                used.add(base)
                todo.append(base)
    defaults = re.search(r"<w:docDefaults>.*?</w:docDefaults>", styles_xml, re.S)
    return (defaults.group(0) if defaults else "") + "".join(blocks[s] for s in used if s in blocks)


def audit(path):
    colours, fonts = collections.Counter(), collections.Counter()
    p = Path(path)
    theme_note = None
    if p.suffix.lower() in {".pptx", ".docx", ".xlsx"}:
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if not n.endswith(".xml") or "/media/" in n:
                    continue
                text = z.read(n).decode("utf-8", "ignore")
                if "/theme/" in n:
                    # The theme carries dozens of per-script fallback fonts and a default colour
                    # scheme; summarise it once instead of auditing every entry.
                    if theme_note is None:
                        major = re.search(r"<a:majorFont>\s*<a:latin typeface=\"([^\"]*)\"", text)
                        minor = re.search(r"<a:minorFont>\s*<a:latin typeface=\"([^\"]*)\"", text)
                        theme_note = (major.group(1) if major else "?", minor.group(1) if minor else "?")
                    continue
                if n == "xl/styles.xml":
                    text = re.sub(r"<colors>.*?</colors>", "", text, flags=re.S)  # Excel's legacy 56-colour palette
                if n == "word/numbering.xml":
                    continue  # bullet glyph fonts (Symbol, Wingdings, Courier New)
                if n in ("word/styles.xml", "word/stylesWithEffects.xml"):
                    text = used_word_styles(z, text)  # only the styles the document applies
                scan_text(text, colours, fonts, xml=True)
    else:
        scan_text(p.read_text(encoding="utf-8", errors="ignore"), colours, fonts, xml=False)

    pal, ok_fonts = palette(), brand_fonts()
    generic = {"sans-serif", "serif", "monospace", "system-ui", "inherit", "+mn-lt", "+mj-lt", "+mn-cs", "+mj-cs", "+mn-ea", "+mj-ea"}
    off_c = {c: n for c, n in colours.items() if c not in IGNORE and f"#{c}" not in pal}
    off_f = {f: n for f, n in fonts.items() if f.lower() not in ok_fonts and f.lower() not in generic}
    print(f"{p.name}")
    if theme_note:
        ok = all(f.lower() in ok_fonts for f in theme_note)
        print(f"  {'ok    ' if ok else 'NOTE  '} theme fonts: headings {theme_note[0]}, body {theme_note[1]}"
              + ("" if ok else " - text that doesn't set its own font falls back to these"))
    on = sorted((f"#{c}", pal[f'#{c}'], n) for c, n in colours.items() if f"#{c}" in pal)
    for h, name, n in on:
        print(f"  ok     {h}  {name} ({n}x)")
    for c, n in sorted(off_c.items(), key=lambda x: -x[1]):
        near = min(pal, key=lambda h: sum((int(h[i:i + 2], 16) - int(c[i - 1:i + 1], 16)) ** 2 for i in (1, 3, 5)))
        print(f"  REVIEW #{c}  not a brand colour ({n}x) - nearest {near} {pal[near]}")
    for f, n in sorted(off_f.items(), key=lambda x: -x[1]):
        print(f"  REVIEW font '{f}' ({n}x) - brand stack is {TOKENS['type']['brand_latin']} / {', '.join(TOKENS['type']['fallback_latin'][:3])}")
    if not (off_c or off_f):
        print("  every colour and font in the content is on-brand")
    return bool(off_c or off_f)


def main(argv):
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    if cmd == "tokens":
        for group in ("core", "neutrals", "status"):
            print(group.upper())
            for name, v in TOKENS[group].items():
                print(f"  {v['hex']}  {name:10s} {v['role']}  (on white {contrast(v['hex'], '#FFFFFF'):.2f}:1)")
        t = TOKENS["type"]
        print(f"TYPE\n  Latin  {t['brand_latin']} -> {', '.join(t['fallback_latin'])} (Office: {t['office_latin']})")
        print(f"  Arabic {t['brand_arabic']} -> {', '.join(t['fallback_arabic'])} (Office: {t['office_arabic']})")
        return 0
    if cmd == "contrast" and len(args) == 2:
        r = contrast(*args)
        print(f"{args[0]} on {args[1]}: {r:.2f}:1 - {verdict(r)}")
        return 0
    if cmd == "audit" and args:
        flagged = [audit(a) for a in args]
        return 3 if any(flagged) else 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
