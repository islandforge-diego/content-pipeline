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
import kajabi_sync

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
        r = md.get("reach", 0); imp = md.get("impressions", 0)
        # "Views" is platform-inconsistent: IG/TikTok/YouTube report `views`, while
        # Facebook pages and most LinkedIn posts report only `impressions` (no views).
        # impressions >= views always, so take the larger as the post's view-count —
        # otherwise FB-page and LinkedIn-image posts read 0.
        v = max(md.get("views", 0) or 0, imp or 0)
        eng = sum(md.get(k, 0) for k in ENGAGE)
        reach += r; impressions += imp; views += v; engagement += eng
        if md.get("engagementRate"):
            rates.append(md["engagementRate"])
        plat = p.get("channelService", "") or ""
        pp = per_platform.setdefault(plat, {"reach": 0, "engagement": 0, "posts": 0,
                                            "views": 0, "saves": 0, "follows": 0})
        pp["reach"] += r; pp["engagement"] += eng; pp["posts"] += 1; pp["views"] += v
        pp["saves"] += md.get("saves", 0); pp["follows"] += md.get("follows", 0)
        assets = p.get("assets") or []
        asset_type = assets[0].get("type", "image").capitalize() if assets else "Image"
        cards.append({
            "title": _short(p.get("text", "")),
            "platform": plat,
            "reach": r, "engagement": eng,
            "externalLink": p.get("externalLink", "") or "",
            "asset_type": asset_type,
            "date": (p.get("dueAt") or "")[:10],
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
    top_by_platform = {}
    for c in cards:
        top_by_platform.setdefault(c["platform"], []).append(c)
    top_by_platform = {
        plat: sorted(psts, key=lambda c: (c["m"]["views"], c["engagement"]), reverse=True)[:5]
        for plat, psts in top_by_platform.items()
    }
    return {
        "posts": len(posts),
        "reach": reach, "impressions": impressions, "views": views,
        "engagement": engagement,
        # Buffer's average of per-post rates (kept for reference)
        "engagement_rate": round(sum(rates) / len(rates), 2) if rates else None,
        # consistent rate: total engagement over total views (what we display)
        "engagement_rate_total": round(engagement / views * 100, 1) if views else None,
        "by_platform": per_platform,
        "top_posts": top,
        "top_by_platform": top_by_platform,
    }


def merge_manual(summary, client):
    """Fold manually-captured metrics (e.g., Facebook personal profile) into totals.

    Backend keeps the split in `by_platform_detail` (facebook_page vs
    facebook_personal); the displayed `by_platform` merges them into one 'facebook'.
    """
    detail = {p: dict(v) for p, v in summary["by_platform"].items()}
    manual = client.get("manual_metrics", {}) or {}
    fbp = manual.get("facebook_personal")
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

    # Total followers across all platforms. Buffer exposes no follower-count API, so each
    # platform's baseline is captured manually (manual_metrics.followers, with an as_of
    # date); Facebook comes from facebook_personal.followers (added to summary["followers"]
    # above). Where Buffer reports a per-post `follows` metric (Instagram only, today), the
    # new follows accrued AFTER the baseline date are added on top — see build_kpis — so the
    # number creeps up automatically between manual refreshes without double-counting the
    # audience already in the baseline.
    new_follows = summary.get("new_follows_by_platform", {}) or {}
    fol_cfg = manual.get("followers") or {}
    fb_followers = (fbp or {}).get("followers", 0) or 0
    followers_by_platform = {}
    if fb_followers:
        fb_growth = int(new_follows.get("facebook", 0) or 0)
        followers_by_platform["facebook"] = fb_followers + fb_growth
        # the baseline was already added in the fbp block; add only the growth here
        summary["followers"] = (summary.get("followers", 0) or 0) + fb_growth
    for plat, count in fol_cfg.items():
        if plat == "as_of":
            continue
        count = int(count or 0)
        if count:
            total = count + int(new_follows.get(plat, 0) or 0)
            followers_by_platform[plat] = total
            summary["followers"] = (summary.get("followers", 0) or 0) + total
    if followers_by_platform:
        summary["followers_by_platform"] = followers_by_platform
        summary["followers_as_of"] = fol_cfg.get("as_of") or (fbp or {}).get("updated") or ""

    # Recompute the displayed rate AFTER folding in manual sources, so it stays
    # consistent with the totals shown (total engagement / total views, incl. Facebook).
    v = summary.get("views", 0) or 0
    summary["engagement_rate_total"] = round(summary["engagement"] / v * 100, 1) if v else None

    summary["by_platform_detail"] = detail
    return summary


def compute_follower_growth(summary, client, posts, today, cutoff30):
    """Per-platform follower totals + 'gained' growth.

    Growth source, in priority order:
      1. Snapshot diff — if a follower-count snapshot from >=30 days ago exists, the
         true 30-day gain is (today's total - that snapshot's total). Accurate, and
         works for every platform. Builds up as snapshots accrue on each sync.
      2. Partial signals (until history matures): Buffer's per-post `follows` over the
         trailing 30 days (Instagram, in practice) and Facebook's manual `net_follows`.

    Returns the updated snapshot history so the caller can persist it. Sets on summary:
    follower_growth {platform: {total, gained, window}}, followers_gained_total,
    followers_gained_is_true_30d, followers_gained_since.
    """
    manual = client.get("manual_metrics", {}) or {}
    cur = summary.get("followers_by_platform", {}) or {}

    # Buffer per-post follows in the trailing 30 days (not gated by the baseline date).
    buf30 = {}
    for p in posts:
        f = int(_md(p).get("follows", 0) or 0)
        if f and (p.get("dueAt") or "")[:10] >= cutoff30:
            plat = p.get("channelService", "") or ""
            buf30[plat] = buf30.get(plat, 0) + f

    # Append today's snapshot to the history (replace any same-date entry).
    history = [h for h in (manual.get("followers_history") or []) if h.get("date") != today]
    history.append({"date": today, "by_platform": dict(cur), "total": summary.get("followers", 0)})
    history.sort(key=lambda h: h.get("date", ""))

    # Accurate 30-day gain if we have a snapshot at least 30 days old.
    snap_gained = None
    prior = [h for h in history if h.get("date", "") <= cutoff30]
    if prior:
        base = prior[-1]
        bp = base.get("by_platform", {}) or {}
        snap_gained = {plat: cur.get(plat, 0) - bp.get(plat, 0) for plat in cur}
        summary["followers_gained_since"] = base.get("date")

    fbp = manual.get("facebook_personal") or {}
    growth, total_gained = {}, 0
    for plat, tot in cur.items():
        gained, window = None, None
        if snap_gained is not None:
            gained, window = snap_gained.get(plat, 0), "30d"
        elif plat == "facebook" and fbp.get("net_follows"):
            gained, window = int(fbp["net_follows"]), fbp.get("window", "")
        elif plat in buf30:
            gained, window = buf30[plat], "30d"
        growth[plat] = {"total": tot, "gained": gained, "window": window}
        if gained:
            total_gained += gained

    summary["follower_growth"] = growth
    summary["followers_gained_is_true_30d"] = snap_gained is not None
    summary["followers_gained_total"] = total_gained if (snap_gained is not None or total_gained) else None
    return history


def build_kpis(client, buffer_token, calendly_token=None, kajabi_token=None, window_days=30):
    org_id = client["buffer"]["org_id"]
    channel_ids = [c["id"] for c in client["buffer"]["channels"].values() if c.get("id")]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)
    since = start.isoformat()

    posts = buffer_api.posts_with_metrics(buffer_token, org_id, channel_ids, since)
    summary = summarize_posts(posts)

    # Follower growth since the manual baseline. Buffer emits a per-post `follows`
    # metric (Instagram only, today); count only posts published on/after the baseline
    # capture date so we don't double-count the audience already in the baseline.
    as_of = ((client.get("manual_metrics", {}) or {}).get("followers") or {}).get("as_of")
    if as_of:
        new_follows = {}
        for p in posts:
            f = int(_md(p).get("follows", 0) or 0)
            if f and (p.get("dueAt") or "")[:10] >= as_of:
                plat = p.get("channelService", "") or ""
                new_follows[plat] = new_follows.get(plat, 0) + f
        if new_follows:
            summary["new_follows_by_platform"] = new_follows

    summary = merge_manual(summary, client)

    today = end.strftime("%Y-%m-%d")
    cutoff30 = (end - timedelta(days=30)).strftime("%Y-%m-%d")
    summary["_followers_history"] = compute_follower_growth(summary, client, posts, today, cutoff30)

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

    kajabi_kpis = kajabi_sync.build_kajabi_metrics(client, kajabi_token, window_days)
    if kajabi_kpis is not None:
        summary["kajabi"] = kajabi_kpis

    summary["window_days"] = window_days
    summary["updated"] = end.astimezone(timezone(timedelta(hours=-5))).strftime("%b %-d, %-I:%M %p CT")
    return summary


def sync_kpis(client, buffer_token, calendly_token=None, kajabi_token=None, window_days=None):
    window = window_days or client.get("preview", {}).get("kpi_window_days", 30)
    kpis = build_kpis(client, buffer_token, calendly_token, kajabi_token, window)
    slug = client["slug"]

    # Persist the follower-count snapshot history back to the source client config so
    # 30-day growth becomes computable over time (the preview data is a derived artifact).
    history = kpis.pop("_followers_history", None)
    if history is not None:
        src = ROOT / "config" / "clients" / f"{slug}.json"
        if src.exists():
            src_cfg = json.loads(src.read_text())
            src_cfg.setdefault("manual_metrics", {})["followers_history"] = history
            src.write_text(json.dumps(src_cfg, indent=2))

    data_path = PREVIEW_DIR / "clients" / slug / "config.json"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(data_path.read_text()) if data_path.exists() else {"slug": slug}
    data["kpis"] = kpis
    data_path.write_text(json.dumps(data, indent=2))
    subprocess.run([sys.executable, "generate.py"], cwd=str(PREVIEW_DIR),
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
    return kpis
