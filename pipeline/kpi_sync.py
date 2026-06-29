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
        pp = per_platform.setdefault(plat, {"reach": 0, "engagement": 0, "posts": 0, "views": 0})
        pp["reach"] += r; pp["engagement"] += eng; pp["posts"] += 1; pp["views"] += v
        assets = p.get("assets") or []
        cards.append({
            "title": _short(p.get("text", "")),
            "platform": plat,
            "reach": r, "engagement": eng,
            # per-post breakdown for the card (only present metrics get shown)
            "m": {
                "views": int(v),
                "likes": int(md.get("reactions", 0)),   # 'reactions' across platforms = likes
                "comments": int(md.get("comments", 0)),
                "shares": int(md.get("shares", 0)),
                "saves": int(md.get("saves", 0)),
                "watch_min": round(float(md.get("totalTimeWatched", 0)), 1),
            },
            "media": ({"type": "video", "src": assets[0].get("source", ""),
                       "poster": assets[0].get("thumbnail", "")} if assets and assets[0].get("type") == "video"
                      else {"type": "gallery", "images": [assets[0]["source"]] if assets else []}),
        })
    top = sorted(cards, key=lambda c: (c["m"]["views"], c["engagement"]), reverse=True)[:5]
    return {
        "posts": len(posts),
        "reach": reach, "impressions": impressions, "views": views,
        "engagement": engagement,
        "engagement_rate": round(sum(rates) / len(rates), 2) if rates else None,
        "by_platform": per_platform,
        "top_posts": top,
    }


def merge_manual(summary, client):
    """Fold manually-captured metrics (e.g., Facebook personal profile) into totals.

    Backend keeps the split in `by_platform_detail` (facebook_page vs
    facebook_personal); the displayed `by_platform` merges them into one 'facebook'.
    """
    detail = {p: dict(v) for p, v in summary["by_platform"].items()}
    fbp = (client.get("manual_metrics", {}) or {}).get("facebook_personal")
    if fbp:
        r = fbp.get("reach", 0) or 0
        e = fbp.get("engagement", 0) or 0
        f = fbp.get("followers", 0) or 0
        # preserve the distinction in the backend detail
        if "facebook" in detail:
            detail["facebook_page"] = detail.pop("facebook")
        detail["facebook_personal"] = {"reach": r, "views": r, "engagement": e, "posts": 0, "followers": f}
        # add into the top-line totals (reach kept in backend; Views is what we display)
        summary["reach"] += r
        summary["views"] = summary.get("views", 0) + r
        summary["engagement"] += e
        summary["followers"] = (summary.get("followers", 0) or 0) + f
        # merged single 'facebook' line for display (FB 'reach' is its Views metric)
        fb = summary["by_platform"].setdefault("facebook", {"reach": 0, "engagement": 0, "posts": 0, "views": 0})
        fb["reach"] += r
        fb["engagement"] += e
        fb["views"] = fb.get("views", 0) + r
        # pass through the richer drill-down (what drives the personal-profile reach)
        summary["facebook_personal_detail"] = {
            "window": fbp.get("window", ""),
            "reach": r, "engagement": e, "followers": f,
            "views_by_type": fbp.get("views_by_type", []),
            "top_posts": fbp.get("top_posts", []),
            "followers_split": fbp.get("followers_split", []),
        }
    summary["by_platform_detail"] = detail
    return summary


def build_kpis(client, buffer_token, calendly_token=None, window_days=30):
    org_id = client["buffer"]["org_id"]
    channel_ids = [c["id"] for c in client["buffer"]["channels"].values() if c.get("id")]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)
    since = start.isoformat()

    posts = buffer_api.posts_with_metrics(buffer_token, org_id, channel_ids, since)
    summary = summarize_posts(posts)
    summary = merge_manual(summary, client)

    bookings = None
    cal = client.get("calendly", {})
    if calendly_token:
        try:
            bookings = calendly_api.list_bookings(
                calendly_token, since, end.isoformat(), cal.get("user_uri"))["count"]
        except Exception:
            bookings = None
    if bookings is None:  # manual fallback (from a Calendly CSV export) until the API token
        man = (client.get("manual_metrics", {}) or {}).get("calendly") or {}
        if man.get("bookings") is not None:
            bookings = man["bookings"]

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
