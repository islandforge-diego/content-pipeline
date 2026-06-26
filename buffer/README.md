# buffer

Schedule delivered (edited) videos and image posts to the client's social channels via Buffer,
across FB / IG / TikTok / LinkedIn / YouTube on the client's cadence.

## Today (how it's done now)
Scheduling currently happens through the **Buffer MCP connector** inside Claude (Cowork), not a
standalone script. Claude calls `create_post` / `edit_post` against the channel ids in
`config/clients/<slug>.json`, using S3/hosted media URLs from the uploader. Stories go out as
`schedulingType=notification` reminders so the client taps interactive stickers in-app.

## schedule_stub.py
A documented starting point for a standalone scheduler (for when you want this outside Claude,
e.g. a cron/Action). It loads a client config + a simple post manifest and shows the shape of a
Buffer API call. It does NOT post yet — fill in the Buffer API token + HTTP call.

```bash
python3 schedule_stub.py ../config/clients/deba.json posts.example.json
```

## Roadmap (for Claude Code)
- Read a per-week `posts.json` manifest (media URL + per-platform captions + datetime).
- Map platforms → channel ids from the client config; apply reels-vs-image channel rules.
- Call Buffer's API (token in env/secret) to create scheduled posts; print created post ids.
- Optionally write the same manifest into `content-preview/clients/<slug>/config.json` so the
  review page and the schedule are generated from one source of truth.
