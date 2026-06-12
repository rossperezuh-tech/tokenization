# Assembly Coffee London — Style Reference
> Embers in a dark roastery. A near-black canvas with warm, low-lit product photography and italic serif labels — the feeling of a specialty coffee menu printed in a midnight zine.

**Theme:** dark

Assembly Coffee's visual system reads like an editorial magazine printed on black paper. The interface is overwhelmingly dark — near-black canvases carry everything — interrupted only by product photography lit against warm studio backdrops (ember-red, deep amber) and hairline typography in white. Two type families do all the work: a geometric sans (GT America) for UI scaffolding, navigation, and metadata, and a refined serif (ID00 Serif) for product names, section labels, and editorial copy, almost always in italic, which turns a functional nav list into a curated index. The palette is almost monochromatic: the chromatic vocabulary is rationed to badge fills (pale yellow, sage green, antique gold) and the occasional warm-tinted cream surface. Buttons are not loud — price chips and 'Shop Now' links live as small text or pill-shaped cream labels. Components are thin, sharp-cornered, and rely on borders and weight contrast rather than shadows or fills for separation.

## Tokens — Colors

| Name | Value | Token | Role |
|------|-------|-------|------|
| Obsidian | `#0e1311` | `--color-obsidian` | Primary canvas — page backgrounds, hero sections, card surfaces |
| Pure Black | `#000000` | `--color-pure-black` | Deepest surface, borders, and type |
| Ash Charcoal | `#1a1a1a` | `--color-ash-charcoal` | Secondary surface and border tone |
| Graphite | `#333333` | `--color-graphite` | Mid-neutral for secondary text, input borders |
| Stone Gray | `#808080` | `--color-stone-gray` | Image placeholder and muted background tone |
| Silver | `#b3b3b3` | `--color-silver` | De-emphasized borders and helper text |
| Bone | `#ffffff` | `--color-bone` | Primary text on dark canvases |
| Linen | `#f6f7f2` | `--color-linen` | Warm off-white surface for inverted sections, price pills |
| Sand Khaki | `#dfdbca` | `--color-sand-khaki` | Hairline borders, dividers on light surfaces |
| Lichen Green | `#cadcac` | `--color-lichen-green` | Green state accent for badges |
| Citron | `#faf080` | `--color-citron` | Yellow state accent for badges |
| Antique Gold | `#cfa53b` | `--color-antique-gold` | Accent stroke for promotional / limited badges |
| Olive Bark | `#4d4a31` | `--color-olive-bark` | Dark olive announcement bar background |

## Typography

- **GT America Standard** (substitute: Inter) — UI workhorse: nav, body, metadata. Weights 300–600, sizes 11–42px.
- **ID00 Serif** (substitute: Cormorant Garamond Italic / Playfair Display Italic) — editorial voice: product names, headings, manifesto. Almost always italic, weights 300–400.

### Type Scale

| Role | Size | Line Height |
|------|------|-------------|
| caption | 11px | 1.5 |
| body | 16px | 1.5 |
| subheading | 18px | 1.4 |
| heading-sm | 21px | 1.25 |
| heading | 30px | 1.25 |
| heading-lg | 36px | 1.2 |
| display | 42px | 1.2 |

## Spacing & Shapes

Base unit 4px. Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 80, 96, 160.
Radii: nav/cards/badges/inputs/buttons 4px; price pills 60px.
Page max-width 1400px; section gap 80px; card padding 20px.

## Key Components

- **Announcement Bar** — olive-bark background, cream text, GT America 11–13px centered.
- **Primary Header / Nav** — sticky on #0e1311, serif monogram left, sans nav center, utilities right, 1px #1a1a1a border-bottom.
- **Editorial Hero — Featured Column** — vertical index of serif-italic entries on a dark→ember gradient; 'FEATURED' label uppercase 11px.
- **Product Hero** — large product photo on warm ember-red backdrop, no text overlay.
- **Manifesto Block** — full-width obsidian, serif italic 30–36px, no buttons.
- **Product Card (Dark)** — photo upper 65% on warm backdrop; serif italic name; sans tasting notes in silver; price pill bottom-left; 1px #1a1a1a border, 4px radius.
- **Price Pill** — linen #f6f7f2, 60px radius, sans 13px medium, obsidian text.
- **Editorial Tag Badge** — 4px radius, 11px uppercase sans; citron for new release, lichen for editorial categories, antique-gold stroke for limited editions.
- **Typographic CTA** — serif italic links, underline on hover; no filled chromatic buttons.
- **Cart Indicator** — text-only 'Cart (0)'.
- **Pairing Banner** — deep-red (#7a1212) framed event block with hairline border.

## Do's and Don'ts

### Do
- Set headlines and product names in serif italic.
- Keep the canvas near-black; bone type carries hierarchy.
- 4px radii everywhere except the 60px price pill.
- Product imagery on warm, low-lit backdrops (ember red, dark amber, charcoal).
- Badge colors sparingly, editorial tags only.
- CTAs as typographic serif italic links.
- Separate layers with 1px hairlines, not shadows.

### Don't
- No filled chromatic CTA buttons.
- No serif for body/nav; no sans for product names.
- No bright white page backgrounds.
- No saturated brand colors on backgrounds/cards/text.
- No large drop shadows (10px blur @ 5% is the ceiling).
- No headlines at weight 600–700.
- No product imagery on white/light-gray backgrounds.

## Layout

Full-width dark sections stack with 80px+ vertical rhythm. Hero is a two-column split: left ~30% typographic index, right ~55% product photograph. Below: centered manifesto, two-column splits, 3-column product grid (2 on tablet). Gallery cadence: quiet black, loud photograph, quiet black.
