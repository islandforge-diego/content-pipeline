# content-preview

Mobile-friendly review pages where clients preview their upcoming scheduled content
(per-day feed posts + an Instagram-Stories calendar with tap-to-view cards).
Static HTML, hosted on GitHub Pages. One generator, many clients.

## How it works
- `generate.py` reads every `clients/<slug>/config.json` and writes `clients/<slug>/index.html`,
  plus a root `index.html` that redirects to `DEFAULT_CLIENT`.
- `clients/<slug>/config.json` holds that client's **week of content** (feed posts + story items + theme).
  This is the volatile, per-week data — distinct from the stable client profile in
  `config/clients/<slug>.json` (brand, channel ids, schedule, bucket).

## Update / regenerate
```bash
python3 generate.py
# then commit + push to the GitHub Pages repo for this site
```

## Add a client to the preview
1. `mkdir -p clients/<slug>/stories` and add story PNGs.
2. Create `clients/<slug>/config.json` (copy Deba's; set theme + feed + stories).
3. `python3 generate.py` → share `…/clients/<slug>/`.

## Notes
- This currently lives in the GitHub repo `islandforge-diego/deba-content-preview` (Pages).
  When standardizing, point that repo at this folder, or mirror this `content-preview/` into the Pages repo.
- Pulling the week's feed data straight from Buffer (`list_posts`) so the page stays in sync
  is a good next step — see `../buffer/`.
- `config/clients/<slug>.json.preview.theme` is the source of truth for colors; keep the per-week
  `clients/<slug>/config.json` theme in sync with it.
