# Notes for Claude Code sessions

- Static site, no build. Keep it that way unless asked.
- Navigation lives in `assets/js/site.js` (`SITE`). Every new page needs an entry there and `data-root`, `data-section`, `data-page` on `<html>`.
- Every exploration reads `data/sample-model.json` through `assets/js/model.js`. Change the model in `tools/build_sample_model.py`, then regenerate.
- Use the layer color tokens (`--l-source` ... `--l-report`) and `DML.layerColor()`; never hard-code layer colors, so dark mode keeps working.
- Pin exact CDN versions (d3 7.9.0, d3-sankey 0.12.3).
- Links to the sister site use relative paths (`../dataviz-lab/` from the root) so they work on github.io and on a custom domain.
- Writing style for guide pages: practitioner voice, opinionated where practice is settled, no em-dashes, no client or employer specifics.
- Reading pages (guide/*, model/) wear the Futobi Labs Test Print skin: `data-skin="testprint"` on `<html>`, the Archivo + IBM Plex Mono font link, and `assets/css/testprint.css` after `site.css`. `site.js` then draws the Test Print header and lab bar, light only. Copy `guide/_template.html` for new guide pages.
- `explore/index.html` is a Test Print landing generated outside the repo (live window plus Go in rooms). Add a new exploration to its rows by hand. The explorations themselves keep their own style and do not take the skin.
