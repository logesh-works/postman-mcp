# Branding & visual assets — plan

This directory holds the visual identity for Postman MCP. The docs site already ships a
working SVG logo + favicon at [`../docs/assets/`](../docs/assets/); this plan covers the
larger marketing assets needed for a launch.

## Directory layout

```text
assets/
├── README.md            ← this plan
├── logo/                ← the mark, in all required formats
│   ├── logo.svg         (master, source of truth — see ../docs/assets/logo.svg)
│   ├── logo-dark.svg    (for light backgrounds)
│   ├── logo-light.svg   (for dark backgrounds)
│   ├── logo-256.png
│   └── logo-512.png
├── banner/              ← README + docs header
│   ├── banner.svg
│   └── banner.png       (1280×640)
├── social/              ← GitHub social preview / OG image
│   └── social-preview.png  (1280×640)
├── screenshots/         ← product captures (see capture plan below)
│   ├── syncapi-diff.png
│   ├── syncall-run.png
│   └── collection-result.png
└── architecture/        ← exported diagrams
    ├── system-overview.svg
    └── request-lifecycle.svg
```

## Brand

| Token | Value | Notes |
|---|---|---|
| Primary | `#FF6C37` | Postman-adjacent orange; matches the docs `deep orange` palette |
| Ink | `#1B1B1F` | text / dark surfaces |
| Accent | `#FFB088` | highlights |
| Typeface | Inter / system sans | UI + docs |
| Mono | JetBrains Mono / ui-monospace | code + the diff previews |

The mark is a stylized **"M"** (for MCP) inside a rounded orange tile — already drawn in
[`../docs/assets/logo.svg`](../docs/assets/logo.svg). Export PNG sizes from that master.

## Required deliverables (priority order)

1. **GitHub social preview** — `social/social-preview.png`, 1280×640. Repo name +
   tagline + the diff-preview motif on brand orange. Set under repo Settings → Social
   preview.
2. **README banner** — `banner/banner.png`, full-width, tagline + logo.
3. **Animated demo** — a terminal/Claude Code recording of `syncapi` producing a diff,
   exported as GIF/SVG (e.g. with [asciinema](https://asciinema.org/) +
   [agg](https://github.com/asciinema/agg), or [VHS](https://github.com/charmbracelet/vhs)).
   Embed at the top of the README. **This is the single highest-converting asset.**
4. **Architecture diagrams** — export the Mermaid diagrams from
   [`../docs/architecture/overview.md`](../docs/architecture/overview.md) to SVG for the
   README and docs.
5. **Screenshots** — see the capture plan.

## Screenshot capture plan

Capture inside Claude Code against the [`../examples/fastapi-basic`](../examples/fastapi-basic)
example so they're reproducible:

| File | Shows |
|---|---|
| `syncapi-diff.png` | `/postman:syncapi create_payment` diff preview |
| `syncall-run.png` | `/postman:syncall` multi-route preview |
| `collection-result.png` | the populated collection in the Postman UI |

Use a clean terminal theme, hide secrets, and crop to a 16:9-ish frame. Keep originals at
2× for retina.

## Producing the assets

The SVG masters are hand-editable. For PNG exports:

```bash
# from an SVG master (requires librsvg or Inkscape)
rsvg-convert -w 512 -h 512 logo/logo.svg -o logo/logo-512.png
```

For the VHS-based demo, a `.tape` script should live in `assets/` once recorded so the GIF
is reproducible in CI.
