#!/usr/bin/env python3
"""schedule_stub.py — starting point for a standalone Buffer scheduler.

Loads a client profile (config/clients/<slug>.json) and a per-week post manifest,
then shows the shape of the Buffer post payloads. It does NOT call Buffer yet —
wire in the Buffer API token + HTTP request where marked TODO.

Usage:
    python3 schedule_stub.py ../config/clients/deba.json posts.example.json

Post manifest shape (posts.example.json):
[
  {
    "datetime": "2026-06-26T12:00:00-05:00",
    "kind": "reel",                       # reel | image | story
    "media_url": "https://debadouglas.s3.us-east-2.amazonaws.com/reels/skit3.mp4",
    "captions": { "instagram": "...", "facebook": "...", "linkedin": "..." }
  }
]
"""
import json, sys

def channels_for(kind, sched):
    if kind == "reel":  return sched["feed"]["reels_channels"]
    if kind == "image": return sched["feed"]["image_channels"]
    if kind == "story": return [sched["stories"]["channel"]]
    return []

def main(client_path, manifest_path):
    client = json.load(open(client_path))
    posts = json.load(open(manifest_path))
    ch = client["buffer"]["channels"]
    sched = client["schedule"]
    print(f"Client: {client['display_name']}  (Buffer org {client['buffer']['org_id']})")
    for p in posts:
        targets = channels_for(p["kind"], sched)
        print(f"\n{p['datetime']}  [{p['kind']}]  {p['media_url']}")
        for platform in targets:
            cid = ch.get(platform, {}).get("id")
            cap = p.get("captions", {}).get(platform, p.get("captions", {}).get("default", ""))
            if not cid:
                print(f"  - {platform}: (no channel id in config — skip)")
                continue
            payload = {
                "channelId": cid,
                "dueAt": p["datetime"],
                "text": cap,
                "assets": [{"video" if p["kind"] != "image" else "image": {"url": p["media_url"]}}],
            }
            # TODO: POST payload to Buffer API with your token, or hand to the Buffer MCP.
            print(f"  - {platform} ({cid}): would schedule, caption {len(cap)} chars")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__); sys.exit(1)
    main(sys.argv[1], sys.argv[2])
