# PHT × Gowan — Procurement Pitch Deck

A self-contained, 15-slide HTML presentation: *"Procurement Excellence as a System."*
Built from the Claude Design handoff (`PHT Procurement Pitch.html`).

## Viewing

It's a static site — open `index.html` directly in a browser, or serve the folder:

```bash
cd pht-pitch
python3 -m http.server 8000
# then open http://localhost:8000/
```

Serving over HTTP (rather than `file://`) is recommended so the Google Fonts
and relative asset paths load reliably.

## Navigation

- **← / →**, **PgUp / PgDn**, **Space** — previous / next slide
- **Home / End** — first / last slide
- **R** — reset to the first slide
- Click a **chapter tab** in the top bar to jump to that chapter
- On touch devices, tap the left / right half of the stage
- A thumbnail rail (left) lets you click, reorder, skip, or delete slides

## Structure

| File | Purpose |
| --- | --- |
| `index.html` | The deck — all slide markup + styles, authored at 1920×1080 |
| `deck-stage.js` | `<deck-stage>` web component: auto-scaling canvas, keyboard / touch nav, thumbnail rail, print-to-PDF (one slide per page) |
| `pareto.js` | Renders & animates the interactive tail-spend Pareto exhibit (slide 7) |
| `animate.js` | Slide-entry motion (count-up numbers, growing bars), the slide-2 trending-hashtag ticker, the progress bar, and the persistent chapter tab bar |
| `assets/` | Logos and certification marks referenced by the deck |

## Editing

Slide content is static HTML inside `<deck-stage>` in `index.html`, so headings,
stats, and body copy can be edited directly in the markup. Chapter labels live in
one place — the `CHAPTERS` array in `animate.js` — and the trending hashtags on
slide 2 are static, directly-editable text in the cover/opener markup.
