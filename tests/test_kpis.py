"""Tests for KPI metric shaping and Calendly booking counts (no network)."""
import kpi_sync
import calendly_api


def _post(plat, reach, reactions, comments, shares=0, saves=0):
    return {
        "channelService": plat,
        "text": "a fairly long caption with several words in it here",
        "assets": [{"type": "video", "source": "u", "thumbnail": ""}],
        "metrics": [
            {"type": "reach", "value": reach},
            {"type": "reactions", "value": reactions},
            {"type": "comments", "value": comments},
            {"type": "shares", "value": shares},
            {"type": "saves", "value": saves},
            {"type": "engagementRate", "value": 5.0},
        ],
    }


def test_summarize_totals_top_and_platforms():
    posts = [_post("instagram", 1000, 50, 10), _post("tiktok", 3000, 20, 5),
             _post("linkedin", 500, 5, 1)]
    s = kpi_sync.summarize_posts(posts)
    assert s["reach"] == 4500
    assert s["engagement"] == (60 + 25 + 6)
    assert s["posts"] == 3
    assert s["top_posts"][0]["platform"] == "tiktok"      # ranked by reach
    assert s["by_platform"]["instagram"]["reach"] == 1000
    assert s["engagement_rate"] == 5.0
    assert s["top_posts"][0]["title"].endswith("…")        # title is truncated


def test_summarize_empty():
    s = kpi_sync.summarize_posts([])
    assert s["reach"] == 0 and s["top_posts"] == [] and s["engagement_rate"] is None


def test_merge_manual_facebook_personal():
    summary = {"reach": 1000, "engagement": 100,
               "by_platform": {"facebook": {"reach": 200, "engagement": 20, "posts": 5},
                               "instagram": {"reach": 800, "engagement": 80, "posts": 10}}}
    client = {"manual_metrics": {"facebook_personal": {"reach": 5000, "engagement": 300, "followers": 7000}}}
    out = kpi_sync.merge_manual(summary, client)
    # totals include the personal profile
    assert out["reach"] == 6000
    assert out["engagement"] == 400
    assert out["followers"] == 7000
    # by_platform shows ONE merged facebook line (page + personal)
    assert out["by_platform"]["facebook"]["reach"] == 5200
    # backend keeps the split
    assert out["by_platform_detail"]["facebook_page"]["reach"] == 200
    assert out["by_platform_detail"]["facebook_personal"]["reach"] == 5000


def test_merge_manual_noop_without_block():
    summary = {"reach": 10, "engagement": 1,
               "by_platform": {"instagram": {"reach": 10, "engagement": 1, "posts": 1}}}
    out = kpi_sync.merge_manual(summary, {})
    assert out["reach"] == 10
    assert "facebook_personal" not in out["by_platform_detail"]


def test_calendly_counts_across_pages(monkeypatch):
    pages = [
        {"collection": [{}, {}], "pagination": {"next_page": "https://api.calendly.com/p2"}},
        {"collection": [{}], "pagination": {"next_page": None}},
    ]
    seq = {"i": 0}

    def fake_get(url, token, params=None):
        page = pages[seq["i"]]
        seq["i"] += 1
        return page

    monkeypatch.setattr(calendly_api, "_get", fake_get)
    out = calendly_api.list_bookings("tok", "2026-06-01T00:00:00Z", "2026-06-30T00:00:00Z", user_uri="u")
    assert out["count"] == 3
