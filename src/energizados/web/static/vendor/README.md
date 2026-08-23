# Vendored Web Console Assets

All third-party frontend libraries used by the web console are vendored here so
the console works with **zero external network requests** (offline / air-gapped
deployments). `templates/base.html` references every file below through the
`url_for('static', ...)` pattern.

## Current contents

| File | Library | Version | Source | License |
|------|---------|---------|--------|---------|
| `htmx.min.js` | htmx | 1.9.10 | <https://unpkg.com/htmx.org@1.9.10> | Zero-Clause BSD (0BSD) |
| `bootstrap.min.css` | Bootstrap | 5.3.0 | <https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css> | MIT |
| `bootstrap.bundle.min.js` | Bootstrap | 5.3.0 | <https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js> | MIT |
| `bootstrap-icons/bootstrap-icons.min.css` | Bootstrap Icons | 1.11.3 | <https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css> | MIT |
| `bootstrap-icons/fonts/bootstrap-icons.woff2` / `.woff` | Bootstrap Icons (font) | 1.11.3 | <https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/fonts/> | MIT |
| `plotly-2.27.0.min.js` | Plotly.js | 2.27.0 | <https://cdn.plot.ly/plotly-2.27.0.min.js> | MIT |
| `inter/inter.css` + `inter/inter-*.woff2` | Inter (variable font) | v20 | <https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700> | SIL Open Font License 1.1 |

Notes:

- `bootstrap-icons.min.css` references its fonts through the relative `./fonts/`
  path, so the `bootstrap-icons/fonts/` layout must be preserved.
- Inter is served by the Google Fonts css2 API as a **variable font**
  (weight axis 100–900): one file per subset covers all weights. Only the
  `latin` and `latin-ext` subsets are vendored (the console is English-only).
- The Tailwind Play script used by self-contained *comparison reports* is a
  separate vendored asset: `src/energizados/evaluation/assets/`.

## Updating a vendored version

1. Download the new version from the source URL into this directory (keep the
   file name pinned to the exact version, e.g. `plotly-2.28.0.min.js`).
2. Update the reference in `src/energizados/web/templates/base.html`.
3. Update the table above and the relevant test expectations in
   `tests/web/test_vendored_assets.py`.
4. Verify the version string inside the downloaded file matches the pinned
   filename (do not trust the URL alone).
