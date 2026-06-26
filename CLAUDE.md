# Content Pipeline — build context (for Claude Code)

This repo is the **reusable, config-driven content pipeline** for Island Forge Studio (Diego).
Goal: clone it, add one client config + an S3 bucket, and have a working pipeline that ingests
footage, schedules posts to Buffer, and hosts a client review page.

> Client-specific *context* (who Deba is, brand kit, account ids) lives in the **Deba Douglas**
> project's `CLAUDE.md`. This repo is the *system*; that folder is the *client brief*.

## What each component does
- `uploader/push_to_s3.sh` — media → S3 → shareable URL. Presigned by default (works with Block
  Public Access ON). One `studio-uploader` IAM user serves all buckets; `--bucket` targets a client.
- `buffer/` — schedule delivered media to Buffer across FB/IG/TikTok/LinkedIn/YouTube. Today this
  runs through the **Buffer MCP** in Claude; `schedule_stub.py` is the seed for a standalone scheduler.
- `content-preview/generate.py` — multi-tenant static review site. Reads `clients/<slug>/config.json`,
  writes `clients/<slug>/index.html` + a root redirect. Hosted on GitHub Pages.
- `config/clients/<slug>.json` — stable client profile (brand, channel ids, schedule, bucket, theme).
- `aws/` — IAM + bucket-policy templates and `setup.md`.

## Conventions
- **Two config layers:** stable profile in `config/clients/<slug>.json`; volatile per-week content in
  `content-preview/clients/<slug>/config.json`. Don't merge them. Keep theme colors in sync.
- Everything client-specific lives in config; code stays shared. No hardcoded client values in `.py`/`.sh`.
- Default media delivery is **presigned URLs**; only go public via CloudFront or a `media/`-scoped
  bucket policy (`aws/bucket-policy-public-media.json`).
- Stories post as Buffer `schedulingType=notification` reminders (interactive stickers are added in-app).

## Environment constraints (important)
- The Claude/Cowork **sandbox cannot reach AWS** (network allowlisted to GitHub + PyPI). Run S3
  uploads on a Mac (`push_to_s3.sh`) or a GitHub Action — never from the sandbox. (An `AWS API` MCP
  connector, if enabled, can run AWS CLI calls from chat.)
- `api.github.com` is blocked from the sandbox → create repos / enable Pages in the GitHub UI; `git push` works.
- GitHub auth: classic PAT with `repo` scope, supplied per session, not stored.

## Good next steps (not yet built)
1. Make `content-preview/generate.py` read brand/theme from `config/clients/<slug>.json` so there's
   one source of truth for colors (currently the per-week file repeats the theme).
2. Flesh out `buffer/schedule_stub.py` into a real scheduler that reads a `posts.json` manifest +
   the client config and creates Buffer posts (token via env/secret).
3. Optionally generate the preview page's feed data directly from Buffer `list_posts` so the page
   always matches what's actually scheduled.
4. Add a story-card generator component (the PIL generator from the Deba build) under `cards/`.
5. Wire the GitHub Pages repo for the preview site to this `content-preview/` folder.

## How to run what exists
```bash
cd content-preview && python3 generate.py          # build review pages
uploader/push_to_s3.sh clip.mp4 --share            # upload media, get presigned URL (needs aws configure)
python3 buffer/schedule_stub.py config/clients/deba.json buffer/posts.example.json   # dry-run shape
```
