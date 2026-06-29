"""fb_export.py — parse Facebook profile CSV exports into KPI metrics.

Personal FB profiles have no API, but the Professional Dashboard can export CSVs.
This parses the two exports into the `facebook_personal` metrics block:
  - Profile_Activity_Daily breakdown → authoritative totals (views/impressions/
    interactions/net follows) summed over the period.
  - Content_Publish time_Summary → per-post rows → views-by-type + top posts.

Re-run with a fresh export to refresh the numbers (window auto-detected from the
filenames, e.g. "Apr-30-2026_Jun-29-2026").
"""
import csv
import glob
import os
import re

_TYPE_LABEL = {"Content": "Other"}  # FB's generic "Content" reads clearer as "Other"


def _num(s):
    s = (s or "").strip().replace(",", "")
    if not s or s == "--":
        return 0
    try:
        return float(s)
    except ValueError:
        return 0


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _short(text, n=44):
    t = " ".join((text or "").split())
    return (t[:n] + "…") if len(t) > n else t


def _find(folder, needle):
    for f in glob.glob(os.path.join(folder, "*.csv")):
        b = os.path.basename(f)
        if not b.startswith("._") and needle in b:
            return f
    return None


def _window_from_name(path):
    m = re.search(r"([A-Z][a-z]{2}-\d{1,2}-\d{4})_([A-Z][a-z]{2}-\d{1,2}-\d{4})", os.path.basename(path or ""))
    if not m:
        return ""
    fmt = lambda s: s.replace("-", " ", 1).replace("-", ", ")  # Apr-30-2026 -> Apr 30, 2026
    return f"{fmt(m.group(1))} – {fmt(m.group(2))}"


def parse_profile_daily(path):
    """Sum the daily profile metrics over the export window."""
    cols = {"views": "Views", "impressions": "Impressions", "engagement": "Interactions",
            "net_follows": "Net follows", "reactions": "Reactions",
            "comments": "Comments and replies", "shares": "Shares"}
    out = {k: 0 for k in cols}
    rows = _read(path)
    for r in rows:
        for k, c in cols.items():
            out[k] += _num(r.get(c))
    return {k: int(v) for k, v in out.items()}


def parse_content(path, page_name):
    """Return the profile's own posts (filtered to page_name) with their metrics."""
    posts = []
    for r in _read(path):
        if r.get("Page name", "") != page_name:
            continue
        posts.append({
            "title": (r.get("Title", "") or "").strip(),
            "type": (r.get("Post type", "") or "").strip(),
            "views": int(_num(r.get("Views"))),
            "interactions": int(_num(r.get("Interactions"))),
        })
    return posts


def build_facebook_personal(folder, page_name="Deba Douglas", followers=None):
    """Assemble the facebook_personal metrics dict from a folder of FB exports."""
    prof = _find(folder, "Profile_Activity")
    cont = _find(folder, "Content")
    if not prof:
        raise FileNotFoundError("No 'Profile_Activity' CSV found in folder")
    daily = parse_profile_daily(prof)
    posts = parse_content(cont, page_name) if cont else []

    by_type = {}
    for p in posts:
        by_type[p["type"]] = by_type.get(p["type"], 0) + p["views"]
    total = sum(by_type.values()) or 1
    views_by_type = sorted(
        ([_TYPE_LABEL.get(t, t), round(v * 100 / total, 1)] for t, v in by_type.items()),
        key=lambda x: x[1], reverse=True)
    top = sorted(posts, key=lambda p: p["views"], reverse=True)[:5]
    top_posts = [[_short(p["title"]) or p["type"], p["views"]] for p in top]

    return {
        "followers": followers,
        "reach": daily["views"],            # FB 'Views' is the reach-equivalent metric
        "impressions": daily["impressions"],
        "engagement": daily["engagement"],
        "net_follows": daily["net_follows"],
        "window": _window_from_name(prof) or "Last 60 days",
        "views_by_type": views_by_type,
        "top_posts": top_posts,
    }
