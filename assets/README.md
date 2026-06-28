# Branding and visual assets: plan

This directory holds the visual identity for Postman MCP. The docs site already ships a
working SVG logo and favicon at [`../docs/assets/`](../docs/assets/); this plan covers
the larger marketing assets needed for a launch.

## Directory layout

```text
assets/
├── README.md            (this plan)
├── logo/                 the mark, in all required formats
│   ├── logo.svg          master, source of truth (see ../docs/assets/logo.svg)
│   ├── logo-dark.svg     for light backgrounds
│   ├── logo-light.svg    for dark backgrounds
│   ├── logo-256.png
│   └── logo-512.png
├── banner/                README + docs header
│   ├── banner.svg
│   └── banner.png        (1280x640)
├── social/                GitHub social preview / OG image
│   └── social-preview.png  (1280x640)
├── screenshots/           product captures (see capture plan below)
│   ├── syncapi-diff.png
│   ├── syncall-run.png
│   └── collection-result.png
└── architecture/          exported diagrams
    ├── system-overview.svg
    └── request-lifecycle.svg
```

## Brand

| Token | Value | Notes |
|---|---|---|
| Primary | `#FF6C37` | Postman-adjacent orange, matches the docs' `deep orange` palette |
| Ink | `#1B1B1F` | text / dark surfaces |
| Accent | `#FFB088` | highlights |
| Typeface | Inter / system sans | UI and docs |
| Mono | JetBrains Mono / ui-monospace | code and the diff previews |

The mark is a stylized "M" (for MCP) inside a rounded orange tile, already drawn in
[`../docs/assets/logo.svg`](../docs/assets/logo.svg). Export PNG sizes from that master.

## Deliverables, in priority order

1. **GitHub social preview.** `social/social-preview.png`, 1280x640: repo name, tagline,
   and the diff-preview motif on brand orange. Set under repo Settings > Social preview.
   For any AI framing on these assets, follow the
   [messaging guardrails](launch/LAUNCH.md#messaging-guardrails): "Claude-guided" /
   "AI-assisted, powered by Claude Code" — never "AI inside MCP."
2. **README banner.** `banner/banner.png`, full-width, tagline plus logo.
3. **Animated demo.** A terminal/Claude Code recording of `syncapi` producing a diff,
   exported as GIF or SVG, for example with [asciinema](https://asciinema.org/) plus
   [agg](https://github.com/asciinema/agg), or with
   [VHS](https://github.com/charmbracelet/vhs). Embed at the top of the README. This is
   the asset most likely to actually get someone to try the tool, since it shows the
   real thing instead of describing it.
4. **Architecture diagrams.** Export the Mermaid diagrams from
   [`../docs/architecture/overview.md`](../docs/architecture/overview.md) to SVG for the
   README and docs.
5. **Screenshots.** See the capture plan below.

## Screenshot capture plan

Capture inside Claude Code against the
[`../examples/fastapi-basic`](../examples/fastapi-basic) example, so they're
reproducible:

| File | Shows |
|---|---|
| `syncapi-diff.png` | `/postman:syncapi create_payment` diff preview |
| `syncapi-prompt.png` | `/postman:syncapi create_payment --prompt "Act as a Stripe API architect"` — Claude-guided framing, deterministic engine |
| `syncall-run.png` | `/postman:syncall` multi-route preview |
| `collection-result.png` | the populated collection in the Postman UI |

Use a clean terminal theme, hide secrets, and crop to a roughly 16:9 frame. Keep
originals at 2x for retina displays.

## Producing the assets

The SVG masters are hand-editable. For PNG exports:

```bash
# from an SVG master (requires librsvg or Inkscape)
rsvg-convert -w 512 -h 512 logo/logo.svg -o logo/logo-512.png
```

> **Export status.** The PNG deliverables above haven't been generated yet. No SVG-to-PNG
> rasterizer (librsvg, Inkscape, cairosvg, or resvg) is installed in this repo's
> toolchain, and these binaries aren't going to be faked by hand. Install one of the
> above and run the `rsvg-convert` commands, one per size in the layout, to produce them.
> The SVG masters in [`logo/`](logo/) and [`banner/`](banner/) are the source of truth
> and render correctly as-is wherever SVG is supported.

For the VHS-based demo, a `.tape` script should live in `assets/` once it's recorded, so
the GIF is reproducible in CI.
