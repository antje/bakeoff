# bakeoff design

One system for the deck, the README, and anything that prints a number. The rule that holds it together: **monochrome, one crumb of color.** Ink and paper do the work; the amber shows up once per surface, on the one thing the reader should look at.

## The mark

A bold B with a bite taken out. The bite says "sampled, not swallowed whole"; the crumbs are the only colored pixels in the whole system, and they set the pattern for how color is used everywhere else: small, few, pointing at something.

| File | Use |
|---|---|
| `assets/mark-dark.svg` | paper B, amber crumbs, transparent. Dark surfaces (deck, README in dark mode). Primary. |
| `assets/mark-light.svg` | ink B, amber crumbs, transparent. Light surfaces (docs, slides in light mode). |
| `assets/icon-dark.svg` | ink tile. Avatars, social preview, anything that needs a solid square. |
| `assets/icon.svg` + `icon-*.png` | amber tile. Favicon and app icons only, where a solid color must read at 16 px. |

Lockup: mark, then `bakeoff` in JetBrains Mono 600, tracking -0.04em, mark height about 1.2x the x-height of the wordmark. Never stretch, recolor the B, or add a second color to the crumbs.

Both SVGs expose `--ink` and `--crumb` CSS variables; the tile icon exposes `--bg`, `--fg`, `--edge`. `scripts/render-assets.sh` re-renders the PNG exports.

## Color

| Token | Value | Role |
|---|---|---|
| `--bg` ink | `#0b0c0f` | background of every dark surface |
| `--surface` | `#14161b` | cards, chat bubbles, help panel |
| `--rule` | `#2a2d34` | hairlines, chip borders, table rules |
| `--muted` | `#9a978f` | secondary text, captions, labels |
| `--fg` paper | `#f3efe6` | primary text, the B |
| `--accent` amber | `#f0b429` | the pointer. Once per surface. |
| `--accent-dim` | `rgba(240,180,41,.14)` | fill behind the pointer when it is a row or box |

Light surfaces (notes view, docs) invert ink and paper: `--bg #f6f4ee`, `--fg #17181c`, `--muted #66645e`, `--rule #dcd9d0`. Amber stays amber.

**What the accent may be:** the verdict row's inset bar, the star-baker chip, the after-number on a before/after row, the URL on the call-to-action, the current step in a numbered recipe, the crumbs.

**What the accent may not be:** running text, commands, headings, question marks, avatars, borders on things that are not the pointer, more than one thing on a slide. If two things want amber, one of them wants weight instead.

## Type

| Face | Weight | Where |
|---|---|---|
| Instrument Serif | 400 roman | slide titles, section headings. Italic only for the tagline. |
| Inter | 400 / 500 / 600 | body, table headers, chat |
| JetBrains Mono | 400 / 600 | numbers, commands, model and provider names, footers, labels |

Numbers are always mono with `font-variant-numeric: tabular-nums`, right-aligned. Labels above tables are Inter, uppercase, 0.8em, letter-spacing 0.04em, muted. The wordmark is mono; the tagline is serif italic; that pairing is the brand voice: precise thing, said warmly.

## Components

**Hairline rows.** Lists of facts sit between 1px `--rule` lines with generous vertical padding. No boxes around rows, no zebra striping.

**Chips.** Mono, uppercase, 1px `--rule` border, pill radius, muted text. At most one chip per surface is filled (`--accent` background, ink text) or outlined in amber; that chip is the verdict.

**Tables.** Mono numbers, muted uppercase headers, one 3px amber inset bar on the verdict row, a caption in muted Inter directly under the table carrying the conditions. A table without its conditions caption is not finished.

**Cards.** `--surface` fill, 1px `--rule` border, 10px radius. Used for quoted chat only.

**Footers.** Left: the lockup at caption size. Right: page or slide counter. Both muted mono.

## Rules of thumb

1. If a slide has no amber, that is fine. If it has two, fix it.
2. Contrast comes from weight and size before it comes from color.
3. Every number carries its conditions. The design has a place for them (the caption) so they are never dropped for space.
4. Nothing decorative: no gradients, no glows, no banner or title images. The mark stands alone at icon size; the title is always live text.
5. When adding a surface, start from the tokens above, not from the deck's CSS.

## Inspiration, not a copy

Gimlet's sites use one loud accent as a small label device on hairlines and outline their icons in a single stroke; the content is monochrome. bakeoff borrows the discipline (accent as label, not as text) and keeps its own ink, paper and amber.
