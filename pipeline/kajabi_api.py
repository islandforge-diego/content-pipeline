"""kajabi_api.py — revenue and Community engagement (the Kajabi business-outcome KPIs).

Kajabi's site-analytics + communities REST API. Auth: a Partner/Developer API
token as a Bearer header. All endpoints are scoped to one site_id (see
list_sites in the Kajabi MCP connector, or the Kajabi admin URL, to find it).
"""
import requests

BASE = "https://api.kajabi.com"  # TODO: confirm against real Partner API docs once a token exists


def _get(url, token, params=None):
    if url.startswith("/"):
        url = BASE + url
    r = requests.get(url, headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json"},
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_revenue_analytics(token, site_id, since, until, granularity="week"):
    """Revenue over time. Returns a list of {period, amount, count}."""
    data = _get(f"/sites/{site_id}/analytics/revenue", token,
                {"since": since, "until": until, "granularity": granularity})
    return [{"period": r.get("date", "")[:10], "amount": float(r.get("amount", 0) or 0),
              "count": int(r.get("count", 0) or 0)} for r in data.get("results", [])]


def get_subscriptions_mrr(token, site_id, since, until, granularity="week"):
    """MRR over time. Returns a list of {period, grossMrrAmount, netMrrAmount}."""
    data = _get(f"/sites/{site_id}/analytics/mrr", token,
                {"since": since, "until": until, "granularity": granularity})
    return [{"period": r.get("date", "")[:10],
              "grossMrrAmount": float(r.get("grossMrrAmount", 0) or 0),
              "netMrrAmount": float(r.get("netMrrAmount", 0) or 0)} for r in data.get("results", [])]


def get_revenue_by_offer(token, site_id, since, until):
    """Lifetime/windowed revenue per offer. Returns a list of {title, count, amount}."""
    data = _get(f"/sites/{site_id}/analytics/revenue_by_offer", token,
                {"since": since, "until": until})
    return [{"title": r.get("offerTitle", ""), "count": r.get("count"),
              "amount": float(r.get("grossRevenueAmount", 0) or 0)} for r in data.get("results", [])]


def get_contacts_analytics(token, site_id, since, until, granularity="week"):
    """New contacts/leads over time. Returns a list of {period, count, totalCount}."""
    data = _get(f"/sites/{site_id}/analytics/contacts", token,
                {"since": since, "until": until, "granularity": granularity})
    return [{"period": r.get("date", "")[:10], "count": int(r.get("count", 0) or 0),
              "totalCount": int(r.get("totalCount", 0) or 0)} for r in data.get("results", [])]


def get_community_metrics(token, site_id, since, until):
    """Community engagement over a window (max 90 days per Kajabi's API).

    Returns {active_users, new_members, messages_sent, meetup_rsvp,
    challenges_joined}, each an int count, or None if a field is absent.
    Field names are taken from the Kajabi MCP `get_metrics` tool description
    (not yet confirmed against a live response) — re-check this parsing
    against a real payload before trusting it in production.
    """
    data = _get(f"/sites/{site_id}/communities/metrics", token,
                {"start_date": since, "end_date": until})
    metrics = data.get("metrics", {}) or {}

    def count(key):
        v = metrics.get(key)
        return v.get("count") if isinstance(v, dict) else v

    return {
        "active_users": count("active_users"),
        "new_members": count("new_members"),
        "messages_sent": count("messages_sent"),
        "meetup_rsvp": count("meetup_rsvp"),
        "challenges_joined": count("challenges_joined"),
    }
