# Open WebUI design baseline

The console interface uses Open WebUI v0.6.5 as a visual and interaction baseline for its navigation rail, chat header, centered empty state, conversation spacing, and floating composer.

- Upstream: https://github.com/open-webui/open-webui
- Baseline tag: `v0.6.5`
- Upstream license at this tag: BSD 3-Clause

Colors were re-expressed in OKLCH instead of copied as hex. Translucent surfaces are built with `color-mix(..., transparent)`, which lowers the color's alpha rather than the element's `opacity`, so text drawn on them stays fully opaque.

Browsers composite those layers in gamma-encoded sRGB, as upstream does, so a given percentage gives the same tint in both interfaces.

The console remains a separate Next.js implementation connected to its existing API. No current Open WebUI branding or post-v0.6.5 restricted source is bundled.
