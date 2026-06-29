"""kpi_sync.py — build the Performance (KPIs) block for the client preview.

Business-outcome focused: Calendly bookings + Buffer reach/impressions/engagement,
top posts, and a short AI 'what's working' insight that seeds the feedback loop.

Reach/impressions/engagement are summed from PER-POST Buffer metrics (the org-wide
aggregate only returns metrics common to every channel). Calendly bookings are
optional — they appear once CALENDLY_TOKEN is set.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import buffer_api
import calendly_api

ROOT = Path(__file__).resolve().parent.parent
PREVIEW_DIR = ROOT / "content-preview"

ENGAGE = ("reactions", "comments", "shares", "saves")


def _md(post):
    return {m["type"]: m.get("value", 0) or 0 for m in (post.get("metrics") or [])}


def _short(text, words=8):
    parts = " ".join((text or "").split()).split(" ")
    return " ".join(parts[:words]) + ("…" if len(parts) > words else "")


def summarize_posts(posts):
    """Sum per-post Buffer metrics into totals, per-platform, and top posts."""
    reach = impressions = views = engagement = 0
    rates, per_platform, cards = [], {}, []
    for p in posts:
        md = _md(p)
        r = md.get("reach", 0); imp = md.get("impressions", 0); v = md.get("views", 0)
        eng = sum(md.get(k, 0) for k in ENGAGE)
        reach += r; impressions += imp; views += v; engagement += eng
        if md.get("engagementRate"):
            rates.append(md["engagementRate"])
        plat = p.get("channelService", "") or ""
        pp = per_platform.setdefault(plat, {"reach": 0, "engagement": 0, "posts": 0})
        pp["reach"] += r; pp["engagement"] += eng; pp["posts"] += 1
        assets = p.get("assets") or []
        cards.append({
            "title": _short(p.get("text", "")),
            "platform": plat,
            "reach": r, "engagement": eng,
            "media": ({"type": "video", "src": assets[0].get("source", ""),
                       "poster": assets[0].get("thumbnail", "")} if assets and assets[0].get("type") == "video"
                      else {"type": "gallery", "images": [assets[0]["source"]] if assets else []}),
        })
    top = sorted(cards, key=lambda c: (c["reach"], c["engagement"]), reverse=True)[:5]
    return {
        "posts": len(posts),
        "reach": reach, "impressions": impressions, "views": views,
        "engagement": engagement,
        "engagement_rate": round(sum(rates) / len(rates), 2) if rates else None,
        "by_platform": per_platform,
        "top_posts": top,
    }


def build_kpis(client, buffer_token, calendly_token=None, window_days=30):
    org_id = client["buffer"]["org_id"]
    channel_ids = [c["id"] for c in client["buffer"]["channels"].values() if c.get("id")]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)
    since = start.isoformat()

    posts = buffer_api.posts_with_metrics(buffer_token, org_id, channel_ids, since)
    summary = summarize_posts(posts)

    bookings = None
    cal = client.get("calendly", {})
    if calendly_token:
        try:
            bookings = calendly_api.list_bookings(
                calendly_token, since, end.isoformat(), cal.get("user_uri"))["count"]
        except Exception:
            bookings = None

    summary["bookings"] = bookings
    summary["window_days"] = window_days
    summary["updated"] = end.astimezone(timezone(timedelta(hours=-5))).strftime("%b %-d, %-I:%M %p CT")
    return summary


def sync_kpis(client, buffer_token, calendly_token=None, window_days=None):
    window = window_days or client.get("preview", {}).get("kpi_window_days", 30)
    kpis = build_kpis(client, buffer_token, calendly_token, window)
    slug = client["slug"]
    data_path = PREVIEW_DIR / "clients" / slug / "config.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(data_path.read_text()) if data_path.exists() else {"slug": slug}
    data["kpis"] = kpis
    data_path.write_text(json.dumps(data, indent=2))
    subprocess.run([sys.executable, "generate.py"], cwd=str(PREVIEW_DIR),
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    return kpis
