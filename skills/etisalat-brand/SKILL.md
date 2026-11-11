---
name: etisalat-brand
description: Applies the etisalat (Etisalat UAE, formerly e& / etisalat by e&) look to anything Claude makes - slides, Word reports, Excel dashboards, HTML pages, charts, posters, emails - with the brand red, ink and white palette, the Suiss / GE SS Two type stack and its fallbacks, bilingual English-Arabic layout rules and a colour audit. Use it whenever the user mentions etisalat, Etisalat, e&, eand or an etisalat store or team, asks for something "on brand", "in our colours" or "with company branding" while working for etisalat, or shares an etisalat template to match - even when they don't say the word "brand".
license: Complete terms in LICENSE.txt
---

# etisalat brand

Working brand rules for internal etisalat (UAE) material: store reports, team briefings, dashboards, decks. The core colours, type stack and button shape were read from the public site etisalat.ae on 11 Nov 2026. The neutrals and status colours are derived working values for internal documents. This is not the official brand book: when the user supplies an official template, logo file or brand book, it overrules everything here.

**Naming.** The UAE consumer brand writes its name in lowercase: "etisalat", "etisalat UAE". Material from 2022 to 2025 uses "e&" or "etisalat by e&". Match whatever the user's template or existing file uses, and never mix the two in one piece.

## Colour

| Token | Hex | Use |
|---|---|---|
| Red | `#E00800` | The brand colour. Primary buttons, links, the one figure or word that matters most on a slide. About 10% of a page, never a full-page background behind body text. |
| Ink | `#140F21` | Body text, headings, dark backgrounds, table headers. |
| White | `#FFFFFF` | The main background. Pages are mostly white. |
| Red dark | `#B30600` | Red text on a tinted background, pressed states. |
| Red tint | `#FDE8E7` | Callout boxes, highlighted table rows. |
| Grey 700 | `#5C5866` | Secondary text, captions, footnotes. |
| Grey 400 | `#8A8794` | Disabled text; axis labels only at large sizes. |
| Grey 200 | `#DCDAE0` | Rules, borders, gridlines. |
| Grey 50 | `#F4F3F6` | Alternate rows, side panels. |

**Status (performance against target):** good `#137A47` at 100%+, watch `#9A5B00` at 90-99.9%, below 90% brand red `#E00800`. Always pair the colour with the figure or an icon. Colour is never the only signal.

**Charts:** series in the order ink, red, grey 700, grey 400, grey 200. Put the series the reader must notice (this store, this month, the target line) in red and everything else in ink and greys.

**Contrast:** red on white is 5.0:1, which is fine for any text. Red on ink is only 3.75:1, so use it for large text (18pt+, or 14pt bold) and graphics only. On ink backgrounds write in white. Check any other pairing with `python3 scripts/brand.py contrast FG BG`.

## Type

- **Brand fonts:** Suiss (Latin) and GE SS Two (Arabic). Both are licensed fonts and usually not installed, so don't promise them.
- **Fallbacks:** Inter, then Roboto or Arial for Latin; Noto Sans Arabic, then Tahoma for Arabic. In Office files that will be opened on other PCs use Arial and Tahoma, which are present everywhere.
- **Hierarchy:** one bold heading weight, regular body. Headings in ink, never in red over long lines. Sentence case for headings.
- **Numbers:** tabular figures in tables, thousands separators, "AED 1,250" with the currency first.

## Bilingual layout

- Arabic runs right to left: set `dir="rtl"` in HTML, right-align Arabic paragraphs, and mirror the layout (logo and page numbers move to the opposite side).
- Side by side, English goes on the left and Arabic on the right. Stacked, follow the template, usually English first for internal material.
- Keep numbers in Western digits (0-9) in both languages unless the user's template uses Arabic-Indic digits.
- Never machine-translate customer-facing Arabic without telling the user it needs a native check.

## Logo

Never draw, trace or recreate the logo, and never type the wordmark in a font to fake it. Use the official file the user gives you (SVG or PNG), keep its proportions, give it clear space at least the height of the "e", and place it on white or ink only. If no logo file was given, leave a clearly marked placeholder and say so.

## Shape and spacing

4 px base unit; 5 px corner radius on cards; pill buttons (25 px radius) in red with white text, secondary buttons white with red text. Generous white space and thin grey 200 rules rather than heavy boxes.

## Applying it

| Output | How |
|---|---|
| HTML / web | Link or inline `assets/tokens.css` and use its `--et-*` variables. |
| PowerPoint | `RGBColor.from_string("E00800")` with python-pptx, or the hex without `#` in pptxgenjs. White slides with an ink title. A red accent bar or one red figure per slide. Ink section-divider slides with white text. |
| Word | Headings ink and bold, body ink 10-11pt, table header row ink with white text, alternate rows grey 50. |
| Excel | Header row ink fill with white bold text, gridlines grey 200, totals row bold on grey 50, status colours through conditional formatting (good / watch / red). Don't fill whole sheets in red. |
| Charts (any tool) | The series order and status colours above; no 3-D, no gradients. |

All tokens are machine-readable in `assets/brand.json`, so read them from there in scripts instead of retyping hex codes.

## Check before delivering

1. `python3 scripts/brand.py audit OUTPUT_FILE` lists every colour and font in a .pptx, .docx, .xlsx, .html, .css or .svg. Fix or justify each `REVIEW` line. Colours taken from photos, or from a template the user supplied, are fine; say so.
2. Every text and background pair you introduced passes contrast (red on ink only at large sizes).
3. Name written consistently ("etisalat" or "e&", as the template uses); no recreated logo.
4. Arabic text set RTL, in an Arabic font, and flagged for a native check if you translated it.
5. Tell the user in one line which fonts were substituted (for example "Suiss isn't installed, so I used Inter").
