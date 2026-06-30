"""kajabi_sync.py — build the Kajabi revenue + Community engagement KPI block.

Mirrors calendly_api's role in kpi_sync.py: each live endpoint is optional and
individually fault-tolerant (one failing call, e.g. a site with no Community,
doesn't blank the whole block), and there's a manual-JSON fallback
(manual_metrics.kajabi) for use before a real Kajabi API token exists.
"""
from datetime import datetime, timedelta, timezone

import kajabi_api

TOP_OFFERS_LIMIT = 5


def _live_kajabi_metrics(token, site_id, since, until):
    """Fetch every live Kajabi metric, each independently fault-tolerant.

    Returns the aggregated kajabi dict, or None if every call failed/returned
    nothing (the caller then falls back to manual_metrics.kajabi).
    """
    revenue_weekly = mrr = offers = contacts = community = None

    try:
        revenue_weekly = kajabi_api.get_revenue_analytics(token, site_id, since, until)
    except Exception:
        revenue_weekly = None

    try:
        mrr = kajabi_api.get_subscriptions_mrr(token, site_id, since, until)
    except Exception:
        mrr = None

    try:
        offers = kajabi_api.get_revenue_by_offer(token, site_id, since, until)
    except Exception:
        offers = None

    try:
        contacts = kajabi_api.get_contacts_analytics(token, site_id, since, until)
    except Exception:
        contacts = None

    try:
        community = kajabi_api.get_community_metrics(token, site_id, since, until)
    except Exception:
        community = None

    if not any([revenue_weekly, mrr, offers, contacts, community]):
        return None

    revenue_total = round(sum(r["amount"] for r in (revenue_weekly or [])), 2) or None
    last_mrr = mrr[-1] if mrr else {}
    top_offers = sorted(offers or [], key=lambda o: o["amount"], reverse=True)[:TOP_OFFERS_LIMIT]
    new_contacts = sum(c["count"] for c in (contacts or [])) or None
    contacts_total = contacts[-1]["totalCount"] if contacts else None

    return {
        "revenue_total": revenue_total,
        "revenue_weekly": [{"period": r["period"], "amount": r["amount"], "count": r["count"]}
                            for r in (revenue_weekly or [])],
        "mrr_gross": last_mrr.get("grossMrrAmount"),
        "mrr_net": last_mrr.get("netMrrAmount"),
        "new_contacts": new_contacts,
        "contacts_total": contacts_total,
        "top_offers": [{"title": o["title"], "amount": o["amount"], "count": o["count"]}
                        for o in top_offers],
        "community": community,
    }


def _manual_kajabi_metrics(client):
    man = (client.get("manual_metrics", {}) or {}).get("kajabi")
    if not man:
        return None
    return {
        "revenue_total": man.get("revenue_total"),
        "revenue_weekly": man.get("revenue_weekly", []),
        "mrr_gross": man.get("mrr_gross"),
        "mrr_net": man.get("mrr_net"),
        "new_contacts": man.get("new_contacts"),
        "contacts_total": man.get("contacts_total"),
        "top_offers": man.get("top_offers", [])[:TOP_OFFERS_LIMIT],
        "community": man.get("community"),
    }


def build_kajabi_metrics(client, kajabi_token=None, window_days=30):
    """Returns the kajabi kpis sub-dict, or None if no live token nor manual data exists."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=window_days)
    since, until = start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    kajabi_cfg = client.get("kajabi", {}) or {}
    site_id = kajabi_cfg.get("site_id")

    metrics = None
    if kajabi_token and site_id:
        metrics = _live_kajabi_metrics(kajabi_token, site_id, since, until)
    if metrics is None:
        metrics = _manual_kajabi_metrics(client)
    if metrics is None:
        return None

    metrics["window_days"] = window_days
    metrics["updated"] = end.astimezone(timezone(timedelta(hours=-5))).strftime("%b %-d, %-I:%M %p CT")
    return metrics
