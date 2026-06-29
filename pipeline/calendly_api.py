"""calendly_api.py — count Calendly bookings (the business-outcome KPI).

Calendly API v2. Auth: a Personal Access Token (CALENDLY_TOKEN) as a Bearer
header. We discover the user URI from /users/me (or use a configured one), then
count scheduled events in a time window.
"""
import csv

import requests

BASE = "https://api.calendly.com"


def count_events_csv(path):
    """Count booked vs canceled events from a Calendly event-data CSV export.

    Used as the manual bookings source until the API token is connected.
    Returns {'total', 'booked', 'canceled'}.
    """
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))
    canceled = sum(1 for r in rows if (r.get("Canceled", "") or "").strip().lower() == "true")
    return {"total": len(rows), "booked": len(rows) - canceled, "canceled": canceled}


def _get(url, token, params=None):
    if url.startswith("/"):
        url = BASE + url
    r = requests.get(url, headers={"Authorization": f"Bearer {token}",
                                   "Content-Type": "application/json"},
                     params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def me(token):
    """Return the authenticated user resource (uri, current_organization, ...)."""
    return _get("/users/me", token)["resource"]


def list_bookings(token, since, until, user_uri=None):
    """Count active scheduled events in [since, until] (ISO 8601, e.g. 2026-06-01T00:00:00Z).

    Returns {'count': int, 'events': [...]}. Paginates via Calendly's next_page.
    """
    if not user_uri:
        user_uri = me(token)["uri"]
    params = {"user": user_uri, "min_start_time": since, "max_start_time": until,
              "count": 100, "status": "active"}
    events, url = [], "/scheduled_events"
    for _ in range(50):  # safety cap
        data = _get(url, token, params)
        events += data.get("collection", []) or []
        nxt = (data.get("pagination") or {}).get("next_page")
        if not nxt:
            break
        url, params = nxt, None  # next_page is a full URL with params baked in
    return {"count": len(events), "events": events}
