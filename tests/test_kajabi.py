"""Tests for Kajabi revenue + Community engagement KPI shaping (no network)."""
import kajabi_api
import kajabi_sync
import kpi_sync


def test_build_kajabi_metrics_live(monkeypatch):
    monkeypatch.setattr(kajabi_api, "get_revenue_analytics", lambda *a, **k: [
        {"period": "2026-06-01", "amount": 20153.0, "count": 9},
        {"period": "2026-06-08", "amount": 24404.0, "count": 16},
    ])
    monkeypatch.setattr(kajabi_api, "get_subscriptions_mrr", lambda *a, **k: [
        {"period": "2026-06-01", "grossMrrAmount": 2371.69, "netMrrAmount": 2371.69},
    ])
    monkeypatch.setattr(kajabi_api, "get_revenue_by_offer", lambda *a, **k: [
        {"title": "Roadmap Tier 1", "count": 5, "amount": 1000.0},
        {"title": "Roadmap Mentorship", "count": 88, "amount": 335605.6},
        {"title": "WBC Membership", "count": 565, "amount": 66696.0},
        {"title": "Staging Checkout", "count": 36, "amount": 58490.0},
        {"title": "AV Tier", "count": 17, "amount": 30554.1},
        {"title": "Smallest", "count": 1, "amount": 10.0},
    ])
    monkeypatch.setattr(kajabi_api, "get_contacts_analytics", lambda *a, **k: [
        {"period": "2026-06-01", "count": 9, "totalCount": 1753},
        {"period": "2026-06-08", "count": 16, "totalCount": 1769},
    ])
    monkeypatch.setattr(kajabi_api, "get_community_metrics", lambda *a, **k: {
        "active_users": 120, "new_members": 8, "messages_sent": 340,
        "meetup_rsvp": 12, "challenges_joined": 4,
    })

    client = {"kajabi": {"site_id": "2147563407"}}
    out = kajabi_sync.build_kajabi_metrics(client, "tok", window_days=14)

    assert out["revenue_total"] == 44557.0
    assert out["mrr_gross"] == 2371.69 and out["mrr_net"] == 2371.69
    assert out["new_contacts"] == 25
    assert out["contacts_total"] == 1769            # last period's running total
    assert len(out["top_offers"]) == 5               # capped to top 5
    assert out["top_offers"][0]["title"] == "Roadmap Mentorship"  # sorted by amount desc
    assert out["community"]["active_users"] == 120
    assert out["window_days"] == 14


def test_build_kajabi_metrics_falls_back_to_manual(monkeypatch):
    def boom(*a, **k):
        raise Exception("no creds")
    monkeypatch.setattr(kajabi_api, "get_revenue_analytics", boom)
    monkeypatch.setattr(kajabi_api, "get_subscriptions_mrr", boom)
    monkeypatch.setattr(kajabi_api, "get_revenue_by_offer", boom)
    monkeypatch.setattr(kajabi_api, "get_contacts_analytics", boom)
    monkeypatch.setattr(kajabi_api, "get_community_metrics", boom)

    client = {
        "kajabi": {"site_id": "2147563407"},
        "manual_metrics": {"kajabi": {
            "revenue_total": 24404.0, "mrr_gross": 2371.69, "mrr_net": 2371.69,
            "new_contacts": 119, "contacts_total": 1781,
            "top_offers": [{"title": "Roadmap Mentorship", "amount": 335605.6, "count": 88}],
            "community": {"active_users": None, "new_members": None, "messages_sent": None,
                          "meetup_rsvp": None, "challenges_joined": None},
        }},
    }
    out = kajabi_sync.build_kajabi_metrics(client, kajabi_token="tok")
    assert out["revenue_total"] == 24404.0
    assert out["new_contacts"] == 119
    assert out["top_offers"][0]["title"] == "Roadmap Mentorship"


def test_build_kajabi_metrics_no_token_uses_manual():
    client = {"manual_metrics": {"kajabi": {"revenue_total": 100.0}}}
    out = kajabi_sync.build_kajabi_metrics(client)
    assert out["revenue_total"] == 100.0


def test_build_kajabi_metrics_none_when_nothing_configured():
    assert kajabi_sync.build_kajabi_metrics({}) is None


def test_build_kpis_populates_kajabi_from_manual(monkeypatch):
    monkeypatch.setattr(kpi_sync.buffer_api, "posts_with_metrics", lambda *a, **k: [])
    client = {
        "buffer": {"org_id": "o", "channels": {"instagram": {"id": "c1"}}},
        "manual_metrics": {"kajabi": {"revenue_total": 500.0}},
    }
    out = kpi_sync.build_kpis(client, "tok", window_days=30)
    assert out["kajabi"]["revenue_total"] == 500.0


def test_build_kpis_omits_kajabi_when_unconfigured(monkeypatch):
    monkeypatch.setattr(kpi_sync.buffer_api, "posts_with_metrics", lambda *a, **k: [])
    client = {"buffer": {"org_id": "o", "channels": {"instagram": {"id": "c1"}}}}
    out = kpi_sync.build_kpis(client, "tok", window_days=30)
    assert "kajabi" not in out
