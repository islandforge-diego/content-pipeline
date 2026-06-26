# Content Pipeline

A cloneable, config-driven social-content pipeline for **Island Forge Studio** clients.
Onboard a new client by adding a config + creating an S3 bucket — the same components then
ingest footage, schedule posts, and host a client review page.

## End-to-end flow
1. **Ingest raw footage → S3.** Editors pull source / deliver finals via presigned links
   (replaces WeTransfer; far cheaper than Cloudinary). → `uploader/`
2. **Editor delivers finals → schedule to Buffer.** Captions per platform, scheduled across
   FB / IG / TikTok / LinkedIn / YouTube on the client's cadence. → `buffer/`
3. **Hosted preview page.** Scheduled posts + a Stories calendar surface on the client's review
   page (GitHub Pages) so they see upcoming content. → `content-preview/`

## Layout
```
content-pipeline/
  config/clients/<slug>.json   # stable client profile: brand, channel ids, schedule, bucket, theme
  uploader/                    # push_to_s3.sh — media → S3 → URL (presigned by default)
  buffer/                      # schedule delivered media to Buffer (MCP today; schedule_stub.py to standalone)
  content-preview/             # generate.py — multi-tenant review site (GitHub Pages)
  aws/                         # IAM + bucket policy templates, setup.md
  CLAUDE.md                    # build context for Claude Code working in this repo
```

## Two config layers
- `config/clients/<slug>.json` — **stable profile** (brand, Buffer org/channel ids, schedule, S3 bucket, preview theme). Tweak once per client.
- `content-preview/clients/<slug>/config.json` — **this week's content** (feed posts + story items) that the review page renders. Volatile; updated each cycle.

## Onboard a new client
1. `cp config/clients/_template.json config/clients/<slug>.json` and fill it in (brand, channel ids, bucket).
2. Create their S3 bucket (`aws/setup.md`): region `us-east-2`, ACLs off, Block Public Access ON.
3. Connect their Buffer channels; copy the channel ids into the config.
4. `mkdir -p content-preview/clients/<slug>/stories`, add a week of `content-preview/clients/<slug>/config.json`.
5. `cd content-preview && python3 generate.py` → share `…/clients/<slug>/`.

## Status
- `uploader/` and `content-preview/` are working (ported from the Deba build).
- `buffer/` scheduling runs through the Buffer MCP in Claude today; `schedule_stub.py` is the seed for a standalone version.
- Deba's live preview currently runs from the repo `islandforge-diego/deba-content-preview`; standardizing means pointing that Pages repo at `content-preview/` here (or mirroring it).

## Notes
- The Claude/Cowork sandbox can't reach AWS — uploads run on a Mac or via a GitHub Action.
- `api.github.com` is blocked from the sandbox; create new repos / enable Pages in the GitHub UI, then `git push`.
