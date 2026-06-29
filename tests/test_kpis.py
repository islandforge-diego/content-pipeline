"""Tests for KPI metric shaping and Calendly booking counts (no network)."""
import kpi_sync
import calendly_api


def _post(plat, reach, reactions, comments, shares=0, saves=0, views=0):
    return {
        "channelService": plat,
        "text": "a fairly long caption with several words in it here",
        "assets": [{"type": "video", "source": "u", "thumbnail": ""}],
        "metrics": [
            {"type": "reach", "value": reach},
            {"type": "views", "value": views},
            {"type": "reactions", "value": reactions},
            {"type": "comments", "value": comments},
            {"type": "shares", "value": shares},
            {"type": "saves", "value": saves},
            {"type": "engagementRate", "value": 5.0},
        ],
    }


def test_summarize_totals_top_and_platforms():
    posts = [_post("instagram", 1000, 50, 10, views=900),
             _post("tiktok", 3000, 20, 5, views=3000),
             _post("linkedin", 500, 5, 1, views=400)]
    s = kpi_sync.summarize_posts(posts)
    assert s["views"] == 4300
    assert s["engagement"] == (60 + 25 + 6)               # actual engagements only
    assert s["posts"] == 3
    assert s["top_posts"][0]["platform"] == "tiktok"      # ranked by views
    assert s["by_platform"]["instagram"]["views"] == 900
    assert s["engagement_rate"] == 5.0
    # total-consistent rate = total engagement / total views (what the page displays)
    assert s["engagement_rate_total"] == round(91 / 4300 * 100, 1)
    assert s["top_posts"][0]["m"]["likes"] == 20          # per-post breakdown present


def test_summarize_empty():
    s = kpi_sync.summarize_posts([])
    assert s["reach"] == 0 and s["top_posts"] == [] and s["engagement_rate"] is None
    assert s["engagement_rate_total"] is None              # no divide-by-zero on empty


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


def test_merge_manual_total_followers():
    summary = {"reach": 0, "engagement": 0, "by_platform": {}}
    client = {"manual_metrics": {
        "facebook_personal": {"reach": 0, "engagement": 0, "followers": 7000},
        "followers": {"as_of": "2026-06-29",
                      "instagram": 1200, "tiktok": 800, "linkedin": 0, "youtube": 300},
    }}
    out = kpi_sync.merge_manual(summary, client)
    # total followers = FB personal + each non-zero manual platform (as_of is not a platform)
    assert out["followers"] == 7000 + 1200 + 800 + 300
    fbp = out["followers_by_platform"]
    assert fbp["facebook"] == 7000
    assert fbp["instagram"] == 1200 and fbp["tiktok"] == 800 and fbp["youtube"] == 300
    assert "linkedin" not in fbp                            # zero entries dropped
    assert "as_of" not in fbp                               # the date key is skipped
    assert out["followers_as_of"] == "2026-06-29"


def test_merge_manual_adds_buffer_new_follows():
    # Buffer-reported new follows since the baseline grow the per-platform totals.
    summary = {"reach": 0, "engagement": 0, "by_platform": {},
               "new_follows_by_platform": {"instagram": 17}}
    client = {"manual_metrics": {
        "followers": {"as_of": "2026-06-29", "instagram": 1200, "tiktok": 800},
    }}
    out = kpi_sync.merge_manual(summary, client)
    assert out["followers_by_platform"]["instagram"] == 1200 + 17   # baseline + growth
    assert out["followers_by_platform"]["tiktok"] == 800            # no growth reported
    assert out["followers"] == 1217 + 800


def test_build_kpis_gates_new_follows_by_as_of(monkeypatch):
    # Only `follows` on posts dated on/after as_of count toward growth.
    posts = [
        {**_post("instagram", 0, 0, 0, views=0), "dueAt": "2026-06-15T00:00:00Z",
         "metrics": [{"type": "follows", "value": 5}]},   # before baseline → ignored
        {**_post("instagram", 0, 0, 0, views=0), "dueAt": "2026-07-02T00:00:00Z",
         "metrics": [{"type": "follows", "value": 9}]},   # after baseline → counted
    ]
    monkeypatch.setattr(kpi_sync.buffer_api, "posts_with_metrics",
                        lambda *a, **k: posts)
    client = {
        "buffer": {"org_id": "o", "channels": {"instagram": {"id": "c1"}}},
        "manual_metrics": {"followers": {"as_of": "2026-06-29", "instagram": 1000}},
    }
    out = kpi_sync.build_kpis(client, "tok", None, window_days=60)
    assert out["new_follows_by_platform"] == {"instagram": 9}
    assert out["followers_by_platform"]["instagram"] == 1009


def test_merge_manual_noop_without_block():
    summary = {"reach": 10, "engagement": 1,
               "by_platform": {"instagram": {"reach": 10, "engagement": 1, "posts": 1}}}
    out = kpi_sync.merge_manual(summary, {})
    assert out["reach"] == 10
    assert "facebook_personal" not in out["by_platform_detail"]


def test_calendly_count_events_csv(tmp_path):
    p = tmp_path / "events.csv"
    p.write_text("Invitee Name,Canceled\nA,false\nB,true\nC,false\nD,FALSE\n", encoding="utf-8")
    c = calendly_api.count_events_csv(str(p))
    assert c["total"] == 4 and c["canceled"] == 1 and c["booked"] == 3


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
