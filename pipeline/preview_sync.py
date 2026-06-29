"""preview_sync.py — build the client preview page from Buffer's real scheduled posts.

Buffer is the single source of truth: this pulls the org's upcoming posts, groups
the per-channel posts of the same video/day into one feed item (so the calendar
shows one card with per-platform captions), preserves the curated stories/theme,
writes content-preview/clients/<slug>/config.json, and rebuilds the HTML.
"""
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytz

import buffer_api

_KEYWORD_RE = re.compile(r'[Cc]omment\s+"?([A-Za-z][A-Za-z ]{0,18}?)"?\s*[\U0001F000-\U0001FAFF👇]', re.UNICODE)
_KEYWORD_RE2 = re.compile(r'[Cc]omment\s+"([^"]{1,20})"')


def _short_title(text, words=6):
    parts = " ".join((text or "").split()).split(" ")
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def _cta_summary(caps):
    """Derive a compact CTA label from the captions: a ManyChat keyword or a link."""
    for _, t in caps:
        m = _KEYWORD_RE2.search(t or "") or _KEYWORD_RE.search(t or "")
        if m:
            return {"type": "comment", "keyword": m.group(1).strip()}
    for _, t in caps:
        low = (t or "").lower()
        if "http" in low or "link in bio" in low or "calendly" in low:
            return {"type": "link"}
    return {}

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = ROOT / "content-preview"


def _local(due, tz_name):
    """Convert a Buffer dueAt (UTC ISO) to (local_date, 'h:MM AM/PM TZ') in tz_name."""
    try:
        dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(pytz.timezone(tz_name))
        z = dt.strftime("%Z")
        # CDT/CST -> CT, EST/EDT -> ET, etc.; keep full label otherwise
        label = (z[0] + "T") if len(z) == 3 and z[1] in ("D", "S") else z
        return dt.strftime("%Y-%m-%d"), dt.strftime("%-I:%M %p") + (" " + label if label else "")
    except Exception:
        return (due[:10], due[11:16])


def posts_to_feed(posts, tz_name="America/Chicago"):
    """Group Buffer post nodes into preview feed items (pure; unit-tested).

    Posts to the same media on the same day become ONE item with each platform's
    caption under it. Times are shown in the client's timezone.
    """
    groups, order = {}, []
    for p in posts:
        due = p.get("dueAt") or ""
        date, time = _local(due, tz_name)
        assets = p.get("assets") or []
        src = assets[0].get("source", "") if assets else ""
        atype = assets[0].get("type", "video") if assets else "video"
        platform = (p.get("channelService") or "").lower()
        key = (date, src)
        if key not in groups:
            media = ({"type": "video", "src": src, "poster": (assets[0].get("thumbnail") if assets else "")}
                     if atype == "video" else {"type": "gallery", "images": [src] if src else []})
            groups[key] = {"iso_date": date, "time": time, "title": "",
                           "chips": [], "media": media, "caps": []}
            order.append(key)
        g = groups[key]
        if platform and platform not in g["chips"]:
            g["chips"].append(platform)
        g["caps"].append([platform, p.get("text") or ""])

    feed = []
    for key in order:
        g = groups[key]
        # brief title from the instagram caption if present, else the first one
        cap = dict(g["caps"]).get("instagram") or (g["caps"][0][1] if g["caps"] else "")
        g["title"] = _short_title(cap)
        g["cta"] = _cta_summary(g["caps"])
        feed.append(g)
    feed.sort(key=lambda f: (f["iso_date"], f.get("time", "")))
    return feed


def stories_to_feed(posts, tz_name="America/Chicago"):
    """Turn Buffer story posts into preview story items (one per post)."""
    items = []
    for p in posts:
        date, time = _local(p.get("dueAt") or "", tz_name)
        assets = p.get("assets") or []
        src = assets[0].get("source", "") if assets else ""
        atype = assets[0].get("type", "image") if assets else "image"
        media = ({"type": "video", "src": src, "poster": (assets[0].get("thumbnail") if assets else "")}
                 if atype == "video" else {"type": "gallery", "images": [src] if src else []})
        items.append({"iso_date": date, "time": time, "media": media,
                      "sticker": p.get("text") or "", "title": ""})
    items.sort(key=lambda s: (s["iso_date"], s.get("time", "")))
    return items


def _is_story(p):
    md = p.get("metadata") or {}
    return (md.get("type") == "story") or (p.get("schedulingType") == "notification")


def sync_preview(client, token):
    """Pull the client's posts from Buffer (history + upcoming) and rebuild the preview.

    Splits feed posts from IG stories; returns (feed_count, story_count).
    """
    org_id = client["buffer"]["org_id"]
    tz_name = client["buffer"].get("timezone", "America/Chicago")
    since = client.get("preview", {}).get("history_since", "2026-06-01") + "T00:00:00-05:00"
    channel_ids = [c["id"] for c in client["buffer"]["channels"].values() if c.get("id")]
    posts = buffer_api.list_scheduled_posts(token, org_id, channel_ids, since=since)

    stories_posts = [p for p in posts if _is_story(p)]
    feed_posts = [p for p in posts if not _is_story(p)]
    feed = posts_to_feed(feed_posts, tz_name)
    stories = stories_to_feed(stories_posts, tz_name)

    slug = client["slug"]
    data_path = PREVIEW_DIR / "clients" / slug / "config.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(data_path.read_text()) if data_path.exists() else {}
    data.setdefault("slug", slug)
    data.setdefault("title", f"{client.get('display_name', slug)} — Content Preview")
    data.setdefault("theme", client.get("preview", {}).get("theme", {}))
    data["feed"] = feed
    data["stories"] = stories
    data_path.write_text(json.dumps(data, indent=2))

    subprocess.run([sys.executable, "generate.py"], cwd=str(PREVIEW_DIR),
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    return len(feed), len(stories)
